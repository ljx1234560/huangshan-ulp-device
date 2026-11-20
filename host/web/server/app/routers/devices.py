import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_authenticated_device, get_current_user, get_upload_device, require_csrf
from ..models import (
    ActivityDaily,
    ActivityRecord,
    BridgeSession,
    Device,
    DeviceBinding,
    PetSnapshot,
    SyncLog,
    User,
)
from ..schemas import ActivityBatchIn, BridgeSessionRequest, BridgeStatusIn, DeviceBindRequest, PetSnapshotIn
from ..security import hash_token, new_token
from ..services.events import record_event

router = APIRouter(prefix="/api/v1", tags=["devices"])


def active_binding(db: Session, device_id: str) -> DeviceBinding | None:
    return db.scalar(
        select(DeviceBinding).where(DeviceBinding.device_id == device_id, DeviceBinding.unbound_at.is_(None))
    )


def latest_bridge(db: Session, device_id: str, user_id: str | None = None) -> BridgeSession | None:
    query = select(BridgeSession).where(BridgeSession.device_id == device_id)
    if user_id:
        query = query.where(BridgeSession.user_id == user_id)
    return db.scalar(query.order_by(BridgeSession.created_at.desc()))


def bridge_payload(bridge: BridgeSession | None) -> dict:
    if not bridge:
        return {
            "state": "not_running",
            "running": False,
            "connected": False,
            "message": "未发现桥接会话",
            "lastSeenAt": None,
            "lastSyncStatus": None,
            "lastSyncAt": None,
            "lastSyncMessage": None,
        }
    last_seen = bridge.last_seen_at
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    stale = not last_seen or datetime.now(timezone.utc) - last_seen > timedelta(seconds=45)
    running = bridge.running and not stale
    return {
        "state": "stale" if stale and bridge.running else bridge.state,
        "running": running,
        "connected": bridge.connected and running,
        "message": bridge.message,
        "lastSeenAt": bridge.last_seen_at.isoformat() if bridge.last_seen_at else None,
        "clientId": bridge.client_id,
        "lastSyncStatus": bridge.last_sync_status,
        "lastSyncAt": bridge.last_sync_at.isoformat() if bridge.last_sync_at else None,
        "lastSyncMessage": bridge.last_sync_message,
    }


def device_payload(device: Device, bound: bool = True, bridge: BridgeSession | None = None) -> dict:
    now = datetime.now(timezone.utc)
    last_sync = device.last_sync_at
    if not bound:
        sync_state = "unbound"
    elif not last_sync:
        sync_state = "stale"
    else:
        aware_sync = last_sync.replace(tzinfo=timezone.utc) if last_sync.tzinfo is None else last_sync
        sync_state = "synced" if now - aware_sync <= timedelta(days=1) else "stale"
    return {
        "id": device.id,
        "name": device.name,
        "model": device.model,
        "firmwareVersion": device.firmware_version,
        "protocolVersion": device.sync_protocol_version,
        "battery": device.battery,
        "bound": bound,
        "lastSyncAt": device.last_sync_at.isoformat() if device.last_sync_at else None,
        "syncState": sync_state,
        "anomaly": "超过 24 小时未同步" if sync_state == "stale" else None,
        "bridge": bridge_payload(bridge),
    }


def sync_payload(log: SyncLog, device: Device) -> dict:
    return {
        "id": log.id,
        "deviceId": device.serial_number,
        "createdAt": log.created_at.isoformat(),
        "status": log.status,
        "recordCount": log.record_count,
        "message": log.message,
        "source": log.source,
        "transport": log.transport,
    }


def activity_record_matches(existing: ActivityRecord, incoming) -> bool:
    stored_time = existing.occurred_at
    if stored_time.tzinfo is None:
        stored_time = stored_time.replace(tzinfo=timezone.utc)
    else:
        stored_time = stored_time.astimezone(timezone.utc)
    return (
        stored_time == incoming.occurred_at.astimezone(timezone.utc)
        and existing.activity_date == incoming.local_date
        and existing.steps == incoming.steps
        and existing.active_minutes == incoming.active_minutes
        and existing.goal == incoming.goal
        and existing.timezone_offset_minutes == incoming.timezone_offset_minutes
        and existing.source == incoming.source
        and existing.rtc_trusted == incoming.rtc_trusted
    )


@router.get("/devices")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bindings = list(db.scalars(
        select(DeviceBinding).where(DeviceBinding.user_id == user.id, DeviceBinding.unbound_at.is_(None))
    ))
    result = []
    for binding in bindings:
        device = db.get(Device, binding.device_id)
        if device:
            result.append(device_payload(device, bridge=latest_bridge(db, device.id, user.id)))
    return result


@router.post("/devices/bind")
def bind_device(
    payload: DeviceBindRequest,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    device = db.scalar(select(Device).where(Device.serial_number == payload.serial_number))
    if not device or device.claim_code_hash != hash_token(payload.claim_code):
        raise HTTPException(status_code=404, detail="设备编号或绑定码不正确")
    existing = active_binding(db, device.id)
    if existing and existing.user_id != user.id:
        raise HTTPException(status_code=409, detail="设备已被其他用户绑定")
    if not existing:
        db.add(DeviceBinding(device_id=device.id, user_id=user.id))
        db.commit()
    return device_payload(device, bridge=latest_bridge(db, device.id, user.id))


@router.delete("/devices/{device_id}/binding")
def unbind_device(
    device_id: str,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    binding = db.scalar(select(DeviceBinding).where(
        DeviceBinding.device_id == device_id,
        DeviceBinding.user_id == user.id,
        DeviceBinding.unbound_at.is_(None),
    ))
    if not binding:
        raise HTTPException(status_code=404, detail="未找到有效设备绑定")
    binding.unbound_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/devices/{device_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def request_sync(
    device_id: str,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    binding = db.scalar(select(DeviceBinding).where(
        DeviceBinding.device_id == device_id,
        DeviceBinding.user_id == user.id,
        DeviceBinding.unbound_at.is_(None),
    ))
    if not device or not binding:
        raise HTTPException(status_code=404, detail="设备不存在或不属于当前用户")
    log = SyncLog(
        device_id=device.id,
        user_id=user.id,
        upload_id="web-" + str(uuid.uuid4()),
        source="web_request",
        status="pending",
        message="同步请求已记录，等待移动端桥接或设备上传",
        is_demo=device.is_demo,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return sync_payload(log, device)


@router.post("/devices/serial/{serial_number}/bridge-sessions", status_code=status.HTTP_201_CREATED)
def create_bridge_session(
    serial_number: str,
    payload: BridgeSessionRequest,
    user: User = Depends(get_current_user),
    _=Depends(require_csrf),
    db: Session = Depends(get_db),
):
    device = db.scalar(select(Device).where(Device.serial_number == serial_number))
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    binding = db.scalar(select(DeviceBinding).where(
        DeviceBinding.device_id == device.id,
        DeviceBinding.user_id == user.id,
        DeviceBinding.unbound_at.is_(None),
    ))
    if not binding:
        raise HTTPException(status_code=403, detail="设备未绑定到当前用户")
    now = datetime.now(timezone.utc)
    for previous in db.scalars(select(BridgeSession).where(
        BridgeSession.device_id == device.id,
        BridgeSession.user_id == user.id,
        BridgeSession.client_id == payload.client_id,
        BridgeSession.revoked_at.is_(None),
    )):
        previous.revoked_at = now
        previous.connected = False
        previous.running = False
    token = new_token()
    session = BridgeSession(
        device_id=device.id,
        user_id=user.id,
        client_id=payload.client_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(minutes=15),
        last_seen_at=now,
        state="authorized",
        running=True,
        message="桥接已获得短期授权",
    )
    db.add(session)
    db.commit()
    return {
        "token": token,
        "expiresAt": session.expires_at.isoformat(),
        "serialNumber": device.serial_number,
        "clientId": session.client_id,
    }


@router.get("/devices/{device_id}/bridge-status")
def get_bridge_status(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    binding = db.scalar(select(DeviceBinding).where(
        DeviceBinding.device_id == device_id,
        DeviceBinding.user_id == user.id,
        DeviceBinding.unbound_at.is_(None),
    ))
    if not binding:
        raise HTTPException(status_code=404, detail="设备不存在或不属于当前用户")
    return bridge_payload(latest_bridge(db, device_id, user.id))


@router.get("/devices/sync-logs")
def sync_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = list(db.scalars(
        select(SyncLog).where(SyncLog.user_id == user.id).order_by(SyncLog.created_at.desc()).limit(100)
    ))
    result = []
    for log in logs:
        device = db.get(Device, log.device_id)
        if device:
            result.append(sync_payload(log, device))
    return result


@router.post("/device-uploads/{serial_number}/activity-batches")
def upload_activity_batch(
    serial_number: str,
    payload: ActivityBatchIn,
    x_velapet_device_token: str | None = Header(default=None, alias="X-VelaPet-Device-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    device, bridge, transport = get_upload_device(serial_number, x_velapet_device_token, authorization, db)
    binding = active_binding(db, device.id)
    if not binding:
        raise HTTPException(status_code=403, detail="设备当前没有有效用户绑定")
    if bridge and bridge.user_id != binding.user_id:
        raise HTTPException(status_code=403, detail="桥接会话与当前设备绑定用户不匹配")
    if bridge and payload.bridge_client_id and payload.bridge_client_id != bridge.client_id:
        raise HTTPException(status_code=403, detail="桥接客户端标识与短期授权不匹配")
    upload_offset = payload.upload_offset if payload.upload_offset is not None else (payload.cursor or 0)
    log = db.scalar(select(SyncLog).where(
        SyncLog.device_id == device.id,
        SyncLog.source == "device_upload",
        SyncLog.upload_id == payload.upload_id,
    ))
    if log and log.user_id != binding.user_id:
        raise HTTPException(status_code=409, detail="上传任务属于设备的历史绑定用户，不能跨绑定继续")
    if not log:
        if upload_offset != 0:
            raise HTTPException(status_code=409, detail="HTTP 上传任务偏移不匹配，期望 0")
        device_cursor = payload.device_cursor
        if device_cursor is None:
            device_cursor = device.activity_cursor or 0
        if device.activity_cursor is not None and device_cursor > device.activity_cursor:
            raise HTTPException(
                status_code=409,
                detail=f"设备历史游标存在缺口，数据库期望 {device.activity_cursor}，收到 {device_cursor}",
            )
        log = SyncLog(
            device_id=device.id,
            user_id=binding.user_id,
            upload_id=payload.upload_id,
            source="device_upload",
            transport=transport,
            status="pending",
            device_cursor_start=device_cursor,
            device_cursor_end=device_cursor,
            is_demo=device.is_demo,
        )
        db.add(log)
        db.flush()
    else:
        expected_device_cursor = (log.device_cursor_start or 0) + upload_offset
        device_cursor = payload.device_cursor if payload.device_cursor is not None else expected_device_cursor
        if device_cursor != expected_device_cursor:
            raise HTTPException(
                status_code=409,
                detail=f"设备游标与 HTTP 偏移不一致，期望 {expected_device_cursor}",
            )
    if upload_offset > log.cursor:
        raise HTTPException(status_code=409, detail=f"HTTP 上传任务偏移不匹配，期望 {log.cursor}")
    if upload_offset < log.cursor:
        for item in payload.records:
            existing = db.scalar(select(ActivityRecord).where(
                ActivityRecord.device_id == device.id,
                ActivityRecord.external_record_id == item.record_id,
            ))
            if not existing or not activity_record_matches(existing, item):
                raise HTTPException(status_code=409, detail=f"记录 {item.record_id} 内容冲突：重放内容与已持久化内容不一致")
        ack_cursor = device_cursor + len(payload.records)
        db.commit()
        return {
            "uploadId": payload.upload_id,
            "accepted": 0,
            "duplicates": len(payload.records),
            "nextCursor": log.cursor,
            "nextUploadOffset": log.cursor,
            "ackCursor": ack_cursor,
            "persistedDeviceCursor": device.activity_cursor or ack_cursor,
            "complete": log.status == "success",
        }

    accepted = 0
    duplicates = 0
    touched_dates = set()
    persisted_before = device.activity_cursor
    for index, item in enumerate(payload.records):
        local_time = item.occurred_at.astimezone(timezone.utc) + timedelta(minutes=item.timezone_offset_minutes)
        if local_time.date() != item.local_date:
            raise HTTPException(status_code=422, detail=f"记录 {item.record_id} 的本地日期与时区不匹配")
        exists = db.scalar(select(ActivityRecord).where(
            ActivityRecord.device_id == device.id,
            ActivityRecord.external_record_id == item.record_id,
        ))
        if exists:
            if not activity_record_matches(exists, item):
                raise HTTPException(status_code=409, detail=f"记录 {item.record_id} 内容冲突：重复 ID 的内容不一致")
            duplicates += 1
            continue
        if persisted_before is not None and device_cursor + index < persisted_before:
            raise HTTPException(status_code=409, detail=f"设备游标 {device_cursor + index} 已持久化但记录不存在")
        db.add(ActivityRecord(
            external_record_id=item.record_id,
            device_id=device.id,
            user_id=binding.user_id,
            occurred_at=item.occurred_at.astimezone(timezone.utc),
            activity_date=item.local_date,
            steps=item.steps,
            active_minutes=item.active_minutes,
            goal=item.goal,
            timezone_offset_minutes=item.timezone_offset_minutes,
            source=item.source,
            rtc_trusted=item.rtc_trusted,
            is_demo=device.is_demo,
        ))
        touched_dates.add(item.local_date)
        accepted += 1
    db.flush()

    for activity_date in touched_dates:
        totals = db.execute(
            select(
                func.sum(ActivityRecord.steps),
                func.sum(ActivityRecord.active_minutes),
                func.max(ActivityRecord.goal),
                func.max(ActivityRecord.occurred_at),
            ).where(
                ActivityRecord.user_id == binding.user_id,
                ActivityRecord.device_id == device.id,
                ActivityRecord.activity_date == activity_date,
            )
        ).one()
        daily = db.scalar(select(ActivityDaily).where(
            ActivityDaily.user_id == binding.user_id,
            ActivityDaily.device_id == device.id,
            ActivityDaily.activity_date == activity_date,
        ))
        if not daily:
            daily = ActivityDaily(user_id=binding.user_id, device_id=device.id, activity_date=activity_date)
            db.add(daily)
        daily.steps = int(totals[0] or 0)
        daily.active_minutes = int(totals[1] or 0)
        daily.goal = int(totals[2] or 10000)
        daily.last_record_at = totals[3]
        daily.is_demo = device.is_demo
        sources = set(db.scalars(select(ActivityRecord.source).where(
            ActivityRecord.user_id == binding.user_id,
            ActivityRecord.device_id == device.id,
            ActivityRecord.activity_date == activity_date,
        )))
        daily.data_source = next(iter(sources)) if len(sources) == 1 else "mixed"

    batch_end_cursor = device_cursor + len(payload.records)
    log.cursor = max(log.cursor, upload_offset + len(payload.records))
    log.device_cursor_end = max(log.device_cursor_end or device_cursor, batch_end_cursor)
    log.record_count += accepted
    log.status = "success" if payload.final else "pending"
    log.message = "设备批次上传完成" if payload.final else "批次已接收，等待后续游标"
    device.last_sync_at = datetime.now(timezone.utc)
    device.activity_cursor = max(device.activity_cursor or batch_end_cursor, batch_end_cursor)
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version
    if payload.protocol_version:
        device.sync_protocol_version = payload.protocol_version
    if bridge:
        bridge.connected = True
        bridge.running = True
        bridge.state = "syncing"
        bridge.message = log.message
    db.commit()
    owner = db.get(User, binding.user_id)
    if owner and accepted > 0:
        record_event(db, owner, "device_active")
    return {
        "uploadId": payload.upload_id,
        "accepted": accepted,
        "duplicates": duplicates,
        "nextCursor": log.cursor,
        "nextUploadOffset": log.cursor,
        "ackCursor": batch_end_cursor,
        "persistedDeviceCursor": device.activity_cursor,
        "complete": payload.final,
    }


@router.post("/device-uploads/{serial_number}/bridge-status")
def update_bridge_status(
    serial_number: str,
    payload: BridgeStatusIn,
    x_velapet_device_token: str | None = Header(default=None, alias="X-VelaPet-Device-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    device, bridge, _ = get_upload_device(serial_number, x_velapet_device_token, authorization, db)
    binding = active_binding(db, device.id)
    if not binding or (bridge and bridge.user_id != binding.user_id):
        raise HTTPException(status_code=403, detail="桥接会话与当前设备绑定不匹配")
    if bridge is None:
        raise HTTPException(status_code=403, detail="状态上报仅接受短期桥接会话")
    bridge.state = payload.state
    bridge.running = payload.running
    bridge.connected = payload.connected and payload.running
    bridge.message = payload.message
    now = datetime.now(timezone.utc)
    bridge.last_seen_at = now
    if payload.state in ("success", "failed"):
        bridge.last_sync_status = payload.state
        bridge.last_sync_at = now
        bridge.last_sync_message = payload.message
    db.commit()
    return bridge_payload(bridge)


@router.post("/device-uploads/{serial_number}/pet-snapshots", status_code=status.HTTP_201_CREATED)
def upload_pet_snapshot(
    serial_number: str,
    payload: PetSnapshotIn,
    x_velapet_device_token: str | None = Header(default=None, alias="X-VelaPet-Device-Token"),
    db: Session = Depends(get_db),
):
    device = get_authenticated_device(serial_number, x_velapet_device_token, db)
    binding = active_binding(db, device.id)
    if not binding:
        raise HTTPException(status_code=403, detail="设备当前没有有效用户绑定")
    existing = db.scalar(select(PetSnapshot).where(
        PetSnapshot.device_id == device.id,
        PetSnapshot.snapshot_id == payload.snapshot_id,
    ))
    if existing:
        return {"id": existing.id, "version": existing.version, "duplicate": True}
    latest = db.scalar(select(PetSnapshot).where(PetSnapshot.device_id == device.id).order_by(PetSnapshot.version.desc()))
    if latest and payload.version <= latest.version:
        raise HTTPException(status_code=409, detail=f"快照版本过旧，当前版本为 {latest.version}")
    snapshot = PetSnapshot(
        snapshot_id=payload.snapshot_id,
        device_id=device.id,
        user_id=binding.user_id,
        version=payload.version,
        pet_instance_id=payload.pet_instance_id,
        name=payload.name,
        level=payload.level,
        current_exp=payload.current_exp,
        next_level_exp=payload.next_level_exp,
        title=payload.title,
        skins=payload.skins,
        tasks=[task.model_dump(by_alias=True) for task in payload.tasks],
        total_steps=payload.total_steps,
        streak_days=payload.streak_days,
        captured_at=payload.captured_at.astimezone(timezone.utc),
        is_demo=device.is_demo,
    )
    db.add(snapshot)
    device.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(snapshot)
    return {"id": snapshot.id, "version": snapshot.version, "duplicate": False}
