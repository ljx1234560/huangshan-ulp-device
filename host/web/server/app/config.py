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
    text_ai_provider: str = "mock"
    text_ai_api_key: str = ""
    text_ai_base_url: str = "https://api.deepseek.com"
    text_ai_model: str = ""
    text_ai_timeout_seconds: float = 20.0
    text_ai_service_url: str = "http://127.0.0.1:8010"
    text_ai_device_token: str = ""
    image_ai_provider: str = "mock"
    image_ai_api_key: str = ""
    image_ai_base_url: str = "https://api.openai.com/v1"
    image_ai_model: str = ""
    image_ai_timeout_seconds: float = 120.0
    image_ai_size: str = "1024x1024"
    image_ai_quality: str = "medium"
    image_ai_output_format: str = "png"
    image_ai_background: str = "auto"
    image_ai_response_format: str = "b64_json"
    image_ai_watermark: bool = False
    image_storage_dir: str = "./data/pet-images"
    image_max_bytes: int = 10 * 1024 * 1024
    image_daily_limit: int = 10
    image_concurrent_limit: int = 1
    image_job_max_attempts: int = 2
    image_job_stale_minutes: int = 10
    seed_demo: bool = False

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
