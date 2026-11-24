import hashlib
import json
from datetime import datetime, time, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..deps import get_current_user, require_csrf
from ..models import PetAsset, PetGenerationJob, PetSnapshot, User, uuid4
from ..schemas import FavoriteAssetIn, PetGenerationIn
from ..services.image_jobs import process_image_job
from ..services.image_provider import ImageAiError, get_image_provider
from ..services.image_storage import ImageStorageError, get_image_storage

router = APIRouter(prefix="/api/v1/pets", tags=["pets"])


def job_payload(job: PetGenerationJob, asset: PetAsset | None = None) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "createdAt": job.created_at.isoformat(),
        "imageUrl": asset.image_url if asset else None,
        "assetId": job.asset_id,
        "petId": job.pet_instance_id,
        "error": job.error,
        "input": job.input_json,
        "source": job.source,
        "provider": job.provider,
        "model": job.model,
        "attemptCount": job.attempt_count,
        "durationMs": job.duration_ms,
        "totalTokens": job.total_tokens,
        "favorite": asset.favorite if asset else False,
    }


def asset_payload(asset: PetAsset) -> dict:
    return {
        "id": asset.id,
        "ownerId": asset.owner_id,
        "generationJobId": asset.generation_job_id,
        "imageUrl": asset.image_url,
        "name": asset.name,
        "favorite": asset.favorite,
        "createdAt": asset.created_at.isoformat(),
        "source": asset.source,
        "model": asset.model,
        "width": asset.width,
        "height": asset.height,
    }


@router.get("/current")
def current_pet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    snapshot = db.scalar(
        select(PetSnapshot).where(PetSnapshot.user_id == user.id).order_by(PetSnapshot.version.desc())
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="尚未同步宠物状态快照")
    asset = db.get(PetAsset, user.current_pet_asset_id) if user.current_pet_asset_id else None
    if asset and asset.owner_id != user.id:
        asset = None
    return {
        "id": snapshot.pet_instance_id,
        "name": asset.name if asset else snapshot.name,
        "level": snapshot.level,
        "currentExp": snapshot.current_exp,
        "nextLevelExp": snapshot.next_level_exp,
        "title": snapshot.title,
        "imageUrl": asset.image_url if asset else "/pets/lumi.png",
        "skins": snapshot.skins,
        "tasks": snapshot.tasks,
        "totalSteps": snapshot.total_steps,
        "streakDays": snapshot.streak_days,
        "lastSyncedAt": snapshot.captured_at.isoformat(),
        "source": "mock" if snapshot.is_demo else "device_snapshot",
        "currentAssetId": asset.id if asset else None,
    }


@router.post("/generation-jobs", status_code=status.HTTP_202_ACCEPTED)
def create_generation_job(
    payload: PetGenerationIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        provider = get_image_provider(settings)
        provider.validate_configuration()
    except ImageAiError as exc:
        raise HTTPException(status_code=exc.http_status, detail=f"{exc}（{exc.code}）") from exc
    input_json = payload.model_dump(by_alias=True)
    fingerprint = hashlib.sha256(
        (user.id + json.dumps(input_json, ensure_ascii=False, sort_keys=True)).encode("utf-8")
    ).hexdigest()
    existing = db.scalar(select(PetGenerationJob).where(
        PetGenerationJob.user_id == user.id,
        PetGenerationJob.request_fingerprint == fingerprint,
        PetGenerationJob.status.in_(["queued", "running", "processing"]),
    ).order_by(PetGenerationJob.created_at.desc()))
    if existing:
        return job_payload(existing, db.get(PetAsset, existing.asset_id) if existing.asset_id else None)

    day_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    daily_count = db.scalar(select(func.count(PetGenerationJob.id)).where(
        PetGenerationJob.user_id == user.id,
        PetGenerationJob.created_at >= day_start,
    )) or 0
    if daily_count >= settings.image_daily_limit:
        raise HTTPException(status_code=429, detail=f"今日图片生成额度已用完（{settings.image_daily_limit} 次）")
    active_count = db.scalar(select(func.count(PetGenerationJob.id)).where(
        PetGenerationJob.user_id == user.id,
        PetGenerationJob.status.in_(["queued", "running", "processing"]),
    )) or 0
    if active_count >= settings.image_concurrent_limit:
        raise HTTPException(status_code=409, detail="已有图片生成任务正在进行，请完成后再试")
    job = PetGenerationJob(
        user_id=user.id,
        pet_instance_id=uuid4(),
        status="queued",
        progress=8,
        input_json=input_json,
        provider=settings.image_ai_provider,
        model="mock-image-v1" if settings.image_ai_provider == "mock" else settings.image_ai_model,
        source="mock_asset" if settings.image_ai_provider == "mock" else "ai_generated",
        request_fingerprint=fingerprint,
        is_demo=user.is_demo,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if settings.image_ai_provider == "mock":
        background_tasks.add_task(process_image_job, job.id, settings)
    return job_payload(job)


@router.get("/generation-jobs")
def list_generation_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = list(db.scalars(
        select(PetGenerationJob)
        .where(PetGenerationJob.user_id == user.id)
        .order_by(PetGenerationJob.created_at.desc())
        .limit(100)
    ))
    return [job_payload(job, db.get(PetAsset, job.asset_id) if job.asset_id else None) for job in jobs]


@router.get("/generation-jobs/{job_id}")
def get_generation_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(PetGenerationJob).where(
        PetGenerationJob.id == job_id,
        PetGenerationJob.user_id == user.id,
    ))
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return job_payload(job, db.get(PetAsset, job.asset_id) if job.asset_id else None)


@router.get("/assets/{asset_id}/content")
def asset_content(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    asset = db.scalar(select(PetAsset).where(PetAsset.id == asset_id, PetAsset.owner_id == user.id))
    if not asset or not asset.storage_key:
        raise HTTPException(status_code=404, detail="萌宠图片不存在或不属于当前用户")
    try:
        path = get_image_storage(settings).path_for(asset.storage_key)
    except ImageStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=asset.mime_type, filename=f"velapet-{asset.id}.{path.suffix.lstrip('.')}")


@router.post("/assets/{asset_id}/favorite")
def favorite_asset(
    asset_id: str,
    payload: FavoriteAssetIn,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    asset = db.scalar(select(PetAsset).where(PetAsset.id == asset_id, PetAsset.owner_id == user.id))
    if not asset:
        raise HTTPException(status_code=404, detail="萌宠资源不存在或不属于当前用户")
    asset.favorite = payload.favorite
    db.commit()
    return asset_payload(asset)


@router.post("/assets/{asset_id}/set-current")
def set_current_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    asset = db.scalar(select(PetAsset).where(PetAsset.id == asset_id, PetAsset.owner_id == user.id))
    if not asset:
        raise HTTPException(status_code=404, detail="萌宠资源不存在或不属于当前用户")
    user.current_pet_asset_id = asset.id
    db.commit()
    return {"ok": True}
