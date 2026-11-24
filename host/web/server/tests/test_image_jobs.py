import io
from datetime import datetime, timedelta, timezone

from PIL import Image
from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal
from app.models import PetGenerationJob, User
from app.services.image_jobs import process_image_job, recover_stale_image_jobs
import base64

import httpx

from app.services.image_provider import (
    DoubaoImageProvider,
    ImageAiRateLimitError,
    ImageGenerationResult,
    ImageProvider,
)
from app.services.image_storage import LocalImageStorage


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (128, 128), "#71d7c2").save(output, format="PNG")
    return output.getvalue()


def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        image_ai_provider="openai",
        image_ai_api_key="fake",
        image_ai_model="fake-image-model",
        image_ai_output_format="png",
        image_storage_dir=str(tmp_path),
        image_job_max_attempts=2,
        image_job_stale_minutes=1,
    )


def create_job(status="queued", started_at=None) -> str:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@velapet.cn"))
        job = PetGenerationJob(
            user_id=user.id, status=status, progress=20 if status == "running" else 8,
            input_json={"species": "fox", "color": "mint", "style": "forest", "personality": "gentle", "name": "芽芽", "description": ""},
            provider="openai", model="fake-image-model", source="ai_generated", started_at=started_at,
        )
        db.add(job)
        db.commit()
        return job.id


class RateLimitThenSuccess(ImageProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, payload, safety_identifier=""):
        self.calls += 1
        if self.calls == 1:
            raise ImageAiRateLimitError("fake rate limit")
        return ImageGenerationResult(
            image_bytes=png_bytes(), mime_type="image/png", source="ai_generated",
            model="fake-image-model", duration_ms=42, total_tokens=99,
        )


def test_retryable_job_failure_is_bounded_and_then_succeeds(tmp_path):
    job_id = create_job()
    provider = RateLimitThenSuccess()
    config = settings(tmp_path)
    storage = LocalImageStorage(config)
    assert process_image_job(job_id, config, provider, storage) == "queued"
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        assert job.status == "queued"
        assert job.attempt_count == 1
        assert job.error_code == "image_ai_rate_limited"
    assert process_image_job(job_id, config, provider, storage) == "succeeded"
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        assert job.status == "succeeded"
        assert job.attempt_count == 2
        assert job.asset_id and job.asset_id != job.id and job.asset_id != job.pet_instance_id
        assert job.total_tokens == 99


def test_stale_running_job_is_recovered_after_service_restart(tmp_path):
    job_id = create_job("running", datetime.now(timezone.utc) - timedelta(minutes=5))
    assert recover_stale_image_jobs(settings(tmp_path)) == 1
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        assert job.status == "queued"
        assert job.started_at is None
        assert job.error_code == "image_job_recovered"


def doubao_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        image_ai_provider="doubao",
        image_ai_api_key="fake-ark-key",
        image_ai_base_url="https://ark.cn-beijing.volces.com/api/v3",
        image_ai_model="doubao-seedream-5-5-261028",
        image_ai_size="2K",
        image_ai_output_format="png",
        image_ai_background="auto",
        image_ai_response_format="b64_json",
        image_storage_dir=str(tmp_path),
    )


def test_doubao_worker_persists_completed_job_and_asset(tmp_path):
    job_id = create_job()
    config = doubao_settings(tmp_path)
    response = {
        "model": config.image_ai_model,
        "data": [{
            "b64_json": base64.b64encode(png_bytes()).decode("ascii"),
            "output_format": "png",
        }],
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    provider = DoubaoImageProvider(config, client)
    assert process_image_job(job_id, config, provider, LocalImageStorage(config)) == "succeeded"
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        assert job.status == "succeeded"
        assert job.asset_id and job.asset_id != job.id
        assert job.model == config.image_ai_model


def test_doubao_worker_timeout_fails_without_automatic_retry(tmp_path):
    job_id = create_job()
    config = doubao_settings(tmp_path)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    provider = DoubaoImageProvider(config, httpx.Client(transport=httpx.MockTransport(timeout)))
    assert process_image_job(job_id, config, provider, LocalImageStorage(config)) == "failed"
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        assert job.status == "failed"
        assert job.attempt_count == 1
        assert job.error_code == "image_ai_timeout"
