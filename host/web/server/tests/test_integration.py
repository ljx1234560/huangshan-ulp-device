from datetime import date, datetime, timedelta, timezone

from conftest import SyncASGIClient, csrf_headers, login


def activity_payload(upload_id: str = "upload-1", record_id: str = "record-1", device_cursor: int = 0):
    occurred_at = datetime.now(timezone.utc)
    local_date = (occurred_at + timedelta(minutes=480)).date()
    return {
        "uploadId": upload_id,
        "uploadOffset": 0,
        "deviceCursor": device_cursor,
        "final": True,
        "records": [{
            "recordId": record_id,
            "occurredAt": occurred_at.isoformat(),
            "localDate": local_date.isoformat(),
            "timezoneOffsetMinutes": 480,
            "steps": 1234,
            "activeMinutes": 12,
            "goal": 10000,
        }],
    }


def test_real_registration_session_restore_and_logout(client: SyncASGIClient):
    registered = client.post("/api/v1/auth/register", json={
        "name": "新用户",
        "email": "new@example.com",
        "password": "SecurePass123!",
    })
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "user"
    assert client.get("/api/v1/auth/me").status_code == 200
    logout = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_admin_rbac_blocks_normal_users(client: SyncASGIClient):
    login(client, "demo@velapet.cn")
    assert client.get("/api/v1/admin/metrics/overview").status_code == 403
    admin_client = SyncASGIClient(client.app)
    login(admin_client, "admin@velapet.cn", "VelaPetAdmin123!")
    response = admin_client.get("/api/v1/admin/metrics/overview")
    assert response.status_code == 200
    assert response.json()["dataSource"] == "demo"
    assert "activeDevices" in response.json()
    assert "firmwareVersions" in response.json()


def test_user_activity_isolation_and_date_filter(client: SyncASGIClient):
    login(client, "demo@velapet.cn")
    today = date.today().isoformat()
    own = client.get(f"/api/v1/activity/trends?range=week&start_date={today}&end_date={today}")
    assert own.status_code == 200
    assert len(own.json()["points"]) == 1
    other = SyncASGIClient(client.app)
    login(other, "second-demo@velapet.cn")
    isolated = other.get(f"/api/v1/activity/trends?range=week&start_date={today}&end_date={today}")
    assert isolated.status_code == 200
    assert isolated.json()["points"] == []


def test_device_binding_and_unbinding(client: SyncASGIClient):
    login(client, "second-demo@velapet.cn")
    bound = client.post("/api/v1/devices/bind", json={
        "serialNumber": "VP-52U-UNBOUND-DEMO",
        "claimCode": "spare-claim-code",
    }, headers=csrf_headers(client))
    assert bound.status_code == 200
    device_id = bound.json()["id"]
    assert len(client.get("/api/v1/devices").json()) == 1
    unbound = client.delete(f"/api/v1/devices/{device_id}/binding", headers=csrf_headers(client))
    assert unbound.status_code == 200
    assert client.get("/api/v1/devices").json() == []


def test_device_upload_is_idempotent_and_persistent(client: SyncASGIClient):
    payload = activity_payload()
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    first = client.post(url, json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["accepted"] == 1
    duplicate = client.post(url, json=payload, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["accepted"] == 0
    assert duplicate.json()["duplicates"] == 1
    conflicting = activity_payload()
    conflicting["records"][0]["steps"] += 1
    conflict = client.post(url, json=conflicting, headers=headers)
    assert conflict.status_code == 409
    assert "内容冲突" in conflict.json()["detail"]
    login(client, "demo@velapet.cn")
    uploaded_date = payload["records"][0]["localDate"]
    result = client.get(f"/api/v1/activity/daily?range=day&start_date={uploaded_date}&end_date={uploaded_date}")
    assert result.status_code == 200
    assert result.json()["todaySteps"] >= 1234


def test_hardware_upload_rejects_untrusted_rtc(client: SyncASGIClient):
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    payload = activity_payload("untrusted-rtc", "untrusted-hardware-record")
    payload["records"][0]["source"] = "hardware"
    rejected = client.post(url, json=payload, headers=headers)
    assert rejected.status_code == 422

    payload["records"][0]["rtcTrusted"] = True
    accepted = client.post(url, json=payload, headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] == 1


def test_device_upload_resumes_from_persisted_cursor(client):
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    first = activity_payload("resume-upload", "resume-record-1")
    first["final"] = False
    response = client.post(url, json=first, headers=headers)
    assert response.status_code == 200
    assert response.json()["nextUploadOffset"] == 1
    assert response.json()["ackCursor"] == 1

    out_of_order = activity_payload("resume-upload", "resume-record-2")
    out_of_order["uploadOffset"] = 2
    out_of_order["deviceCursor"] = 2
    assert client.post(url, json=out_of_order, headers=headers).status_code == 409

    resumed = activity_payload("resume-upload", "resume-record-2")
    resumed["uploadOffset"] = 1
    resumed["deviceCursor"] = 1
    completed = client.post(url, json=resumed, headers=headers)
    assert completed.status_code == 200
    assert completed.json()["accepted"] == 1
    assert completed.json()["nextUploadOffset"] == 2
    assert completed.json()["ackCursor"] == 2
    assert completed.json()["complete"] is True


def test_absolute_device_cursor_supports_multiple_sync_rounds_and_restart(client: SyncASGIClient):
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    first = activity_payload("round-1", "absolute-record-100", 100)
    first_result = client.post(url, json=first, headers=headers)
    assert first_result.status_code == 200
    assert first_result.json()["nextUploadOffset"] == 1
    assert first_result.json()["ackCursor"] == 101
    assert first_result.json()["persistedDeviceCursor"] == 101

    # A new ASGI client represents a restarted web/API process while using the
    # same persistent database.
    restarted = SyncASGIClient(client.app)
    second = activity_payload("round-2", "absolute-record-101", 101)
    second_result = restarted.post(url, json=second, headers=headers)
    assert second_result.status_code == 200
    assert second_result.json()["ackCursor"] == 102
    assert second_result.json()["persistedDeviceCursor"] == 102

    gap = activity_payload("round-gap", "absolute-record-104", 104)
    gap_result = restarted.post(url, json=gap, headers=headers)
    assert gap_result.status_code == 409
    assert "缺口" in gap_result.json()["detail"]


def test_ack_loss_with_new_upload_id_is_idempotent(client: SyncASGIClient):
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    first = activity_payload("ack-before-loss", "ack-loss-record", 300)
    assert client.post(url, json=first, headers=headers).json()["accepted"] == 1

    replay = {**first, "uploadId": "ack-after-reconnect"}
    repeated = client.post(url, json=replay, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["accepted"] == 0
    assert repeated.json()["duplicates"] == 1
    assert repeated.json()["ackCursor"] == 301
    assert repeated.json()["persistedDeviceCursor"] == 301


def test_upload_task_cannot_resume_across_device_rebinding(client: SyncASGIClient):
    url = "/api/v1/device-uploads/VP-52U-2400168/activity-batches"
    device_headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    original = activity_payload("old-owner-task", "old-owner-record", 50)
    assert client.post(url, json=original, headers=device_headers).status_code == 200

    login(client, "demo@velapet.cn")
    device_id = client.get("/api/v1/devices").json()[0]["id"]
    assert client.delete(f"/api/v1/devices/{device_id}/binding", headers=csrf_headers(client)).status_code == 200

    new_owner = SyncASGIClient(client.app)
    login(new_owner, "second-demo@velapet.cn")
    rebound = new_owner.post(
        "/api/v1/devices/bind",
        json={"serialNumber": "VP-52U-2400168", "claimCode": "demo-claim-code"},
        headers=csrf_headers(new_owner),
    )
    assert rebound.status_code == 200
    replay = client.post(url, json=original, headers=device_headers)
    assert replay.status_code == 409
    assert "不能跨绑定" in replay.json()["detail"]


def test_bridge_short_token_upload_status_and_provenance(client: SyncASGIClient):
    login(client, "demo@velapet.cn")
    session = client.post(
        "/api/v1/devices/serial/VP-52U-2400168/bridge-sessions",
        json={"clientId": "pytest-windows-bridge"},
        headers=csrf_headers(client),
    )
    assert session.status_code == 201
    token = session.json()["token"]
    bridge_headers = {"Authorization": f"Bearer {token}"}
    status_result = client.post(
        "/api/v1/device-uploads/VP-52U-2400168/bridge-status",
        json={"state": "syncing", "connected": True, "running": True, "message": "正在接收历史记录"},
        headers=bridge_headers,
    )
    assert status_result.status_code == 200
    assert status_result.json()["connected"] is True

    payload = activity_payload("bridge-upload", "hardware-record-1")
    payload.update({"firmwareVersion": "3.0.0-test", "protocolVersion": 1, "bridgeClientId": "pytest-windows-bridge"})
    payload["records"][0]["source"] = "hardware"
    payload["records"][0]["rtcTrusted"] = True
    upload = client.post(
        "/api/v1/device-uploads/VP-52U-2400168/activity-batches",
        json=payload,
        headers=bridge_headers,
    )
    assert upload.status_code == 200
    assert upload.json()["accepted"] == 1
    uploaded_date = payload["records"][0]["localDate"]
    daily = client.get(f"/api/v1/activity/daily?range=day&start_date={uploaded_date}&end_date={uploaded_date}").json()
    assert daily["dataSource"] in ("hardware", "mixed")
    assert "hardware" in {point["source"] for point in daily["points"]} or daily["dataSource"] == "mixed"
    devices = client.get("/api/v1/devices").json()
    assert devices[0]["firmwareVersion"] == "3.0.0-test"
    assert devices[0]["protocolVersion"] == 1
    assert devices[0]["bridge"]["state"] == "syncing"

    completed = client.post(
        "/api/v1/device-uploads/VP-52U-2400168/bridge-status",
        json={"state": "success", "connected": True, "running": True, "message": "同步成功"},
        headers=bridge_headers,
    )
    assert completed.status_code == 200
    disconnected = client.post(
        "/api/v1/device-uploads/VP-52U-2400168/bridge-status",
        json={"state": "disconnected", "connected": False, "running": False, "message": "桥接已退出"},
        headers=bridge_headers,
    )
    status = disconnected.json()
    assert status["running"] is False
    assert status["connected"] is False
    assert status["lastSyncStatus"] == "success"
    assert status["lastSyncAt"] is not None


def test_bridge_authorization_rejects_wrong_user_binding(client: SyncASGIClient):
    login(client, "second-demo@velapet.cn")
    denied = client.post(
        "/api/v1/devices/serial/VP-52U-2400168/bridge-sessions",
        json={"clientId": "wrong-owner"},
        headers=csrf_headers(client),
    )
    assert denied.status_code == 403


def test_pet_snapshot_rejects_stale_versions(client: SyncASGIClient):
    url = "/api/v1/device-uploads/VP-52U-2400168/pet-snapshots"
    headers = {"X-VelaPet-Device-Token": "demo-device-token"}
    body = {
        "snapshotId": "snapshot-v8",
        "version": 8,
        "petInstanceId": "pet_lumi_demo",
        "name": "露米",
        "level": 7,
        "currentExp": 720,
        "nextLevelExp": 1000,
        "title": "星光散步家",
        "skins": [],
        "tasks": [],
        "totalSteps": 500000,
        "streakDays": 7,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
    }
    assert client.post(url, json=body, headers=headers).status_code == 201
    body["snapshotId"] = "snapshot-stale"
    body["version"] = 7
    assert client.post(url, json=body, headers=headers).status_code == 409


def test_pet_job_asset_and_instance_ids_are_distinct_and_persist(client: SyncASGIClient):
    login(client, "demo@velapet.cn")
    created = client.post("/api/v1/pets/generation-jobs", json={
        "species": "fox",
        "color": "lavender",
        "style": "celestial",
        "personality": "energetic",
        "name": "新露米",
        "description": "测试资源持久化",
    }, headers=csrf_headers(client))
    assert created.status_code == 202
    job_id = created.json()["id"]
    stored = client.get(f"/api/v1/pets/generation-jobs/{job_id}")
    assert stored.status_code == 200
    result = stored.json()
    assert result["status"] == "succeeded"
    assert len({result["id"], result["assetId"], result["petId"]}) == 3
    asset_id = result["assetId"]
    assert client.post(f"/api/v1/pets/assets/{asset_id}/favorite", json={"favorite": True}, headers=csrf_headers(client)).status_code == 200
    assert client.post(f"/api/v1/pets/assets/{asset_id}/set-current", headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/v1/pets/current").json()["currentAssetId"] == asset_id
    assert any(item["id"] == job_id for item in client.get("/api/v1/pets/generation-jobs").json())
