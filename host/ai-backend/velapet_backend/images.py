"""Reference-image jobs. Demo mode resizes the upload; it is NOT AI generation."""
import base64
import hashlib
import io
import json
import os
import threading
import warnings
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .store import owner_key

MAX_UPLOAD = 5 * 1024 * 1024
MAX_OUTPUT = 16 * 1024 * 1024
SIZES = {"avatar": (128, 128), "home": (240, 240), "skin": (160, 160)}
STYLES = {
    "cartoon": "Q版卡通表宠，保留参考宠物的毛色、耳形和标志特征，单一角色全身居中，浅色纯背景，无文字",
    "pixel": "像素游戏表宠，保留参考宠物特征，全身居中，清晰轮廓，浅色纯背景，无文字",
}


def decode_image(raw: bytes) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("IMAGE_TOO_LARGE")
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("IMAGE_FORMAT_UNSUPPORTED")
            return ImageOps.exif_transpose(image).convert("RGB")


def seedream_image(cfg, source: bytes, style: str) -> Image.Image:
    if not cfg.image_generation_enabled:
        raise ValueError("IMAGE_GENERATION_DISABLED")
    if not cfg.ark_api_key:
        raise ValueError("SEEDREAM_NOT_CONFIGURED")
    payload = {
        "model": cfg.seedream_model, "prompt": STYLES[style],
        "image": "data:image/png;base64," + base64.b64encode(source).decode(),
        "size": "1K", "response_format": "b64_json", "watermark": True,
    }
    # No automatic retries: generation may be billable despite a timeout.
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        with client.stream("POST", "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                           headers={"Authorization": "Bearer " + cfg.ark_api_key}, json=payload) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_OUTPUT * 2:
                    raise ValueError("PROVIDER_RESPONSE_TOO_LARGE")
        body = json.loads(raw)
    item = body["data"][0]
    # Request Base64 to avoid retrieving arbitrary provider-controlled URLs.
    result = base64.b64decode(item["b64_json"], validate=True)
    if len(result) > MAX_OUTPUT:
        raise ValueError("PROVIDER_IMAGE_TOO_LARGE")
    return decode_image(result)


def image_router(cfg, store, auth):
    router = APIRouter(dependencies=[Depends(auth)])
    slots = threading.BoundedSemaphore(2)
    root = cfg.data_root / "image-jobs"
    root.mkdir(exist_ok=True)

    @router.get("/api/v1/image-capabilities")
    def capabilities():
        return {"provider": cfg.image_provider,
                "generation_enabled": cfg.image_provider == "demo" or cfg.image_generation_enabled,
                "paid_generation": cfg.image_provider == "seedream",
                "styles": list(STYLES), "max_upload_bytes": MAX_UPLOAD}

    def run_job(job, image):
        try:
            job["status"] = "processing"
            store.update_job(job)
            folder = root / job["job_id"]
            if cfg.image_provider == "seedream":
                source = io.BytesIO()
                image.save(source, format="PNG")
                generated = seedream_image(cfg, source.getvalue(), job["style"])
                image.close()
                image = generated
            artifacts = []
            for kind, dimensions in SIZES.items():
                output = ImageOps.pad(image, dimensions, color=(245, 245, 250))
                filename = kind + ".png"
                path = folder / filename
                with (folder / (filename + ".part")).open("wb") as stream:
                    output.save(stream, format="PNG")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(folder / (filename + ".part"), path)
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                artifacts.append({"kind": kind, "version": digest[:12], "sha256": digest,
                                  "byte_size": len(raw), "width": dimensions[0], "height": dimensions[1],
                                  "mime_type": "image/png", "filename": filename,
                                  "download_url": f"/api/v1/pet-assets/{job['job_id']}/files/{filename}"})
            job.update(status="succeeded", artifacts=artifacts)
        except Exception as exc:
            # Neither provider bodies nor credentials enter public errors.
            code = "IMAGE_GENERATION_FAILED"
            if isinstance(exc, ValueError) and str(exc) == "SEEDREAM_NOT_CONFIGURED":
                code = "SEEDREAM_NOT_CONFIGURED"
            elif isinstance(exc, httpx.TimeoutException):
                code = "PROVIDER_TIMEOUT_RESULT_UNKNOWN"
            job.update(status="failed", error_code=code)
        finally:
            try:
                store.update_job(job)
            finally:
                image.close()
                slots.release()

    @router.post("/api/v1/pet-assets/jobs", status_code=202)
    async def submit(background: BackgroundTasks, file: UploadFile = File(...),
                     device_id: str = Form(..., pattern=r"^[A-Za-z0-9_.-]{1,64}$"),
                     style: str = Form("cartoon"),
                     idempotency_key: str = Form(..., min_length=1, max_length=64),
                     x_velapet_token: str | None = Header(None)):
        if cfg.image_provider == "seedream" and not cfg.image_generation_enabled:
            await file.close()
            raise HTTPException(503, detail={"error_code": "IMAGE_GENERATION_DISABLED"})
        if style not in STYLES:
            raise HTTPException(422, detail={"error_code": "STYLE_UNSUPPORTED"})
        raw = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, detail={"error_code": "UPLOAD_TOO_LARGE"})
        try:
            image = await run_in_threadpool(decode_image, raw)
        except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, detail={"error_code": "IMAGE_INVALID"})
        owner = owner_key(x_velapet_token, device_id)
        digest = hashlib.sha256(raw + style.encode()).hexdigest()
        job = {"job_id": uuid4().hex, "status": "queued", "style": style,
               "provider": cfg.image_provider, "artifacts": [], "error_code": None,
               "notice": "Demo: upload resized, not AI-generated" if cfg.image_provider == "demo" else "AI-generated image"}
        if not slots.acquire(blocking=False):
            image.close()
            raise HTTPException(429, detail={"error_code": "IMAGE_BUSY"})
        try:
            job, created = store.create_job(job, owner, idempotency_key, digest)
            if created:
                (root / job["job_id"]).mkdir()
                background.add_task(run_job, job, image)
            else:
                image.close()
                slots.release()
        except Exception as exc:
            image.close()
            slots.release()
            if isinstance(exc, ValueError):
                raise HTTPException(409, detail={"error_code": "IDEMPOTENCY_CONFLICT"})
            raise
        return job

    def owned_job(jid, device_id, token):
        job = store.job(jid, owner_key(token, device_id))
        if job is None:
            raise HTTPException(404, detail={"error_code": "JOB_NOT_FOUND"})
        return job

    @router.get("/api/v1/pet-assets/jobs/{jid}")
    def status(jid: str, device_id: str, x_velapet_token: str | None = Header(None)):
        return owned_job(jid, device_id, x_velapet_token)

    @router.get("/api/v1/pet-assets/{jid}/files/{filename}")
    def download(jid: str, filename: str, device_id: str, x_velapet_token: str | None = Header(None)):
        job = owned_job(jid, device_id, x_velapet_token)
        allowed = {asset["filename"] for asset in job["artifacts"]}
        if job["status"] != "succeeded" or filename not in allowed:
            raise HTTPException(404)
        return FileResponse(root / job["job_id"] / filename, media_type="image/png")

    return router
