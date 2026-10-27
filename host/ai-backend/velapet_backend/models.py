from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: int = Field(default=0, ge=0, le=3)
    target: int = Field(default=0, ge=0, le=10_000_000)
    progress: int = Field(default=0, ge=0, le=10_000_000)
    status: int = Field(default=0, ge=0, le=3)


class PetContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pet_name: str = Field(default="NOVA", min_length=1, max_length=32)
    level: int = Field(default=1, ge=1, le=65_535)
    exp: int = Field(default=0, ge=0, le=2_000_000_000)
    exp_to_next: int = Field(default=100, ge=1, le=10_000_000)
    title: str = Field(default="egg_baby", max_length=32)
    current_skin: str = Field(default="default", max_length=24)
    unlocked_skins: list[str] = Field(default_factory=list, max_length=5)
    total_steps: int = Field(default=0, ge=0, le=9_000_000_000_000_000_000)
    today_steps: int | None = Field(default=None, ge=0, le=10_000_000)
    consecutive_days: int = Field(default=0, ge=0, le=1_000_000)
    tasks: list[TaskContext] = Field(default_factory=list, max_length=4)

    @field_validator("unlocked_skins")
    @classmethod
    def validate_skins(cls, values: list[str]) -> list[str]:
        return [value[:24] for value in values if value]


class PromptType(str, Enum):
    CHEER = "cheer"
    TASK = "task"
    LEVEL = "level"
    GREETING = "greeting"
    CUSTOM = "custom"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    prompt_type: PromptType = PromptType.CHEER
    message: str = Field(default="", max_length=240)
    locale: Literal["zh-CN", "en-US"] = "zh-CN"
    max_chars: int = Field(default=50, ge=16, le=80)
    context: PetContext


class ReplyIntent(str, Enum):
    GREETING = "greeting"
    REMINDER = "reminder"
    ENCOURAGEMENT = "encouragement"
    LEVEL_UP = "level_up"
    CHAT = "chat"


class ReplyEmotion(str, Enum):
    CHEERFUL = "cheerful"
    PROUD = "proud"
    GENTLE = "gentle"
    EXCITED = "excited"
    CALM = "calm"


class RewardDecision(BaseModel):
    eligible: bool = False
    event: Literal["ai_encouragement"] | None = None
    event_id: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    reply: str
    intent: ReplyIntent
    emotion: ReplyEmotion
    source: Literal["mimo", "deepseek", "local_fallback"]
    reward: RewardDecision = Field(default_factory=RewardDecision)
    error_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    chat_provider: Literal["mimo", "deepseek", "local_fallback"]
    chat_model: str | None
    auth_required: bool
