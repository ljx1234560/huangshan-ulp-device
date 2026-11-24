from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..config import Settings, get_settings
from ..database import SessionLocal
from ..models import PetAsset, PetGenerationJob
from .image_provider import ImageAiError, ImageProvider, get_image_provider, safety_identifier
from .image_storage import ImageStorageError, StorageProvider, get_image_storage

logger = logging.getLogger(__name__)
ASSET_NAMESPACE = uuid.UUID("d29b5828-86db-4e93-b512-08e1f013a7fa")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def recover_stale_image_jobs(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.image_job_stale_minutes)
    recovered = 0
    with SessionLocal() as db:
        jobs = list(db.scalars(select(PetGenerationJob).where(
            PetGenerationJob.status.in_(["running", "processing"]),
        )))
        for job in jobs:
            if _utc(job.started_at) is None or _utc(job.started_at) < cutoff:
                job.status = "queued"
                job.progress = 8
                job.started_at = None
                job.error = "服务重启后已恢复到队列"
                job.error_code = "image_job_recovered"
                recovered += 1
        if recovered:
            db.commit()
    return recovered


def process_image_job(
    job_id: str,
    settings: Settings | None = None,
    provider: ImageProvider | None = None,
    storage: StorageProvider | None = None,
    claimed: bool = False,
) -> str:
    settings = settings or get_settings()
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        if not job or job.status in {"succeeded", "failed"}:
            return job.status if job else "missing"
        if job.status == "running" and not claimed:
            return "running"
        existing_asset = db.scalar(select(PetAsset).where(PetAsset.generation_job_id == job.id))
        if existing_asset:
            job.asset_id = existing_asset.id
            job.status = "succeeded"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return "succeeded"
        if not claimed:
            job.status = "running"
            job.progress = 20
            job.started_at = datetime.now(timezone.utc)
            job.attempt_count += 1
            job.error = None
            job.error_code = None
        user_id = job.user_id
        payload = dict(job.input_json)
        attempt_count = job.attempt_count
        db.commit()

    provider = provider or get_image_provider(settings)
    storage = storage or get_image_storage(settings)
    asset_id = str(uuid.uuid5(ASSET_NAMESPACE, job_id))
    try:
        result = provider.generate(payload, safety_identifier(user_id))
        stored = storage.save(asset_id, result.image_bytes, settings.image_ai_output_format)
    except (ImageAiError, ImageStorageError) as exc:
        retryable = isinstance(exc, ImageAiError) and exc.retryable
        with SessionLocal() as db:
            job = db.get(PetGenerationJob, job_id)
            if not job:
                return "missing"
            job.error = str(exc)[:1000]
            job.error_code = exc.code if isinstance(exc, ImageAiError) else "image_storage_error"
            if retryable and attempt_count < settings.image_job_max_attempts:
                job.status = "queued"
                job.progress = 8
                job.started_at = None
                outcome = "queued"
            else:
                job.status = "failed"
                job.progress = 100
                job.completed_at = datetime.now(timezone.utc)
                outcome = "failed"
            db.commit()
        logger.warning(
            "image_job_failed job_id=%s provider=%s error_code=%s attempt=%d retryable=%s outcome=%s",
            job_id, settings.image_ai_provider, job.error_code, attempt_count, retryable, outcome,
        )
        return outcome
    except Exception:
        logger.exception("image_job_unexpected_failure job_id=%s provider=%s", job_id, settings.image_ai_provider)
        with SessionLocal() as db:
            job = db.get(PetGenerationJob, job_id)
            if job:
                job.status = "failed"
                job.progress = 100
                job.error = "图片生成发生内部错误"
                job.error_code = "image_job_internal_error"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return "failed"

    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        if not job:
            return "missing"
        asset = PetAsset(
            id=asset_id,
            owner_id=job.user_id,
            generation_job_id=job.id,
            image_url=f"/api/v1/pets/assets/{asset_id}/content",
            storage_key=stored.storage_key,
            name=job.input_json["name"],
            sha256=stored.sha256,
            byte_size=stored.byte_size,
            mime_type=stored.mime_type,
            model=result.model,
            width=stored.width,
            height=stored.height,
            favorite=False,
            source=result.source,
            is_demo=job.is_demo,
        )
        db.add(asset)
        job.asset_id = asset.id
        job.status = "succeeded"
        job.progress = 100
        job.source = result.source
        job.model = result.model
        job.duration_ms = result.duration_ms
        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.total_tokens = result.total_tokens
        job.cost_microusd = result.cost_microusd
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    return "succeeded"


def process_next_image_job(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    with SessionLocal() as db:
        job = db.scalar(
            select(PetGenerationJob)
            .where(PetGenerationJob.status == "queued")
            .order_by(PetGenerationJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job:
            job.status = "running"
            job.progress = 20
            job.started_at = datetime.now(timezone.utc)
            job.attempt_count += 1
            job.error = None
            job.error_code = None
            job_id = job.id
            db.commit()
        else:
            job_id = None
    if not job_id:
        return None
    process_image_job(job_id, settings=settings, claimed=True)
    return job_id
