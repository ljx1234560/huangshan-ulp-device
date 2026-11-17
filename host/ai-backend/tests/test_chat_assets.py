import asyncio
import base64
import hashlib
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from velapet_backend.config import Settings
from velapet_backend.main import create_app
from velapet_backend.models import ChatRequest
from velapet_backend.provider import ChatProviderClient
from velapet_backend.store import Store
from velapet_backend.images import seedream_image
from velapet_backend.image_provider import SeedreamProviderClient


def picture(color="orange"):
    out = io.BytesIO()
    Image.new("RGB", (320, 180), color).save(out, format="PNG")
    return out.getvalue()


def make_client(tmp_path, **kwargs):
    return TestClient(create_app(Settings(data_root=tmp_path, **kwargs)))


def submit(client, raw=None, key="request-1", device="test", headers=None):
    return client.post("/api/v1/pet-assets/jobs", files={"file": ("pet.png", raw or picture(), "image/png")},
                       data={"device_id": device, "idempotency_key": key}, headers=headers)


def test_chat_history_is_bounded_persistent_and_deletable(tmp_path):
    with make_client(tmp_path) as client:
        body = {"device_id": "test", "prompt_type": "custom", "message": "我叫小明", "context": {}}
        first = client.post("/api/v1/chat", json=body).json()
        cid = first["conversation_id"]
        body["conversation_id"] = cid
        for i in range(8):
            body["message"] = str(i)
            assert client.post("/api/v1/chat", json=body).status_code == 200
        with client.app.state.settings.data_root.joinpath("velapet.sqlite3").open("rb") as stream:
            assert stream.read(6) == b"SQLite"
        store = Store(tmp_path)
        from velapet_backend.store import owner_key
        history = store.history(cid, owner_key(None, "test"), "nova")
        assert len(history) == 12
        assert history[-2]["content"] == "7"
        body["device_id"] = "other"
        assert client.post("/api/v1/chat", json=body).status_code == 404
        body["device_id"] = "test"
        body["persona_id"] = "spark"
        assert client.post("/api/v1/chat", json=body).status_code == 404
        assert client.delete(f"/api/v1/conversations/{cid}", params={"device_id": "test"}).status_code == 200
        assert store.history(cid, owner_key(None, "test"), "nova") == []


def test_provider_receives_persona_and_history():
    def handler(request):
        payload = json.loads(request.content)
        assert "活泼" in payload["messages"][0]["content"]
        assert "小白" in payload["messages"][0]["content"]
        assert payload["messages"][1] == {"role": "user", "content": "我叫小明"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"reply":"记住啦，小明！","intent":"chat","emotion":"cheerful"}'}}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            provider = ChatProviderClient(Settings(chat_provider="deepseek", deepseek_api_key="test-only"), http)
            result = await provider.generate_reply(
                ChatRequest(device_id="test", persona_id="spark", context={"pet_name": "小白"}),
                [{"role": "user", "content": "我叫小明"}])
            assert "小明" in result.reply
    asyncio.run(run())


def test_demo_job_assets_idempotency_and_download_integrity(tmp_path):
    with make_client(tmp_path) as client:
        response = submit(client)
        assert response.status_code == 202
        jid = response.json()["job_id"]
        route = f"/api/v1/pet-assets/jobs/{jid}"
        job = client.get(route, params={"device_id": "test"}).json()
        assert job["status"] == "succeeded"
        assert job["provider"] == "demo"
        assert "not AI" in job["notice"]
        assert len(job["artifacts"]) == 3
        assert submit(client).json()["job_id"] == jid
        assert submit(client, picture("blue")).status_code == 409
        for asset in job["artifacts"]:
            raw = client.get(asset["download_url"], params={"device_id": "test"}).content
            assert len(raw) == asset["byte_size"]
            assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
            assert Image.open(io.BytesIO(raw)).size == (asset["width"], asset["height"])
        assert client.get(route, params={"device_id": "other"}).status_code == 404
        assert client.get(f"/api/v1/pet-assets/{jid}/files/source.png", params={"device_id": "test"}).status_code == 404


def test_token_scope_and_upload_validation(tmp_path):
    with make_client(tmp_path, device_tokens=frozenset({"alpha", "beta"})) as client:
        assert submit(client).status_code == 401
        alpha = {"X-VelaPet-Token": "alpha"}
        beta = {"X-VelaPet-Token": "beta"}
        jid = submit(client, headers=alpha).json()["job_id"]
        assert client.get(f"/api/v1/pet-assets/jobs/{jid}", params={"device_id": "test"}, headers=beta).status_code == 404
        assert submit(client, b"not an image", headers=alpha).status_code == 422
        assert submit(client, b"x" * (5 * 1024 * 1024 + 1), headers=alpha).status_code == 413


def test_missing_seedream_key_fails_without_fake_success(tmp_path):
    with make_client(tmp_path, image_provider="seedream", image_generation_enabled=True) as client:
        jid = submit(client).json()["job_id"]
        result = client.get(f"/api/v1/pet-assets/jobs/{jid}", params={"device_id": "test"}).json()
        assert result["status"] == "failed"
        assert result["artifacts"] == []


def test_restart_marks_inflight_jobs_failed(tmp_path):
    store = Store(tmp_path)
    store.create_job({"job_id": "test", "status": "processing"}, "owner", "key", "digest")
    restarted = Store(tmp_path)
    assert restarted.job("test", "owner")["error_code"] == "PROCESS_INTERRUPTED"


def test_seedream_payload_uses_reference_and_no_real_network(monkeypatch):
    real_client = httpx.Client
    def handler(request):
        payload = json.loads(request.content)
        assert request.url == "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        assert payload["image"].startswith("data:image/png;base64,")
        assert payload["response_format"] == "b64_json"
        assert payload["watermark"] is True
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(picture()).decode()}]})
    monkeypatch.setattr("velapet_backend.images.httpx.Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    image = seedream_image(Settings(ark_api_key="test-only", image_generation_enabled=True), picture(), "cartoon")
    assert image.size == (320, 180)
    image.close()


@pytest.mark.parametrize(("upstream_status", "expected_code"), [
    (400, "SEEDREAM_HTTP_400"),
    (403, "SEEDREAM_HTTP_403"),
    (200, "SEEDREAM_INVALID_IMAGE_RESPONSE"),
    (None, "SEEDREAM_TRANSPORT_ERROR"),
])
def test_seedream_job_preserves_safe_failure_diagnostic(tmp_path, monkeypatch, upstream_status, expected_code):
    real_client = httpx.Client
    attempts = []

    def handler(request):
        attempts.append(request.url.path)
        if upstream_status is None:
            raise httpx.ConnectError("upstream-only-detail", request=request)
        return httpx.Response(upstream_status, json={"error": "upstream-only-detail"})

    monkeypatch.setattr("velapet_backend.images.httpx.Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with make_client(tmp_path, image_provider="seedream", image_generation_enabled=True, ark_api_key="test-only") as client:
        jid = submit(client).json()["job_id"]
        response = client.get(f"/api/v1/pet-assets/jobs/{jid}", params={"device_id": "test"})
        assert response.json()["status"] == "failed"
        assert response.json()["error_code"] == expected_code
        assert response.json()["artifacts"] == []
        assert "upstream-only-detail" not in response.text
    assert attempts == ["/api/v3/images/generations"]

def test_ark_env_job_and_corrupt_download(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "fixture-key")
    monkeypatch.setenv("ARK_API_BASE_URL", "https://ark.example.test/custom/v3/")
    monkeypatch.setenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-pro-260628")
    monkeypatch.setenv("SEEDREAM_MODEL", "old-model")
    monkeypatch.setenv("VELAPET_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("VELAPET_DEVICE_TOKENS", "fixture-device")
    monkeypatch.delenv("VELAPET_IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("VELAPET_IMAGE_GENERATION_ENABLED", raising=False)
    cfg = Settings.from_env()
    calls = []

    def provider(request):
        calls.append(request.url.path)
        assert request.url == "https://ark.example.test/custom/v3/images/generations"
        assert request.headers["Authorization"] == "Bearer fixture-key"
        payload = json.loads(request.content)
        assert payload["model"] == "doubao-seedream-5-0-pro-260628"
        assert base64.b64decode(payload["image"].split(",", 1)[1]).startswith(b"\x89PNG")
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(picture()).decode()}]})

    adapter = SeedreamProviderClient(cfg, transport=httpx.MockTransport(provider))
    with TestClient(create_app(cfg, image_client=adapter)) as client:
        headers = {"X-VelaPet-Token": "fixture-device"}
        submitted = submit(client, headers=headers)
        assert submitted.status_code == 202
        jid = submitted.json()["job_id"]
        params = {"device_id": "test"}
        job = client.get(f"/api/v1/pet-assets/jobs/{jid}", params=params, headers=headers).json()
        assert job["status"] == "succeeded"
        assert {asset["kind"] for asset in job["artifacts"]} == {"avatar", "home", "skin"}
        for asset in job["artifacts"]:
            downloaded = client.get(asset["download_url"], params=params, headers=headers)
            assert downloaded.status_code == 200
            assert hashlib.sha256(downloaded.content).hexdigest() == asset["sha256"]
        artifact = job["artifacts"][0]
        path = tmp_path / "image-jobs" / jid / artifact["filename"]
        original = path.read_bytes()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        rejected = client.get(artifact["download_url"], params=params, headers=headers)
        assert rejected.status_code == 500
        assert rejected.json()["detail"]["error_code"] == "ASSET_INTEGRITY_FAILED"
    assert calls == ["/custom/v3/images/generations"]

    monkeypatch.setenv("VELAPET_IMAGE_GENERATION_ENABLED", "false")
    assert not Settings.from_env().image_generation_enabled
    monkeypatch.setenv("VELAPET_IMAGE_PROVIDER", "demo")
    assert Settings.from_env().image_provider == "demo"
