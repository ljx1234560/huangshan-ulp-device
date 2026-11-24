from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..deps import get_current_user, require_csrf
from ..models import PetAsset, PetGenerationJob, PetSnapshot, User, uuid4
from ..schemas import FavoriteAssetIn, PetGenerationIn

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
    }


def complete_mock_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(PetGenerationJob, job_id)
        if not job or job.status == "succeeded":
            return
        asset = PetAsset(
            owner_id=job.user_id,
            generation_job_id=job.id,
            image_url="/pets/lumi.png",
            name=job.input_json["name"],
            favorite=False,
            source="mock_asset",
            is_demo=job.is_demo,
        )
        db.add(asset)
        db.flush()
        job.asset_id = asset.id
        job.status = "succeeded"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


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
):
    settings = get_settings()
    job = PetGenerationJob(
        user_id=user.id,
        pet_instance_id=uuid4(),
        status="queued",
        progress=8,
        input_json=payload.model_dump(by_alias=True),
        provider=settings.ai_provider,
        source="mock_asset" if settings.ai_provider == "mock" else "ai_generated",
        is_demo=user.is_demo,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if settings.ai_provider == "mock":
        background_tasks.add_task(complete_mock_job, job.id)
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
