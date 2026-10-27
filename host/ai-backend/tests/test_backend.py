import asyncio
import json

from fastapi.testclient import TestClient
import httpx
import pytest

from velapet_backend.config import Settings
from velapet_backend.main import build_reply, create_app
from velapet_backend.provider import ChatProviderClient
from velapet_backend.models import ChatRequest


def chat_body() -> dict:
    return {
        "device_id": "host-test",
        "prompt_type": "greeting",
        "context": {"pet_name": "NOVA"},
    }


def test_health_and_local_fallback(tmp_path):
    settings = Settings(data_root=tmp_path)
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "ok",
            "version": "0.2.0",
            "chat_provider": "local_fallback",
            "chat_model": None,
            "auth_required": False,
        }
        response = client.post("/api/v1/chat", json=chat_body())
        assert response.status_code == 200
        assert response.json()["source"] == "local_fallback"
        assert response.json()["error_code"] == "MIMO_NOT_CONFIGURED"


def test_device_authentication(tmp_path):
    settings = Settings(data_root=tmp_path, device_tokens=frozenset({"device-secret"}))
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/chat", json=chat_body()).status_code == 401
        assert client.post(
            "/api/v1/chat",
            json=chat_body(),
            headers={"X-VelaPet-Token": "wrong"},
        ).status_code == 403
        assert client.post(
            "/api/v1/chat",
            json=chat_body(),
            headers={"X-VelaPet-Token": "device-secret"},
        ).status_code == 200


def test_non_loopback_bind_requires_authentication():
    with pytest.raises(ValueError, match="VELAPET_DEVICE_TOKENS"):
        Settings(host="0.0.0.0").validate_bind()
    Settings(host="0.0.0.0", device_tokens=frozenset({"token"})).validate_bind()


def test_mimo_success_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only"
        assert body["model"] == "mimo-v2.6-flash"
        assert body["thinking"] == {"type": "disabled"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "reply": "你好呀，一起动起来！",
                                    "intent": "greeting",
                                    "emotion": "cheerful",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ChatProviderClient(Settings(mimo_api_key="test-only"), http)
            result = await client.generate_reply(ChatRequest(**chat_body()))
            assert result.reply == "你好呀，一起动起来！"

    asyncio.run(run())


def test_payment_error_degrades_to_local_reply():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "Payment required"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ChatProviderClient(Settings(mimo_api_key="test-only"), http)
            response = await build_reply(client, ChatRequest(**chat_body()))
            assert response.source == "local_fallback"
            assert response.error_code == "MIMO_PAYMENT_REQUIRED"
            assert response.reply

    asyncio.run(run())


def test_deepseek_success_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only"
        assert body["model"] == "deepseek-flash"
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 256
        assert body["response_format"] == {"type": "json_object"}
        assert "max_completion_tokens" not in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "reply": "你好，我是 DeepSeek 接入的 NOVA！",
                                    "intent": "greeting",
                                    "emotion": "cheerful",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    async def run():
        settings = Settings(
            chat_provider="deepseek",
            deepseek_api_key="test-only",
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ChatProviderClient(settings, http)
            response = await build_reply(client, ChatRequest(**chat_body()))
            assert response.source == "deepseek"
            assert response.error_code is None
            assert response.reply == "你好，我是 DeepSeek 接入的 NOVA！"

    asyncio.run(run())


def test_invalid_provider_is_rejected():
    with pytest.raises(ValueError, match="VELAPET_CHAT_PROVIDER"):
        Settings(chat_provider="unknown").validate_bind()
