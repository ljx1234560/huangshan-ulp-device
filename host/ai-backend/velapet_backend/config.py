from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _env_tokens(name: str) -> frozenset[str]:
    return frozenset(
        token.strip() for token in os.getenv(name, "").split(",") if token.strip()
    )


@dataclass(frozen=True, slots=True)
class Settings:
    app_version: str = "0.2.0"
    host: str = "127.0.0.1"
    port: int = 8000
    data_root: Path = field(default_factory=lambda: Path("runtime-data"))
    device_tokens: frozenset[str] = field(default_factory=frozenset)
    chat_rate_limit_per_minute: int = 20
    chat_provider: str = "mimo"

    mimo_api_key: str = ""
    mimo_api_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_chat_model: str = "mimo-v2.6-flash"
    mimo_timeout_seconds: float = 30.0

    deepseek_api_key: str = ""
    deepseek_api_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("VELAPET_HOST", "127.0.0.1").strip(),
            port=_env_int("VELAPET_PORT", 8000),
            data_root=Path(os.getenv("VELAPET_DATA_ROOT", "runtime-data")),
            device_tokens=_env_tokens("VELAPET_DEVICE_TOKENS"),
            chat_rate_limit_per_minute=_env_int(
                "VELAPET_CHAT_RATE_LIMIT_PER_MINUTE", 20
            ),
            chat_provider=os.getenv("VELAPET_CHAT_PROVIDER", "mimo").strip().lower(),
            mimo_api_key=os.getenv("MIMO_API_KEY", "").strip(),
            mimo_api_base_url=os.getenv(
                "MIMO_API_BASE_URL", "https://api.xiaomimimo.com/v1"
            ).rstrip("/"),
            mimo_chat_model=os.getenv(
                "MIMO_CHAT_MODEL", "mimo-v2.6-flash"
            ).strip(),
            mimo_timeout_seconds=_env_float("MIMO_TIMEOUT_SECONDS", 30.0),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_api_base_url=os.getenv(
                "DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/"),
            deepseek_chat_model=os.getenv(
                "DEEPSEEK_CHAT_MODEL", "deepseek-flash"
            ).strip(),
            deepseek_timeout_seconds=_env_float("DEEPSEEK_TIMEOUT_SECONDS", 30.0),
        )

    @property
    def auth_required(self) -> bool:
        return bool(self.device_tokens)

    def validate_bind(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("VELAPET_PORT must be between 1 and 65535")
        if self.chat_rate_limit_per_minute < 1:
            raise ValueError("VELAPET_CHAT_RATE_LIMIT_PER_MINUTE must be positive")
        if self.chat_provider not in {"mimo", "deepseek"}:
            raise ValueError("VELAPET_CHAT_PROVIDER must be mimo or deepseek")
        if self.mimo_timeout_seconds <= 0:
            raise ValueError("MIMO_TIMEOUT_SECONDS must be positive")
        if self.deepseek_timeout_seconds <= 0:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be positive")

        try:
            is_loopback = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            is_loopback = self.host.lower() == "localhost"
        if not is_loopback and not self.auth_required:
            raise ValueError(
                "VELAPET_DEVICE_TOKENS is required for a non-loopback bind"
            )
