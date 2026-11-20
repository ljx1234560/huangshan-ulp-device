from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VELAPET_",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"
    database_url: str = "sqlite:///./velapet.db"
    allowed_origins: str = "http://localhost:5173,http://localhost:5174"
    cookie_secure: bool = False
    access_session_minutes: int = 30
    refresh_session_days: int = 14
    ai_provider: str = "mock"
    ai_service_url: str = "http://127.0.0.1:8010"
    ai_device_token: str = ""
    seed_demo: bool = False

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
