"""REST leg for a local Windows BLE relay. BLE framing stays in the board adapter."""
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from .models import ChatRequest, ChatResponse


ERROR_TIMEOUT = -1
ERROR_OFFLINE = -2
ERROR_INVALID = -3
MAX_RESPONSE_BYTES = 4096
UI_ID_BYTES = 48


def _bounded_id(value: str | None) -> str:
    return value if value and len(value.encode("utf-8")) < UI_ID_BYTES else ""


class ChatRelayClient:
    """Forward a decoded watch request and return an ID-correlated UI envelope."""

    def __init__(self, base_url: str, device_token: str = "", *, transport=None):
        url = urlsplit(base_url)
        if (url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment
                or (url.scheme == "http" and url.hostname not in {"127.0.0.1", "::1", "localhost"})):
            raise ValueError("relay requires HTTPS or HTTP loopback")
        self.endpoint = base_url.rstrip("/") + "/api/v1/chat"
        self.token = device_token
        self.transport = transport

    def exchange(self, ui_request_id: int, payload: dict) -> dict:
        if not isinstance(ui_request_id, int) or not 0 < ui_request_id <= 0xFFFFFFFF:
            raise ValueError("invalid UI request id")
        error = {"request_id": ui_request_id, "source": "error"}
        try:
            body = ChatRequest.model_validate(payload)
            headers = {"X-VelaPet-Token": self.token} if self.token else {}
            with httpx.Client(timeout=32, follow_redirects=False, transport=self.transport) as client:
                with client.stream("POST", self.endpoint, headers=headers,
                                   json=body.model_dump(mode="json")) as response:
                    if not response.is_success:
                        return {**error, "error_code": response.status_code}
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=MAX_RESPONSE_BYTES + 1):
                        if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ValueError("oversized response")
                        raw.extend(chunk)
            reply = ChatResponse.model_validate_json(bytes(raw))
            if not reply.reply.strip() or "\x00" in reply.reply:
                raise ValueError("missing reply")
            return {
                "request_id": ui_request_id,
                "source": "local_fallback" if reply.source == "local_fallback" else "cloud",
                "error_code": 0,
                "reply": reply.reply[:body.max_chars],
                "intent": reply.intent.value,
                "emotion": reply.emotion.value,
                "conversation_id": _bounded_id(reply.conversation_id),
                "persona_id": _bounded_id(reply.persona_id),
            }
        except httpx.TimeoutException:
            return {**error, "error_code": ERROR_TIMEOUT}
        except httpx.RequestError:
            return {**error, "error_code": ERROR_OFFLINE}
        except (ValidationError, ValueError):
            return {**error, "error_code": ERROR_INVALID}
