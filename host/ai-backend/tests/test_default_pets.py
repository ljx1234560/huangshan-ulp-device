import hashlib
import io

from fastapi.testclient import TestClient
from PIL import Image

from velapet_backend.config import Settings
from velapet_backend.main import create_app
from velapet_backend.default_pets import render_pet


def test_default_catalog_and_artifact_integrity(tmp_path):
    with TestClient(create_app(Settings(data_root=tmp_path))) as client:
        catalog = client.get("/api/v1/default-pets").json()
        assert catalog["default_pet_id"] == "nova-cat"
        assert len(catalog["pets"]) == 3
        for pet in catalog["pets"]:
            for artifact in pet["artifacts"]:
                response = client.get(artifact["download_url"])
                assert response.status_code == 200
                assert len(response.content) == artifact["byte_size"]
                assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
                with Image.open(io.BytesIO(response.content)) as image:
                    assert image.size == (artifact["width"], artifact["height"])
                    assert image.mode == "RGBA"
        assert client.get("/api/v1/default-pets/missing/home.png").status_code == 404


def test_appearance_persistence_and_token_isolation(tmp_path):
    cfg = Settings(data_root=tmp_path, device_tokens=frozenset({"a", "b"}))
    a, b = {"X-VelaPet-Token": "a"}, {"X-VelaPet-Token": "b"}
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/v1/default-pets").status_code == 401
        assert client.put("/api/v1/appearance", headers=a,
                          json={"device_id": "watch", "pet_id": "mint-rabbit"}).status_code == 200
        assert client.put("/api/v1/appearance", headers=a,
                          json={"device_id": "watch", "pet_id": "unknown"}).status_code == 422
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/v1/appearance", headers=a, params={"device_id": "watch"}).json()["pet_id"] == "mint-rabbit"
        assert client.get("/api/v1/appearance", headers=b, params={"device_id": "watch"}).json()["pet_id"] == "nova-cat"


def test_seedream_disabled_even_with_key(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No image provider request is allowed")
    monkeypatch.setattr("velapet_backend.images.seedream_image", forbidden)
    with TestClient(create_app(Settings(data_root=tmp_path, image_provider="seedream", ark_api_key="test-only"))) as client:
        assert client.get("/api/v1/image-capabilities").json()["generation_enabled"] is False
        response = client.post("/api/v1/pet-assets/jobs", data={"device_id": "watch", "idempotency_key": "x"},
                               files={"file": ("cat.png", render_pet("nova-cat", "home"), "image/png")})
        assert response.status_code == 503
        assert response.json()["detail"]["error_code"] == "IMAGE_GENERATION_DISABLED"
