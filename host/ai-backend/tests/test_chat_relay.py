import json

import httpx
import pytest

from velapet_backend.chat_relay import ChatRelayClient


@pytest.mark.parametrize(("source", "ui_source"), [("deepseek", "cloud"), ("local_fallback", "local_fallback")])
def test_chat_relay_keeps_id_and_fallback(source, ui_source):
    def handler(request):
        assert request.url == "http://127.0.0.1:8000/api/v1/chat"
        assert request.headers["X-VelaPet-Token"] == "test-device"
        body = json.loads(request.content)
        assert body["prompt_type"] == "task"
        assert body["context"]["level"] == 8
        return httpx.Response(200, json={
            "request_id": "server-id",
            "source": source,
            "error_code": "UPSTREAM_FAILURE" if source == "local_fallback" else None,
            "intent": "reminder",
            "emotion": "gentle",
            "conversation_id": "chat_1",
            "persona_id": "nova",
            "reply": "你好！",
        })
    relay = ChatRelayClient("http://127.0.0.1:8000", "test-device",
                            transport=httpx.MockTransport(handler))
    result = relay.exchange(42, {"device_id": "watch", "prompt_type": "task",
                                 "context": {"level": 8}})
    assert result["request_id"] == 42
    assert result["reply"] == "你好！"
    assert result["source"] == ui_source
    assert result["error_code"] == 0
    assert result["conversation_id"] == "chat_1"


@pytest.mark.parametrize(("response", "expected"), [(401, 401), (200, -3), (None, -1)])
def test_chat_relay_reports_terminal_error(response, expected):
    def handler(request):
        if response is None:
            raise httpx.ReadTimeout("simulated", request=request)
        return httpx.Response(response, content=b"{}")
    relay = ChatRelayClient("https://relay.example", transport=httpx.MockTransport(handler))
    assert relay.exchange(5, {"device_id": "watch", "context": {}}) == {
        "request_id": 5, "source": "error", "error_code": expected,
    }
