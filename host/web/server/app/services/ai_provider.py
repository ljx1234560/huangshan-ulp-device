from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings

logger = logging.getLogger(__name__)


class TextAiError(RuntimeError):
    code = "text_ai_error"
    http_status = 502


class TextAiConfigurationError(TextAiError):
    code = "text_ai_not_configured"
    http_status = 503


class TextAiTimeoutError(TextAiError):
    code = "text_ai_timeout"
    http_status = 504


class TextAiRateLimitError(TextAiError):
    code = "text_ai_rate_limited"
    http_status = 429


class TextAiBalanceError(TextAiError):
    code = "text_ai_insufficient_balance"
    http_status = 402


class TextAiResponseError(TextAiError):
    code = "text_ai_invalid_response"
    http_status = 502


class TextAiEmptyResponseError(TextAiResponseError):
    code = "text_ai_empty_response"


class TextAiJsonSyntaxError(TextAiResponseError):
    code = "text_ai_invalid_json"


class TextAiSchemaError(TextAiResponseError):
    code = "text_ai_schema_mismatch"


class TextAiTruncatedResponseError(TextAiResponseError):
    code = "text_ai_truncated_response"


@dataclass(frozen=True)
class ActivityInsight:
    window_days: int
    days_with_data: int
    today_steps: int
    today_active_minutes: int
    current_goal: int
    average_steps: int
    average_active_minutes: int
    completed_days: int
    trend_percent: int
    safe_goal_min: int
    safe_goal_max: int
    sufficient_data: bool


class TextAdvice(BaseModel):
    """Strict schema shared by every text provider and the coaching router."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, frozen=True)

    today_summary: str = Field(min_length=1)
    today_advice: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    weekly_plan: str = Field(min_length=1)
    pet_encouragement: str = Field(min_length=1)


@dataclass(frozen=True)
class TextGeneration:
    advice: TextAdvice
    provider: str
    model: str
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TextProvider:
    def generate(self, insight: ActivityInsight, pet_name: str) -> TextGeneration:
        raise NotImplementedError


def insufficient_data_generation(insight: ActivityInsight, pet_name: str) -> TextGeneration:
    return TextGeneration(
        advice=TextAdvice(
            today_summary=f"最近 {insight.window_days} 天只有 {insight.days_with_data} 天运动记录，暂不足以判断稳定趋势。",
            today_advice="先继续正常佩戴并同步至少 3 天数据，再生成个性化目标；今天可按自身感受进行轻松日常活动。",
            reason="当前数据量不足，因此没有推测缺失日期的步数、活动时长或完成情况。",
            weekly_plan="本周先以持续同步和规律活动为主，不根据不完整记录提高运动目标。",
            pet_encouragement=f"{pet_name}会陪你慢慢积累真实脚印，数据完整后再一起规划新旅程！",
        ),
        provider="rules",
        model="safe-rules-v1",
    )


class MockTextProvider(TextProvider):
    def generate(self, insight: ActivityInsight, pet_name: str) -> TextGeneration:
        if not insight.sufficient_data:
            generated = insufficient_data_generation(insight, pet_name)
            return TextGeneration(generated.advice, "mock", "mock-text-v1")
        remaining = max(0, insight.current_goal - insight.today_steps)
        direction = "上升" if insight.trend_percent > 5 else "下降" if insight.trend_percent < -5 else "平稳"
        advice = (
            f"今天还差 {remaining:,} 步，可拆成两次轻松步行完成；不必一次走完。"
            if remaining
            else "今天已达到当前目标，接下来保持轻松活动并留出恢复时间。"
        )
        return TextGeneration(
            advice=TextAdvice(
                today_summary=f"今天 {insight.today_steps:,} 步、活跃 {insight.today_active_minutes} 分钟。",
                today_advice=advice,
                reason=f"近期开启记录的日均步数为 {insight.average_steps:,}，趋势整体{direction}。",
                weekly_plan=f"本周单日目标建议保持在 {insight.safe_goal_min:,}–{insight.safe_goal_max:,} 步，优先规律而非突增。",
                pet_encouragement=f"{pet_name}已经收好今天的脚印，按自己的节奏继续就很棒！",
            ),
            provider="mock",
            model="mock-text-v1",
        )


class DeepSeekTextProvider(TextProvider):
    max_attempts = 2

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def generate(self, insight: ActivityInsight, pet_name: str) -> TextGeneration:
        if not self.settings.text_ai_api_key:
            raise TextAiConfigurationError("DeepSeek API Key 未配置")
        if not self.settings.text_ai_model:
            raise TextAiConfigurationError("DeepSeek 模型名称未配置，请按账户权限填写 VELAPET_TEXT_AI_MODEL")
        started = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        model = self.settings.text_ai_model
        for attempt in range(self.max_attempts):
            response = self._post(self._request_body(insight, pet_name, retry=attempt > 0))
            self._raise_for_status(response)
            finish_reason = "unknown"
            try:
                data = self._parse_response(response)
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                prompt_tokens += self._safe_int(usage.get("prompt_tokens"))
                completion_tokens += self._safe_int(usage.get("completion_tokens"))
                total_tokens += self._safe_int(usage.get("total_tokens"))
                model = str(data.get("model") or self.settings.text_ai_model)
                finish_reason = self._finish_reason(data)
                advice = self._parse_advice(data, finish_reason)
            except TextAiResponseError as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                logger.warning(
                    "text_ai_response_invalid provider=deepseek model=%s error_code=%s finish_reason=%s "
                    "attempt=%d duration_ms=%d prompt_tokens=%d completion_tokens=%d total_tokens=%d",
                    model, exc.code, finish_reason, attempt + 1, elapsed_ms,
                    prompt_tokens, completion_tokens, total_tokens,
                )
                if attempt + 1 < self.max_attempts:
                    continue
                raise type(exc)(f"{exc}；已重试一次仍失败") from exc

            generation = TextGeneration(
                advice=advice,
                provider="deepseek",
                model=model,
                duration_ms=round((time.perf_counter() - started) * 1000),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            logger.info(
                "text_ai_request provider=deepseek model=%s finish_reason=%s attempts=%d duration_ms=%d "
                "prompt_tokens=%d completion_tokens=%d total_tokens=%d",
                generation.model, finish_reason, attempt + 1, generation.duration_ms,
                generation.prompt_tokens, generation.completion_tokens, generation.total_tokens,
            )
            return generation
        raise TextAiResponseError("DeepSeek 未生成可用建议")

    def _request_body(self, insight: ActivityInsight, pet_name: str, retry: bool) -> dict[str, Any]:
        example = {
            "today_summary": "今天已记录 8362 步，活跃 45 分钟。",
            "today_advice": "今天可分两次轻松步行完成剩余活动量。",
            "reason": "建议依据近期日均步数、活动时长和目标完成情况。",
            "weekly_plan": "本周在安全目标范围内保持规律活动，并安排恢复日。",
            "pet_encouragement": f"{pet_name}会陪你按自己的节奏继续前进！",
        }
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是 VelaPet 的一般健身建议助手。仅依据提供的运动汇总生成非医疗建议，不诊断疾病，"
                    "不修改运动记录、宠物等级或 EXP。必须只输出一个完整、合法的 json 对象，不要使用 Markdown，"
                    "不要输出代码围栏，不要添加示例之外的字段。所有五个字段都必须是非空字符串。\n"
                    "目标 JSON 格式示例：\n" + json.dumps(example, ensure_ascii=False, indent=2)
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于以下 json 运动汇总生成中文建议。周计划不得超出 safe_goal_min 与 safe_goal_max；"
                    "不得声称拥有心率、血氧、GPS 或疾病信息。只返回符合示例的 json 对象。\n"
                    + json.dumps({**asdict(insight), "pet_name": pet_name}, ensure_ascii=False)
                ),
            },
        ]
        if retry:
            messages.append({
                "role": "user",
                "content": (
                    "上一次响应未通过结构校验。请重新生成，只返回完整 json；严格包含 today_summary、"
                    "today_advice、reason、weekly_plan、pet_encouragement 五个非空字符串字段。"
                ),
            })
        return {
            "model": self.settings.text_ai_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 1600,
            "stream": False,
        }

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        try:
            if self.client is None:
                with httpx.Client(timeout=self.settings.text_ai_timeout_seconds) as client:
                    return client.post(self._endpoint(), json=body, headers=self._headers())
            return self.client.post(self._endpoint(), json=body, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise TextAiTimeoutError("DeepSeek 请求超时，请稍后重试") from exc
        except httpx.RequestError as exc:
            raise TextAiError("无法连接 DeepSeek 服务，请检查网络后重试") from exc

    def _endpoint(self) -> str:
        return self.settings.text_ai_base_url.rstrip("/") + "/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.text_ai_api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _safe_int(value: Any) -> int:
        return int(value) if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise TextAiResponseError("DeepSeek 返回了无法解析的响应") from exc
        if not isinstance(data, dict):
            raise TextAiResponseError("DeepSeek 响应格式不合法")
        return data

    @staticmethod
    def _first_choice(data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise TextAiSchemaError("DeepSeek 响应缺少 choices[0]")
        return choices[0]

    def _finish_reason(self, data: dict[str, Any]) -> str:
        value = self._first_choice(data).get("finish_reason")
        return value if isinstance(value, str) and value else "unknown"

    def _parse_advice(self, data: dict[str, Any], finish_reason: str) -> TextAdvice:
        choice = self._first_choice(data)
        if finish_reason == "length":
            raise TextAiTruncatedResponseError("DeepSeek JSON 因达到输出长度限制而被截断")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise TextAiSchemaError("DeepSeek 响应缺少 message 对象")
        content = message.get("content")
        if not isinstance(content, str):
            raise TextAiSchemaError("DeepSeek message.content 必须是字符串")
        if not content.strip():
            raise TextAiEmptyResponseError(
                f"DeepSeek 返回空白内容（finish_reason={finish_reason}）"
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise TextAiJsonSyntaxError(
                f"DeepSeek 返回的 JSON 语法错误（第 {exc.lineno} 行第 {exc.colno} 列）"
            ) from exc
        try:
            return TextAdvice.model_validate(parsed)
        except ValidationError as exc:
            raise TextAiSchemaError(self._validation_message(exc)) from exc

    @staticmethod
    def _validation_message(exc: ValidationError) -> str:
        problems: list[str] = []
        for error in exc.errors(include_url=False, include_input=False):
            field = ".".join(str(part) for part in error.get("loc", ())) or "根对象"
            error_type = error.get("type")
            if error_type == "missing":
                problems.append(f"缺少字段 {field}")
            elif error_type == "extra_forbidden":
                problems.append(f"存在未允许字段 {field}")
            elif error_type == "string_type":
                problems.append(f"字段 {field} 类型错误，应为字符串")
            elif error_type == "string_too_short":
                problems.append(f"字段 {field} 不能为空")
            else:
                problems.append(f"字段 {field} 校验失败（{error_type}）")
        return "DeepSeek JSON 结构不匹配：" + "；".join(problems[:5])

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 402:
            raise TextAiBalanceError("DeepSeek 账户余额不足，请充值后重试")
        if response.status_code == 429:
            raise TextAiRateLimitError("DeepSeek 请求过于频繁，请稍后重试")
        if response.status_code in (408, 504):
            raise TextAiTimeoutError("DeepSeek 请求超时，请稍后重试")
        if response.status_code in (401, 403):
            raise TextAiConfigurationError("DeepSeek 鉴权失败，请检查后端 API Key")
        raise TextAiError(f"DeepSeek 服务返回错误（HTTP {response.status_code}）")


class ExistingVelaPetTextProvider(TextProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, insight: ActivityInsight, pet_name: str) -> TextGeneration:
        if not self.settings.text_ai_device_token:
            raise TextAiConfigurationError("现有 VelaPet AI 服务 Token 未配置")
        body = {
            "device_id": "web-coach", "prompt_type": "task", "locale": "zh-CN", "max_chars": 100,
            "message": "根据活动汇总给出一条简短、非医疗的运动建议",
            "context": {**asdict(insight), "pet_name": pet_name},
        }
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.settings.text_ai_timeout_seconds) as client:
                response = client.post(
                    self.settings.text_ai_service_url.rstrip("/") + "/api/v1/chat", json=body,
                    headers={"X-VelaPet-Token": self.settings.text_ai_device_token},
                )
            response.raise_for_status()
            result = response.json()
            reply = result["reply"]
            if not isinstance(reply, str) or not reply.strip():
                raise TextAiResponseError("现有 AI 服务未返回有效建议")
        except httpx.TimeoutException as exc:
            raise TextAiTimeoutError("现有 AI 服务请求超时") from exc
        except httpx.HTTPError as exc:
            raise TextAiError("现有 AI 服务暂时不可用") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise TextAiResponseError("现有 AI 服务返回格式不合法") from exc
        duration_ms = round((time.perf_counter() - started) * 1000)
        return TextGeneration(
            advice=TextAdvice(
                today_summary=f"今天 {insight.today_steps:,} 步、活跃 {insight.today_active_minutes} 分钟。",
                today_advice=reply.strip(), reason=f"依据最近 {insight.days_with_data} 天已同步运动数据。",
                weekly_plan=f"目标保持在 {insight.safe_goal_min:,}–{insight.safe_goal_max:,} 步范围。",
                pet_encouragement=f"{pet_name}会陪你按自己的节奏继续前进！",
            ), provider="existing_velapet", model="existing-velapet-chat", duration_ms=duration_ms,
        )


def get_text_provider(settings: Settings) -> TextProvider:
    if settings.text_ai_provider == "mock":
        return MockTextProvider()
    if settings.text_ai_provider == "deepseek":
        return DeepSeekTextProvider(settings)
    if settings.text_ai_provider == "existing_velapet":
        return ExistingVelaPetTextProvider(settings)
    raise TextAiConfigurationError(f"不支持的文本 AI Provider：{settings.text_ai_provider}")
