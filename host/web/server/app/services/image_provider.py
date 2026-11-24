from __future__ import annotations

import base64
import binascii
import hashlib
import io
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from PIL import Image, ImageDraw

from ..config import Settings

logger = logging.getLogger(__name__)


class ImageAiError(RuntimeError):
    code = "image_ai_error"
    http_status = 502
    retryable = False


class ImageAiConfigurationError(ImageAiError):
    code = "image_ai_not_configured"
    http_status = 503


class ImageAiTimeoutError(ImageAiError):
    code = "image_ai_timeout"
    http_status = 504


class ImageAiRateLimitError(ImageAiError):
    code = "image_ai_rate_limited"
    http_status = 429
    retryable = True


class ImageAiBalanceError(ImageAiError):
    code = "image_ai_insufficient_quota"
    http_status = 402


class ImageAiContentError(ImageAiError):
    code = "image_ai_content_rejected"
    http_status = 422


class ImageAiResponseError(ImageAiError):
    code = "image_ai_invalid_response"


class ImageAiUpstreamError(ImageAiError):
    code = "image_ai_upstream_error"
    retryable = True


@dataclass(frozen=True)
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    source: str
    model: str
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_microusd: int | None = None


class ImageProvider:
    name = "unknown"

    def generate(self, payload: dict[str, Any], safety_identifier: str = "") -> ImageGenerationResult:
        raise NotImplementedError

    def validate_configuration(self) -> None:
        return None


def build_pet_prompt(payload: dict[str, Any]) -> str:
    species = {"fox": "small fox", "cat": "small cat", "rabbit": "small rabbit"}[payload["species"]]
    style = {
        "celestial": "soft celestial 3D cartoon styling with subtle star details",
        "forest": "soft forest-fairytale 3D cartoon styling with natural details",
        "pixel": "polished 3D cartoon styling inspired by clean pixel geometry, not pixelated output",
    }[payload["style"]]
    personality = {
        "energetic": "energetic and friendly",
        "gentle": "gentle and calm",
        "curious": "curious and adventurous",
    }[payload["personality"]]
    description = payload.get("description", "")
    custom = f" Additional original details: {description}." if description else ""
    return (
        f"Create an original VelaPet virtual companion named {payload['name']}: a {personality} {species} "
        f"with {payload['color']} as the primary color, {style}.{custom} "
        "Unified VelaPet visual system: cute, refined, soft 3D cartoon, full body visible, centered subject, "
        "clear silhouette, balanced proportions, expressive but simple face, single character, no text, no logo, "
        "no watermark, no branded character, no copyrighted franchise, clean background, suitable for later "
        "conversion to a small wearable display asset."
    )


class MockImageProvider(ImageProvider):
    name = "mock"

    def generate(self, payload: dict[str, Any], safety_identifier: str = "") -> ImageGenerationResult:
        colors = {"lavender": "#a99bfa", "mint": "#71d7c2", "coral": "#ff9d91", "midnight": "#48589c"}
        image = Image.new("RGBA", (512, 512), (245, 243, 255, 255))
        draw = ImageDraw.Draw(image)
        color = colors.get(str(payload.get("color")), "#a99bfa")
        draw.ellipse((116, 104, 396, 404), fill=color, outline="#5948bd", width=8)
        draw.polygon(((150, 148), (188, 42), (236, 142)), fill=color, outline="#5948bd")
        draw.polygon(((276, 142), (324, 42), (362, 148)), fill=color, outline="#5948bd")
        draw.ellipse((202, 220, 226, 244), fill="#25213d")
        draw.ellipse((286, 220, 310, 244), fill="#25213d")
        draw.arc((224, 230, 288, 294), 20, 160, fill="#5948bd", width=6)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return ImageGenerationResult(
            image_bytes=output.getvalue(), mime_type="image/png", source="mock_asset", model="mock-image-v1",
        )


class OpenAIImageProvider(ImageProvider):
    name = "openai"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def generate(self, payload: dict[str, Any], safety_identifier: str = "") -> ImageGenerationResult:
        self.validate_configuration()
        request_body: dict[str, Any] = {
            "model": self.settings.image_ai_model,
            "prompt": build_pet_prompt(payload),
            "n": 1,
            "size": self.settings.image_ai_size,
            "quality": self.settings.image_ai_quality,
            "output_format": self.settings.image_ai_output_format,
            "response_format": self.settings.image_ai_response_format,
        }
        if self.settings.image_ai_background != "auto":
            request_body["background"] = self.settings.image_ai_background
        if safety_identifier:
            request_body["safety_identifier"] = safety_identifier

        started = time.perf_counter()
        try:
            if self.client is None:
                with httpx.Client(timeout=self.settings.image_ai_timeout_seconds) as client:
                    response = client.post(self._endpoint(), json=request_body, headers=self._headers())
            else:
                response = self.client.post(self._endpoint(), json=request_body, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise ImageAiTimeoutError("OpenAI 图片生成超时；为避免潜在重复计费，任务不会自动重试") from exc
        except httpx.RequestError as exc:
            raise ImageAiError("无法连接 OpenAI 图片服务") from exc

        duration_ms = round((time.perf_counter() - started) * 1000)
        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise ImageAiResponseError("OpenAI 图片服务返回了无法解析的响应") from exc
        if not isinstance(data, dict):
            raise ImageAiResponseError("OpenAI 图片响应不是 JSON 对象")
        images = data.get("data")
        if not isinstance(images, list) or not images or not isinstance(images[0], dict):
            raise ImageAiResponseError("OpenAI 图片响应缺少 data[0]")
        encoded = images[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            if images[0].get("url"):
                raise ImageAiResponseError("OpenAI 仅返回外部 URL；服务端拒绝将其直接作为可信资源")
            raise ImageAiResponseError("OpenAI 图片响应缺少 b64_json")
        if len(encoded) > ((self.settings.image_max_bytes + 2) // 3 * 4 + 8):
            raise ImageAiResponseError("OpenAI 返回的 Base64 图片超过大小限制")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageAiResponseError("OpenAI 返回的图片 Base64 无效") from exc
        if not image_bytes:
            raise ImageAiResponseError("OpenAI 返回了空图片")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        result = ImageGenerationResult(
            image_bytes=image_bytes,
            mime_type="image/" + self.settings.image_ai_output_format,
            source="ai_generated",
            model=str(data.get("model") or self.settings.image_ai_model),
            duration_ms=duration_ms,
            input_tokens=self._safe_int(usage.get("input_tokens")),
            output_tokens=self._safe_int(usage.get("output_tokens")),
            total_tokens=self._safe_int(usage.get("total_tokens")),
        )
        logger.info(
            "image_ai_request provider=openai model=%s duration_ms=%d input_tokens=%d output_tokens=%d total_tokens=%d",
            result.model, result.duration_ms, result.input_tokens, result.output_tokens, result.total_tokens,
        )
        return result

    def validate_configuration(self) -> None:
        if not self.settings.image_ai_api_key:
            raise ImageAiConfigurationError("OpenAI 图片 API Key 未配置")
        if not self.settings.image_ai_model:
            raise ImageAiConfigurationError("OpenAI 图片模型未配置，请按账户权限填写 VELAPET_IMAGE_AI_MODEL")
        if self.settings.image_ai_output_format not in {"png", "webp"}:
            raise ImageAiConfigurationError("图片输出格式仅允许 png 或 webp")
        if self.settings.image_ai_response_format != "b64_json":
            raise ImageAiConfigurationError("VelaPet 私有图片存储要求 response_format=b64_json")
        if self.settings.image_ai_background not in {"auto", "opaque", "transparent"}:
            raise ImageAiConfigurationError("图片背景配置无效")
        if self.settings.image_ai_quality not in {"auto", "low", "medium", "high", "xhigh", "max"}:
            raise ImageAiConfigurationError("图片质量配置无效")
        match = re.fullmatch(r"(\d{2,4})x(\d{2,4})", self.settings.image_ai_size)
        if not match or any(int(value) < 64 or int(value) > 4096 for value in match.groups()):
            raise ImageAiConfigurationError("图片尺寸配置无效")

    def _endpoint(self) -> str:
        return self.settings.image_ai_base_url.rstrip("/") + "/images/generations"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.image_ai_api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _safe_int(value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _error_code(response: httpx.Response) -> str:
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            return str(error.get("code") or error.get("type") or "") if isinstance(error, dict) else ""
        except ValueError:
            return ""

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        code = self._error_code(response)
        if response.status_code == 402 or code in {"insufficient_quota", "billing_hard_limit_reached"}:
            raise ImageAiBalanceError("OpenAI 图片账户额度不足")
        if response.status_code == 429:
            raise ImageAiRateLimitError("OpenAI 图片请求受到限流")
        if response.status_code in {401, 403}:
            raise ImageAiConfigurationError("OpenAI 图片服务鉴权失败，请检查后端 API Key 和组织权限")
        if code in {"content_policy_violation", "moderation_blocked"}:
            raise ImageAiContentError("图片描述未通过供应商内容安全检查")
        if response.status_code >= 500:
            raise ImageAiUpstreamError(f"OpenAI 图片服务暂时不可用（HTTP {response.status_code}）")
        raise ImageAiError(f"OpenAI 图片服务返回错误（HTTP {response.status_code}）")


@dataclass(frozen=True)
class DoubaoModelCapabilities:
    sizes: frozenset[str]
    supports_explicit_size: bool = True
    min_pixels: int = 921_600
    max_pixels: int = 4_624_220
    output_formats: frozenset[str] | None = None
    backgrounds: frozenset[str] | None = None


class DoubaoImageProvider(ImageProvider):
    """Volcengine Ark Seedream adapter using permanent Base64 responses only."""

    name = "doubao"
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def generate(self, payload: dict[str, Any], safety_identifier: str = "") -> ImageGenerationResult:
        del safety_identifier  # Ark Images API has no equivalent field; never send an unsupported parameter.
        capabilities = self.validate_configuration()
        request_body: dict[str, Any] = {
            "model": self.settings.image_ai_model,
            "prompt": build_pet_prompt(payload),
            "size": self.settings.image_ai_size,
            "response_format": self.settings.image_ai_response_format,
            "watermark": self.settings.image_ai_watermark,
        }
        if capabilities.output_formats is not None:
            request_body["output_format"] = self.settings.image_ai_output_format
        if capabilities.backgrounds is not None:
            request_body["background"] = self.settings.image_ai_background

        started = time.perf_counter()
        try:
            if self.client is None:
                with httpx.Client(timeout=self.settings.image_ai_timeout_seconds) as client:
                    response = client.post(self._endpoint(), json=request_body, headers=self._headers())
            else:
                response = self.client.post(self._endpoint(), json=request_body, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise ImageAiTimeoutError("豆包图片生成超时；为避免潜在重复计费，任务不会自动重试") from exc
        except httpx.RequestError as exc:
            raise ImageAiError("无法连接火山方舟图片服务") from exc

        duration_ms = round((time.perf_counter() - started) * 1000)
        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise ImageAiResponseError("豆包图片服务返回了无法解析的响应") from exc
        if not isinstance(data, dict):
            raise ImageAiResponseError("豆包图片响应不是 JSON 对象")
        images = data.get("data")
        if not isinstance(images, list) or not images or not isinstance(images[0], dict):
            raise ImageAiResponseError("豆包图片响应缺少 data[0]")
        item = images[0]
        encoded = item.get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            if item.get("url"):
                raise ImageAiResponseError("豆包仅返回临时 URL；VelaPet 要求 b64_json 并拒绝直接保存临时链接")
            raise ImageAiResponseError("豆包图片响应缺少 b64_json")
        if len(encoded) > ((self.settings.image_max_bytes + 2) // 3 * 4 + 8):
            raise ImageAiResponseError("豆包返回的 Base64 图片超过大小限制")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageAiResponseError("豆包返回的图片 Base64 无效") from exc
        if not image_bytes:
            raise ImageAiResponseError("豆包返回了空图片")

        actual_format = str(item.get("output_format") or self.settings.image_ai_output_format).lower()
        expected_format = self.settings.image_ai_output_format
        if actual_format != expected_format:
            raise ImageAiResponseError(
                f"豆包返回图片格式 {actual_format}，与请求格式 {expected_format} 不一致"
            )
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        result = ImageGenerationResult(
            image_bytes=image_bytes,
            mime_type="image/" + ("jpeg" if actual_format in {"jpg", "jpeg"} else actual_format),
            source="ai_generated",
            model=str(data.get("model") or self.settings.image_ai_model),
            duration_ms=duration_ms,
            input_tokens=self._safe_int(usage.get("input_tokens") or usage.get("prompt_tokens")),
            output_tokens=self._safe_int(usage.get("output_tokens") or usage.get("completion_tokens")),
            total_tokens=self._safe_int(usage.get("total_tokens")),
        )
        logger.info(
            "image_ai_request provider=doubao model=%s duration_ms=%d input_tokens=%d output_tokens=%d total_tokens=%d",
            result.model, result.duration_ms, result.input_tokens, result.output_tokens, result.total_tokens,
        )
        return result

    def validate_configuration(self) -> DoubaoModelCapabilities:
        if not self.settings.image_ai_api_key:
            raise ImageAiConfigurationError("豆包图片 API Key 未配置")
        if not self.settings.image_ai_model:
            raise ImageAiConfigurationError("豆包 Seedream 模型 ID 未配置，请按火山方舟账户权限填写")
        if self.settings.image_ai_response_format != "b64_json":
            raise ImageAiConfigurationError("VelaPet 私有图片存储要求豆包 response_format=b64_json")

        capabilities = self._capabilities(self.settings.image_ai_model)
        self._validate_size(capabilities)
        output_format = self.settings.image_ai_output_format.lower()
        if capabilities.output_formats is None:
            if output_format != "jpeg":
                raise ImageAiConfigurationError("该 Seedream 版本固定输出 JPEG，请设置 VELAPET_IMAGE_AI_OUTPUT_FORMAT=jpeg")
        elif output_format not in capabilities.output_formats:
            raise ImageAiConfigurationError("该 Seedream 版本不支持配置的图片输出格式")

        background = self.settings.image_ai_background.lower()
        if capabilities.backgrounds is None:
            if background != "auto":
                raise ImageAiConfigurationError("该 Seedream 版本不支持 background 参数，请设置为 auto")
        elif background not in capabilities.backgrounds:
            raise ImageAiConfigurationError("该 Seedream 版本不支持配置的 background 值")
        if background == "transparent" and output_format != "png":
            raise ImageAiConfigurationError("透明背景要求 PNG 输出格式")
        return capabilities

    @staticmethod
    def _capabilities(model: str) -> DoubaoModelCapabilities:
        normalized = model.lower().replace(".", "-")
        if "seedream-5-5" in normalized:
            return DoubaoModelCapabilities(
                frozenset({"1K", "1.5K", "2K"}), output_formats=frozenset({"png", "jpeg"}),
                backgrounds=frozenset({"auto", "transparent", "opaque"}),
            )
        if "seedream-5-0-pro" in normalized or "seedream-5-0-flash" in normalized:
            return DoubaoModelCapabilities(
                frozenset({"1K", "1.5K", "2K"}), output_formats=frozenset({"png", "jpeg"}),
                backgrounds=frozenset({"transparent", "opaque"}),
            )
        if "seedream-5-0-lite" in normalized or "seedream-5-0-" in normalized:
            return DoubaoModelCapabilities(
                frozenset({"2K", "3K", "4K"}), min_pixels=3_686_400, max_pixels=16_777_216,
                output_formats=frozenset({"png", "jpeg"}),
            )
        if "seedream-4-5" in normalized:
            return DoubaoModelCapabilities(
                frozenset({"2K", "4K"}), min_pixels=3_686_400, max_pixels=16_777_216,
            )
        if "seedream-4-0" in normalized:
            return DoubaoModelCapabilities(frozenset({"1K", "2K", "4K"}), max_pixels=16_777_216)
        if "seedream-3-0" in normalized:
            return DoubaoModelCapabilities(
                frozenset(), supports_explicit_size=True, min_pixels=262_144, max_pixels=4_194_304,
            )
        raise ImageAiConfigurationError(
            "无法识别 Seedream 模型版本，已拒绝猜测其参数能力；请使用官方模型 ID"
        )

    def _validate_size(self, capabilities: DoubaoModelCapabilities) -> None:
        size = self.settings.image_ai_size
        if size.upper() in capabilities.sizes:
            return
        match = re.fullmatch(r"(\d{3,5})x(\d{3,5})", size.lower())
        if not match or not capabilities.supports_explicit_size:
            allowed = "、".join(sorted(capabilities.sizes)) or "显式宽x高"
            raise ImageAiConfigurationError(f"该 Seedream 版本不支持尺寸 {size}；可用档位：{allowed}")
        width, height = (int(value) for value in match.groups())
        pixels = width * height
        ratio = width / height
        if width > 4096 or height > 4096:
            raise ImageAiConfigurationError("VelaPet 私有存储当前限制图片单边不超过 4096 像素")
        if not (capabilities.min_pixels <= pixels <= capabilities.max_pixels and 1 / 16 <= ratio <= 16):
            raise ImageAiConfigurationError("Seedream 图片尺寸必须满足总像素与宽高比限制")

    def _endpoint(self) -> str:
        return self.settings.image_ai_base_url.rstrip("/") + "/images/generations"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.image_ai_api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _safe_int(value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0

    def _error_details(self, response: httpx.Response) -> tuple[str, str]:
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            if not isinstance(error, dict):
                return "", ""
            code = re.sub(r"[^A-Za-z0-9._-]", "_", str(error.get("code") or error.get("type") or ""))[:160]
            message = str(error.get("message") or "")
            if self.settings.image_ai_api_key:
                message = message.replace(self.settings.image_ai_api_key, "[REDACTED]")
            message = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", message)
            message = re.sub(
                r"(?i)(api[-_ ]?key|authorization)\s*[:=]\s*[^\s,;]+",
                r"\1=[REDACTED]",
                message,
            )
            message = " ".join(message.split())[:300]
            return code, message
        except ValueError:
            return "", ""

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        code, safe_message = self._error_details(response)
        lowered = code.lower()
        if response.status_code == 402 or any(word in lowered for word in ("balance", "overdue", "quota", "credit")):
            raise ImageAiBalanceError("火山方舟图片账户余额或额度不足")
        if response.status_code == 429:
            raise ImageAiRateLimitError("火山方舟图片请求受到限流")
        if response.status_code in {401, 403}:
            raise ImageAiConfigurationError("火山方舟图片服务鉴权失败，请检查后端 API Key 和模型权限")
        if response.status_code == 404:
            details = f"code={code or 'unknown'}"
            if safe_message:
                details += f"，message={safe_message}"
            raise ImageAiConfigurationError(f"火山方舟图片服务未找到模型或端点（HTTP 404，{details}）")
        if any(word in lowered for word in ("content", "moderation", "safety")):
            raise ImageAiContentError("图片描述未通过供应商内容安全检查")
        if response.status_code >= 500:
            raise ImageAiUpstreamError(f"火山方舟图片服务暂时不可用（HTTP {response.status_code}）")
        raise ImageAiError(f"火山方舟图片服务返回错误（HTTP {response.status_code}）")


def safety_identifier(user_id: str) -> str:
    return "velapet-" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]


def get_image_provider(settings: Settings) -> ImageProvider:
    if settings.image_ai_provider == "mock":
        return MockImageProvider()
    if settings.image_ai_provider == "openai":
        return OpenAIImageProvider(settings)
    if settings.image_ai_provider == "doubao":
        return DoubaoImageProvider(settings)
    raise ImageAiConfigurationError(f"不支持的图片 AI Provider：{settings.image_ai_provider}")
