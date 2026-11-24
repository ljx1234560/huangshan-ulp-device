import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.schemas import PetGenerationIn
from app.services.image_provider import (
    ImageAiBalanceError,
    ImageAiConfigurationError,
    ImageAiResponseError,
    ImageAiTimeoutError,
    MockImageProvider,
    OpenAIImageProvider,
)
from app.services.image_storage import ImageStorageError, LocalImageStorage


def png_bytes(size=(128, 128)) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", size, "#a99bfa").save(output, format="PNG")
    return output.getvalue()


def payload() -> dict:
    return {
        "species": "fox", "color": "lavender", "style": "celestial",
        "personality": "energetic", "name": "露米", "description": "尾巴有原创星光纹理",
    }


def settings(tmp_path=None, **overrides) -> Settings:
    values = {
        "image_ai_provider": "openai",
        "image_ai_api_key": "unit-test-image-key",
        "image_ai_base_url": "https://api.openai.com/v1",
        "image_ai_model": "account-enabled-image-model",
        "image_ai_timeout_seconds": 1,
        "image_ai_size": "1024x1024",
        "image_ai_quality": "medium",
        "image_ai_output_format": "png",
        "image_ai_background": "transparent",
        "image_storage_dir": str(tmp_path) if tmp_path else "./test-images",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def valid_response() -> dict:
    return {
        "data": [{"b64_json": base64.b64encode(png_bytes()).decode("ascii")}],
        "usage": {"input_tokens": 21, "output_tokens": 89, "total_tokens": 110},
    }


def test_mock_image_provider_returns_valid_png():
    result = MockImageProvider().generate(payload())
    assert result.source == "mock_asset"
    assert result.model == "mock-image-v1"
    with Image.open(io.BytesIO(result.image_bytes)) as image:
        assert image.format == "PNG"
        assert image.size == (512, 512)


def test_openai_image_request_contract_and_base64_decode():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/images/generations"
        assert request.headers["Authorization"] == "Bearer unit-test-image-key"
        body = json.loads(request.content)
        assert body["model"] == "account-enabled-image-model"
        assert body["size"] == "1024x1024"
        assert body["quality"] == "medium"
        assert body["output_format"] == "png"
        assert body["background"] == "transparent"
        assert body["response_format"] == "b64_json"
        assert body["safety_identifier"] == "safe-user-hash"
        assert "original VelaPet" in body["prompt"]
        assert "copyrighted franchise" in body["prompt"]
        return httpx.Response(200, json=valid_response())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = OpenAIImageProvider(settings(), client).generate(payload(), "safe-user-hash")
    assert result.image_bytes == png_bytes()
    assert result.total_tokens == 110
    assert result.source == "ai_generated"


@pytest.mark.parametrize("field", ["image_ai_api_key", "image_ai_model"])
def test_openai_image_requires_key_and_explicit_model(field):
    with pytest.raises(ImageAiConfigurationError):
        OpenAIImageProvider(settings(**{field: ""})).generate(payload())


def test_openai_image_timeout_is_not_automatically_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ImageAiTimeoutError) as error:
        OpenAIImageProvider(settings(), client).generate(payload())
    assert error.value.retryable is False


def test_openai_image_quota_error_is_distinct():
    response = {"error": {"code": "insufficient_quota"}}
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429, json=response)))
    with pytest.raises(ImageAiBalanceError):
        OpenAIImageProvider(settings(), client).generate(payload())


@pytest.mark.parametrize("response", [
    {},
    {"data": []},
    {"data": [{"b64_json": "not base64!"}]},
    {"data": [{"url": "https://untrusted.example/image.png"}]},
])
def test_openai_image_rejects_invalid_or_external_url_response(response):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    with pytest.raises(ImageAiResponseError):
        OpenAIImageProvider(settings(), client).generate(payload())


def test_local_storage_validates_format_size_and_safe_key(tmp_path):
    storage = LocalImageStorage(settings(tmp_path))
    stored = storage.save("safe-asset-id", png_bytes(), "png")
    assert stored.mime_type == "image/png"
    assert stored.width == 128
    assert storage.path_for(stored.storage_key).read_bytes() == png_bytes()
    with pytest.raises(ImageStorageError):
        storage.save("bad", b"not-an-image", "png")
    with pytest.raises(ImageStorageError):
        storage.save("tiny", png_bytes((8, 8)), "png")
    with pytest.raises(ImageStorageError):
        storage.path_for("../secret.png")


@pytest.mark.parametrize("description", ["https://example.com/pet.png", "做成皮卡丘", "<script>alert(1)</script>"])
def test_pet_description_rejects_urls_scripts_and_known_ip(description):
    with pytest.raises(ValueError):
        PetGenerationIn(**{**payload(), "description": description})
