from __future__ import annotations

from collections import defaultdict, deque
import hmac
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from .config import Settings
from .provider import ChatProviderClient, ProviderError
from .models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    PromptType,
    ReplyIntent,
    RewardDecision,
)
from .prompts import local_reply


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int):
        self.limit = max(1, requests_per_minute)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] < now - 60.0:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


async def require_device_token(
    request: Request, x_velapet_token: str | None = Header(default=None)
) -> None:
    settings: Settings = request.app.state.settings
    if not settings.auth_required:
        return
    if not x_velapet_token:
        raise HTTPException(status_code=401, detail={"error_code": "AUTH_REQUIRED"})
    if not any(
        hmac.compare_digest(x_velapet_token, expected)
        for expected in settings.device_tokens
    ):
        raise HTTPException(status_code=403, detail={"error_code": "AUTH_INVALID"})


async def build_reply(client: ChatProviderClient, body: ChatRequest) -> ChatResponse:
    request_id = uuid4().hex
    reward = RewardDecision()
    if body.prompt_type == PromptType.CHEER:
        reward = RewardDecision(
            eligible=True,
            event="ai_encouragement",
            event_id=request_id,
        )

    if client.enabled:
        try:
            result = await client.generate_reply(body)
            if result.intent != ReplyIntent.ENCOURAGEMENT:
                reward = RewardDecision()
            return ChatResponse(
                request_id=request_id,
                reply=result.reply,
                intent=result.intent,
                emotion=result.emotion,
                source=client.provider,
                reward=reward,
            )
        except ProviderError as exc:
            reply, intent, emotion = local_reply(body)
            return ChatResponse(
                request_id=request_id,
                reply=reply,
                intent=intent,
                emotion=emotion,
                source="local_fallback",
                reward=reward,
                error_code=exc.code,
            )

    reply, intent, emotion = local_reply(body)
    return ChatResponse(
        request_id=request_id,
        reply=reply,
        intent=intent,
        emotion=emotion,
        source="local_fallback",
        reward=reward,
        error_code=client.not_configured_code,
    )


def create_app(
    settings: Settings | None = None,
    *,
    provider_client: ChatProviderClient | None = None,
) -> FastAPI:
    cfg = settings or Settings.from_env()
    cfg.validate_bind()
    cfg.data_root.mkdir(parents=True, exist_ok=True)
    client = provider_client or ChatProviderClient(cfg)
    limiter = SlidingWindowRateLimiter(cfg.chat_rate_limit_per_minute)

    app = FastAPI(title="VelaPet AI Backend", version=cfg.app_version)
    app.state.settings = cfg

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            version=cfg.app_version,
            chat_provider=client.provider if client.enabled else "local_fallback",
            chat_model=client.model if client.enabled else None,
            auth_required=cfg.auth_required,
        )

    @app.post(
        "/api/v1/chat",
        response_model=ChatResponse,
        dependencies=[Depends(require_device_token)],
    )
    async def chat(body: ChatRequest) -> ChatResponse:
        if not limiter.allow(body.device_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error_code": "RATE_LIMITED"},
            )
        return await build_reply(client, body)

    return app


app = create_app()
