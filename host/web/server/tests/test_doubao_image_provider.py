import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.services.image_provider import (
    DoubaoImageProvider,
    ImageAiBalanceError,
    ImageAiConfigurationError,
    ImageAiRateLimitError,
    ImageAiResponseError,
    ImageAiTimeoutError,
)
from app.services.image_storage import ImageStorageError, LocalImageStorage


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (128, 128), "#a99bfa").save(output, format="PNG")
    return output.getvalue()


def payload() -> dict:
    return {
        "species": "fox", "color": "lavender", "style": "celestial",
        "personality": "energetic", "name": "露米", "description": "尾巴有原创星光纹理",
    }


def settings(tmp_path=None, **overrides) -> Settings:
    values = {
        "image_ai_provider": "doubao",
        "image_ai_api_key": "unit-test-ark-key",
        "image_ai_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "image_ai_model": "doubao-seedream-5-5-261028",
        "image_ai_timeout_seconds": 1,
        "image_ai_size": "2K",
        "image_ai_output_format": "png",
        "image_ai_background": "auto",
        "image_ai_response_format": "b64_json",
        "image_ai_watermark": False,
        "image_storage_dir": str(tmp_path) if tmp_path else "./test-images",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def valid_response(**item_overrides) -> dict:
    item = {
        "b64_json": base64.b64encode(png_bytes()).decode("ascii"),
        "size": "2048x2048",
        "output_format": "png",
        "background": "opaque",
    }
    item.update(item_overrides)
    return {
        "model": "doubao-seedream-5-5-261028",
        "data": [item],
        "usage": {"input_tokens": 12, "output_tokens": 34, "total_tokens": 46},
    }


def test_doubao_request_contract_and_base64_decode():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        assert request.headers["Authorization"] == "Bearer unit-test-ark-key"
        body = json.loads(request.content)
        assert body == {
            "model": "doubao-seedream-5-5-261028",
            "prompt": body["prompt"],
            "size": "2K",
            "response_format": "b64_json",
            "watermark": False,
            "output_format": "png",
            "background": "auto",
        }
        assert "original VelaPet" in body["prompt"]
        assert "quality" not in body and "n" not in body and "safety_identifier" not in body
        return httpx.Response(200, json=valid_response())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = DoubaoImageProvider(settings(), client).generate(payload(), "ignored-user-hash")
    assert result.image_bytes == png_bytes()
    assert result.mime_type == "image/png"
    assert result.model == "doubao-seedream-5-5-261028"
    assert result.total_tokens == 46


@pytest.mark.parametrize("field", ["image_ai_api_key", "image_ai_model"])
def test_doubao_requires_key_and_explicit_model(field):
    with pytest.raises(ImageAiConfigurationError):
        DoubaoImageProvider(settings(**{field: ""})).generate(payload())


@pytest.mark.parametrize("status", [401, 403])
def test_doubao_auth_errors_are_configuration_errors(status):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"error": {}})))
    with pytest.raises(ImageAiConfigurationError):
        DoubaoImageProvider(settings(), client).generate(payload())


@pytest.mark.parametrize("code", [
    "ModelNotOpen",
    "InvalidEndpointOrModel.NotFound",
    "InvalidEndpointOrModel.ModelIDAccessDisabled",
])
def test_doubao_404_exposes_safe_structured_error(code):
    response = {
        "error": {
            "code": code,
            "message": "The configured model is unavailable for this account.",
        }
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404, json=response)))
    with pytest.raises(ImageAiConfigurationError) as error:
        DoubaoImageProvider(settings(), client).generate(payload())
    rendered = str(error.value)
    assert "HTTP 404" in rendered
    assert code in rendered
    assert "The configured model is unavailable for this account." in rendered


def test_doubao_404_redacts_credentials_and_control_characters():
    response = {
        "error": {
            "code": "InvalidEndpointOrModel.NotFound",
            "message": (
                "authorization: Bearer exposed-token\r\n"
                "api_key=unit-test-ark-key model cannot be found"
            ),
        }
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404, json=response)))
    with pytest.raises(ImageAiConfigurationError) as error:
        DoubaoImageProvider(settings(), client).generate(payload())
    rendered = str(error.value)
    assert "exposed-token" not in rendered
    assert "unit-test-ark-key" not in rendered
    assert "[REDACTED]" in rendered
    assert "\r" not in rendered and "\n" not in rendered


def test_doubao_rate_limit_is_retryable():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(429, json={"error": {"code": "RateLimitExceeded"}})
    ))
    with pytest.raises(ImageAiRateLimitError) as error:
        DoubaoImageProvider(settings(), client).generate(payload())
    assert error.value.retryable is True


def test_doubao_balance_error_is_distinct_even_when_http_429():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(429, json={"error": {"code": "AccountOverdue"}})
    ))
    with pytest.raises(ImageAiBalanceError):
        DoubaoImageProvider(settings(), client).generate(payload())


def test_doubao_timeout_is_not_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ImageAiTimeoutError) as error:
        DoubaoImageProvider(settings(), client).generate(payload())
    assert error.value.retryable is False


@pytest.mark.parametrize("response", [
    {},
    {"data": []},
    {"data": [{"b64_json": "not base64!", "output_format": "png"}]},
    {"data": [{"url": "https://example.volces.com/temporary.png"}]},
])
def test_doubao_rejects_invalid_or_url_response(response):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    with pytest.raises(ImageAiResponseError):
        DoubaoImageProvider(settings(), client).generate(payload())


def test_doubao_rejects_response_format_mismatch():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=valid_response(output_format="jpeg"))
    ))
    with pytest.raises(ImageAiResponseError, match="格式"):
        DoubaoImageProvider(settings(), client).generate(payload())


@pytest.mark.parametrize("overrides", [
    {"image_ai_model": "unknown-model"},
    {"image_ai_model": "doubao-seedream-4-5-251128", "image_ai_output_format": "png"},
    {"image_ai_model": "doubao-seedream-5-0-lite-260128", "image_ai_background": "transparent"},
    {"image_ai_model": "doubao-seedream-5-5-261028", "image_ai_output_format": "jpeg", "image_ai_background": "transparent"},
    {"image_ai_size": "9K"},
    {"image_ai_response_format": "url"},
])
def test_doubao_rejects_unsupported_model_parameters(overrides):
    with pytest.raises(ImageAiConfigurationError):
        DoubaoImageProvider(settings(**overrides)).validate_configuration()


@pytest.mark.parametrize(("model", "size", "output_format"), [
    ("doubao-seedream-5-0-lite-260128", "4096x4096", "png"),
    ("doubao-seedream-4-0-250828", "1024x1024", "jpeg"),
    ("doubao-seedream-3-0-t2i", "512x512", "jpeg"),
])
def test_doubao_accepts_documented_explicit_size_ranges(model, size, output_format):
    DoubaoImageProvider(settings(
        image_ai_model=model, image_ai_size=size, image_ai_output_format=output_format,
    )).validate_configuration()


def test_doubao_fixed_jpeg_model_omits_unsupported_fields():
    jpeg_output = io.BytesIO()
    Image.new("RGB", (128, 128), "#71d7c2").save(jpeg_output, format="JPEG")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "output_format" not in body
        assert "background" not in body
        return httpx.Response(200, json={
            "model": "doubao-seedream-4-5-251128",
            "data": [{"b64_json": base64.b64encode(jpeg_output.getvalue()).decode("ascii")}],
        })

    config = settings(
        image_ai_model="doubao-seedream-4-5-251128", image_ai_output_format="jpeg",
        image_ai_background="auto", image_ai_size="2K",
    )
    result = DoubaoImageProvider(config, httpx.Client(transport=httpx.MockTransport(handler))).generate(payload())
    assert result.mime_type == "image/jpeg"


def test_doubao_generated_bytes_still_pass_private_storage_validation(tmp_path):
    storage = LocalImageStorage(settings(tmp_path))
    stored = storage.save("doubao-asset", png_bytes(), "png")
    assert stored.mime_type == "image/png"
    with pytest.raises(ImageStorageError):
        storage.save("spoofed", b"not a real png", "png")
