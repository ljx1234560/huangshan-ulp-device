from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx

from .config import Settings
from .models import ChatRequest, ReplyEmotion, ReplyIntent
from .prompts import SYSTEM_PROMPT, build_user_prompt, sanitize_reply


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(slots=True)
class ProviderReply:
    reply: str
    intent: ReplyIntent
    emotion: ReplyEmotion


class MiMoClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self.settings.mimo_api_key)

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return ""
        if not isinstance(body, dict):
            return ""
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            return message if isinstance(message, str) else ""
        return ""

    @classmethod
    def _raise_for_status(cls, response: httpx.Response) -> None:
        status = response.status_code
        message = cls._error_message(response)
        if status < 400:
            return
        if status == 400 and "unsupported model" in message.lower():
            raise ProviderError("MIMO_MODEL_UNAVAILABLE", message)
        if status in {401, 403}:
            raise ProviderError("MIMO_AUTH_FAILED", "MiMo rejected the API key")
        if status == 402:
            raise ProviderError("MIMO_PAYMENT_REQUIRED", "MiMo account has no usable quota")
        if status == 429:
            raise ProviderError("MIMO_RATE_LIMITED", "MiMo rate limit exceeded", retryable=True)
        if status >= 500:
            raise ProviderError("MIMO_UPSTREAM_ERROR", "MiMo service error", retryable=True)
        raise ProviderError("MIMO_REQUEST_REJECTED", f"MiMo returned HTTP {status}")

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError("MIMO_NOT_CONFIGURED", "MIMO_API_KEY is not configured")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.settings.mimo_timeout_seconds,
            follow_redirects=False,
        )
        try:
            response = await client.post(
                self.settings.mimo_api_base_url + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + self.settings.mimo_api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ProviderError("MIMO_UNAVAILABLE", str(exc), retryable=True) from exc
        finally:
            if owns_client:
                await client.aclose()

        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("MIMO_INVALID_RESPONSE", "MiMo returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ProviderError("MIMO_INVALID_RESPONSE", "MiMo returned a non-object response")
        return data

    @staticmethod
    def _message_content(data: dict[str, Any]) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("MIMO_INVALID_RESPONSE", "MiMo response has no content") from exc
        if not isinstance(content, str):
            raise ProviderError("MIMO_INVALID_RESPONSE", "MiMo content is not text")
        return content

    @staticmethod
    def _parse_reply(raw: str, max_chars: int) -> ProviderReply:
        text = raw.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```")
            text = text.removesuffix("```").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start : end + 1])
                reply = payload["reply"]
                return ProviderReply(
                    sanitize_reply(reply, max_chars),
                    ReplyIntent(payload.get("intent", "chat")),
                    ReplyEmotion(payload.get("emotion", "cheerful")),
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise ProviderError("MIMO_INVALID_RESPONSE", "Invalid structured reply") from exc
        cleaned = sanitize_reply(text, max_chars)
        if not cleaned:
            raise ProviderError("MIMO_EMPTY_RESPONSE", "MiMo returned an empty reply")
        return ProviderReply(cleaned, ReplyIntent.CHAT, ReplyEmotion.CHEERFUL)

    async def generate_reply(self, request: ChatRequest) -> ProviderReply:
        data = await self._post(
            {
                "model": self.settings.mimo_chat_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(request)},
                ],
                "max_completion_tokens": 256,
                "stream": False,
                "thinking": {"type": "disabled"},
            }
        )
        return self._parse_reply(self._message_content(data), request.max_chars)


# Compatibility aliases for callers that imported the original MiMo-only module.
# New code imports these definitions from provider.py directly.
from .provider import ChatProviderClient as ChatProviderClient
from .provider import ProviderError as ProviderError
from .provider import ProviderReply as ProviderReply

MiMoClient = ChatProviderClient
