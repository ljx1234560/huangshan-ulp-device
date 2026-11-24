from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import activity, admin, ai, auth, devices, pets
from .services.seed import seed_demo_data
from .services.image_jobs import recover_stale_image_jobs


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    if settings.seed_demo:
        with SessionLocal() as db:
            seed_demo_data(db)
    recover_stale_image_jobs(settings)
    yield


settings = get_settings()
app = FastAPI(title="VelaPet API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-VelaPet-Device-Token"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        "textAiProvider": settings.text_ai_provider,
        "imageAiProvider": settings.image_ai_provider,
        "demoSeed": settings.seed_demo,
    }


app.include_router(auth.router)
app.include_router(activity.router)
app.include_router(devices.router)
app.include_router(pets.router)
app.include_router(ai.router)
app.include_router(admin.router)
