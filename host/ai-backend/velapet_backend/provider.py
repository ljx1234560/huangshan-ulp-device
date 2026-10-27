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


class ChatProviderClient:
    """Small adapter for the OpenAI-compatible MiMo and DeepSeek chat APIs."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client

    @property
    def provider(self) -> str:
        return self.settings.chat_provider

    @property
    def _prefix(self) -> str:
        return self.provider.upper()

    @property
    def api_key(self) -> str:
        if self.provider == "deepseek":
            return self.settings.deepseek_api_key
        return self.settings.mimo_api_key

    @property
    def api_base_url(self) -> str:
        if self.provider == "deepseek":
            return self.settings.deepseek_api_base_url
        return self.settings.mimo_api_base_url

    @property
    def model(self) -> str:
        if self.provider == "deepseek":
            return self.settings.deepseek_chat_model
        return self.settings.mimo_chat_model

    @property
    def timeout_seconds(self) -> float:
        if self.provider == "deepseek":
            return self.settings.deepseek_timeout_seconds
        return self.settings.mimo_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def not_configured_code(self) -> str:
        return f"{self._prefix}_NOT_CONFIGURED"

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

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        message = self._error_message(response)
        if status < 400:
            return
        if status == 400 and "model" in message.lower():
            raise ProviderError(f"{self._prefix}_MODEL_UNAVAILABLE", message)
        if status in {401, 403}:
            raise ProviderError(
                f"{self._prefix}_AUTH_FAILED",
                f"{self.provider} rejected the API key",
            )
        if status == 402:
            raise ProviderError(
                f"{self._prefix}_PAYMENT_REQUIRED",
                f"{self.provider} account has no usable quota",
            )
        if status == 429:
            raise ProviderError(
                f"{self._prefix}_RATE_LIMITED",
                f"{self.provider} rate limit exceeded",
                retryable=True,
            )
        if status >= 500:
            raise ProviderError(
                f"{self._prefix}_UPSTREAM_ERROR",
                f"{self.provider} service error",
                retryable=True,
            )
        raise ProviderError(
            f"{self._prefix}_REQUEST_REJECTED",
            f"{self.provider} returned HTTP {status}",
        )

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError(
                self.not_configured_code,
                f"{self._prefix}_API_KEY is not configured",
            )

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
        try:
            response = await client.post(
                self.api_base_url + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"{self._prefix}_UNAVAILABLE", str(exc), retryable=True
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        self._raise_for_status(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                f"{self._prefix}_INVALID_RESPONSE",
                f"{self.provider} returned invalid JSON",
            ) from exc
        if not isinstance(data, dict):
            raise ProviderError(
                f"{self._prefix}_INVALID_RESPONSE",
                f"{self.provider} returned a non-object response",
            )
        return data

    def _message_content(self, data: dict[str, Any]) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"{self._prefix}_INVALID_RESPONSE",
                f"{self.provider} response has no content",
            ) from exc
        if not isinstance(content, str):
            raise ProviderError(
                f"{self._prefix}_INVALID_RESPONSE",
                f"{self.provider} content is not text",
            )
        return content

    def _parse_reply(self, raw: str, max_chars: int) -> ProviderReply:
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
                raise ProviderError(
                    f"{self._prefix}_INVALID_RESPONSE", "Invalid structured reply"
                ) from exc
        cleaned = sanitize_reply(text, max_chars)
        if not cleaned:
            raise ProviderError(
                f"{self._prefix}_EMPTY_RESPONSE",
                f"{self.provider} returned an empty reply",
            )
        return ProviderReply(cleaned, ReplyIntent.CHAT, ReplyEmotion.CHEERFUL)

    def _request_payload(self, request: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        if self.provider == "deepseek":
            payload["max_tokens"] = 256
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["max_completion_tokens"] = 256
        return payload

    async def generate_reply(self, request: ChatRequest) -> ProviderReply:
        data = await self._post(self._request_payload(request))
        return self._parse_reply(self._message_content(data), request.max_chars)
