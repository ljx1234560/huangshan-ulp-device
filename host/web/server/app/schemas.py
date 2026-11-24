from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class RegisterRequest(CamelModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class DeviceBindRequest(CamelModel):
    serial_number: str = Field(min_length=3, max_length=80)
    claim_code: str = Field(min_length=4, max_length=100)


class ActivityRecordIn(CamelModel):
    record_id: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    local_date: date
    timezone_offset_minutes: int = Field(ge=-720, le=840)
    steps: int = Field(ge=0, le=200_000)
    active_minutes: int = Field(ge=0, le=1440)
    goal: int = Field(ge=1_000, le=100_000)
    source: Literal["hardware", "test_injected"] = "test_injected"
    rtc_trusted: bool = False

    @model_validator(mode="after")
    def validate_hardware_clock(self):
        if self.source == "hardware" and not self.rtc_trusted:
            raise ValueError("hardware 运动记录必须具有可信 RTC 时间")
        return self


class ActivityBatchIn(CamelModel):
    upload_id: str = Field(min_length=1, max_length=100)
    upload_offset: int | None = Field(default=None, ge=0)
    device_cursor: int | None = Field(default=None, ge=0)
    cursor: int | None = Field(default=None, ge=0, description="Deprecated alias for uploadOffset")
    final: bool = False
    firmware_version: str | None = Field(default=None, max_length=50)
    protocol_version: int | None = Field(default=None, ge=1, le=255)
    bridge_client_id: str | None = Field(default=None, max_length=100)
    records: list[ActivityRecordIn] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def normalize_legacy_cursor(self):
        if self.upload_offset is not None and self.cursor is not None and self.upload_offset != self.cursor:
            raise ValueError("uploadOffset 与旧 cursor 字段不能冲突")
        if self.upload_offset is None:
            self.upload_offset = self.cursor or 0
        return self


class BridgeSessionRequest(CamelModel):
    client_id: str = Field(min_length=1, max_length=100)


class BridgeStatusIn(CamelModel):
    state: Literal["authorized", "connecting", "connected", "syncing", "success", "failed", "disconnected"]
    connected: bool
    running: bool = True
    message: str = Field(default="", max_length=240)


class PetTaskIn(CamelModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=120)
    progress: int = Field(ge=0)
    target: int = Field(gt=0)
    reward_label: str = Field(default="设备规则奖励", max_length=120)
    status: Literal["active", "completed", "claimed"]


class PetSnapshotIn(CamelModel):
    snapshot_id: str = Field(min_length=1, max_length=100)
    version: int = Field(gt=0)
    pet_instance_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=80)
    level: int = Field(ge=1, le=10_000)
    current_exp: int = Field(ge=0)
    next_level_exp: int = Field(gt=0)
    title: str = Field(default="", max_length=100)
    skins: list[str] = Field(default_factory=list, max_length=100)
    tasks: list[PetTaskIn] = Field(default_factory=list, max_length=100)
    total_steps: int = Field(ge=0)
    streak_days: int = Field(ge=0)
    captured_at: datetime


class PetGenerationIn(CamelModel):
    species: Literal["fox", "cat", "rabbit"]
    color: str = Field(min_length=1, max_length=40)
    style: Literal["celestial", "forest", "pixel"]
    personality: Literal["energetic", "gentle", "curious"]
    name: str = Field(min_length=1, max_length=12)
    description: str = Field(default="", max_length=100)

    @field_validator("color", "name", "description", mode="before")
    @classmethod
    def validate_safe_text(cls, value):
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.strip().split())
        lowered = normalized.casefold()
        blocked = ("http://", "https://", "<script", "迪士尼", "米奇", "皮卡丘", "pokemon", "marvel")
        if any(token in lowered for token in blocked):
            raise ValueError("请使用原创描述，不要包含网址、脚本或受保护的知名角色/IP")
        if any(ord(char) < 32 for char in normalized):
            raise ValueError("文本不能包含控制字符")
        return normalized


class FavoriteAssetIn(CamelModel):
    favorite: bool = True


class EventIn(CamelModel):
    event_type: str = Field(min_length=1, max_length=50)
    occurred_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
