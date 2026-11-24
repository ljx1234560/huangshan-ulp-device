import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

test_db = Path(tempfile.gettempdir()) / "velapet_server_tests.sqlite3"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["VELAPET_DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"
os.environ["VELAPET_SEED_DEMO"] = "false"
os.environ["VELAPET_COOKIE_SECURE"] = "false"
os.environ["VELAPET_IMAGE_STORAGE_DIR"] = str(Path(tempfile.gettempdir()) / "velapet_test_images")
os.environ["VELAPET_TEXT_AI_PROVIDER"] = "mock"
os.environ["VELAPET_TEXT_AI_API_KEY"] = ""
os.environ["VELAPET_TEXT_AI_MODEL"] = ""
os.environ["VELAPET_IMAGE_AI_PROVIDER"] = "mock"
os.environ["VELAPET_IMAGE_AI_API_KEY"] = ""
os.environ["VELAPET_IMAGE_AI_MODEL"] = ""

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
    yield


@pytest.fixture
def client():
    yield SyncASGIClient(app)


class SyncASGIClient:
    """Small synchronous wrapper around HTTPX's ASGI transport.

    Starlette's legacy TestClient currently deadlocks on the Python 3.14 host
    used by CI, while the production ASGI path itself is unaffected.
    """

    def __init__(self, asgi_app: Any):
        self.app = asgi_app
        self.cookies = httpx.Cookies()

    def request(self, method: str, url: str, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                cookies=self.cookies,
            ) as async_client:
                response = await async_client.request(method, url, **kwargs)
                self.cookies.update(async_client.cookies)
                return response

        return asyncio.run(send())

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)


def login(client: SyncASGIClient, email: str, password: str = "VelaPetDemo123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def csrf_headers(client: SyncASGIClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("velapet_csrf")}
