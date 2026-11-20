from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import (
    ActivityDaily,
    Device,
    DeviceBinding,
    PetGenerationJob,
    SyncLog,
    User,
    UserEvent,
    BridgeSession,
)
from ..services.events import audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def resolve_dates(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    end = end_date or date.today()
    start = start_date or end - timedelta(days=29)
    if start > end or (end - start).days > 90:
        raise HTTPException(status_code=422, detail="统计日期范围必须为 1–91 天")
    return start, end


def active_users_between(db: Session, start: date, end: date) -> set[str]:
    web = set(db.scalars(select(UserEvent.user_id).where(
        UserEvent.event_type == "web_active",
        UserEvent.event_date >= start,
        UserEvent.event_date <= end,
    )))
    device = set(db.scalars(select(ActivityDaily.user_id).where(
        ActivityDaily.activity_date >= start,
        ActivityDaily.activity_date <= end,
        ActivityDaily.steps > 0,
    )))
    return web | device


@router.get("/metrics/overview")
def overview(
    start_date: date | None = None,
    end_date: date | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start, end = resolve_dates(start_date, end_date)
    users = list(db.scalars(select(User)))
    events = list(db.scalars(select(UserEvent).where(UserEvent.event_date >= start, UserEvent.event_date <= end)))
    activity = list(db.scalars(select(ActivityDaily).where(
        ActivityDaily.activity_date >= start, ActivityDaily.activity_date <= end
    )))
    jobs = list(db.scalars(select(PetGenerationJob).where(
        PetGenerationJob.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
        PetGenerationJob.created_at <= datetime.combine(end, time.max, tzinfo=timezone.utc),
    )))
    syncs = list(db.scalars(select(SyncLog).where(
        SyncLog.source == "device_upload",
        SyncLog.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
        SyncLog.created_at <= datetime.combine(end, time.max, tzinfo=timezone.utc),
    )))
    active_bindings = db.scalar(select(func.count()).select_from(DeviceBinding).where(DeviceBinding.unbound_at.is_(None))) or 0

    event_by_day: dict[date, set[str]] = defaultdict(set)
    device_by_day: dict[date, set[str]] = defaultdict(set)
    new_by_day: dict[date, int] = defaultdict(int)
    for event in events:
        if event.event_type == "web_active":
            event_by_day[event.event_date].add(event.user_id)
    for row in activity:
        if row.steps > 0:
            device_by_day[row.activity_date].add(row.user_id)
    for user in users:
        created_date = user.created_at.date()
        if start <= created_date <= end:
            new_by_day[created_date] += 1

    trend = []
    cursor = start
    while cursor <= end:
        web_users = event_by_day[cursor]
        device_users = device_by_day[cursor]
        trend.append({
            "date": cursor.isoformat(),
            "webDau": len(web_users),
            "deviceDau": len(device_users),
            "productDau": len(web_users | device_users),
            "newUsers": new_by_day[cursor],
        })
        cursor += timedelta(days=1)

    web_dau = len(event_by_day[end])
    device_dau = len(device_by_day[end])
    active_devices = len({row.device_id for row in activity if row.activity_date == end and row.steps > 0})
    product_dau = len(event_by_day[end] | device_by_day[end])
    wau = len(active_users_between(db, end - timedelta(days=6), end))
    mau = len(active_users_between(db, end - timedelta(days=29), end))
    success_count = sum(1 for item in syncs if item.status == "success")
    failed_syncs = sum(1 for item in syncs if item.status == "failed")
    bridge_syncs = sum(1 for item in syncs if item.transport == "ble_bridge")
    firmware_versions: dict[str, int] = defaultdict(int)
    for device in db.scalars(select(Device)):
        firmware_versions[device.firmware_version or "unknown"] += 1
    synced_users = len({item.user_id for item in syncs if item.status == "success" and item.user_id})
    pet_owners = len({job.user_id for job in jobs if job.status == "succeeded"})
    goal_rows = [row for row in activity if row.goal > 0]
    goal_completion = sum(1 for row in goal_rows if row.steps >= row.goal) / len(goal_rows) if goal_rows else 0
    eligible_users = [user for user in users if user.created_at.date() <= end - timedelta(days=7)]
    retained = sum(
        1 for user in eligible_users
        if user.id in active_users_between(db, user.created_at.date() + timedelta(days=1), user.created_at.date() + timedelta(days=7))
    )
    retention_rate = retained / len(eligible_users) if eligible_users else 0
    demo_flags = [user.is_demo for user in users] + [row.is_demo for row in activity] + [job.is_demo for job in jobs]
    data_source = "empty" if not demo_flags else "demo" if all(demo_flags) else "mixed" if any(demo_flags) else "production"
    audit(db, admin, "view_metrics_overview", details={"start": start.isoformat(), "end": end.isoformat()})
    return {
        "dau": web_dau,
        "deviceDau": device_dau,
        "activeDevices": active_devices,
        "productDau": product_dau,
        "wau": wau,
        "mau": mau,
        "totalUsers": len(users),
        "newUsers": sum(new_by_day.values()),
        "boundDevices": active_bindings,
        "syncSuccessRate": success_count / len(syncs) if syncs else 0,
        "syncFailures": failed_syncs,
        "bleBridgeSyncs": bridge_syncs,
        "firmwareVersions": dict(firmware_versions),
        "petGenerations": len(jobs),
        "retentionRate": retention_rate,
        "syncedUsers": synced_users,
        "petOwners": pet_owners,
        "petCreationRate": pet_owners / synced_users if synced_users else 0,
        "goalCompletionRate": goal_completion,
        "dataSource": data_source,
        "trend": trend,
    }


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(500)))
    bindings = set(db.scalars(select(DeviceBinding.user_id).where(DeviceBinding.unbound_at.is_(None))))
    audit(db, admin, "view_users")
    return [{
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "registeredAt": user.created_at.isoformat(),
        "lastActiveAt": user.last_active_at.isoformat(),
        "deviceBound": user.id in bindings,
    } for user in users]


@router.get("/devices")
def list_devices(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    devices = list(db.scalars(select(Device).order_by(Device.created_at.desc()).limit(500)))
    active_devices = set(db.scalars(select(DeviceBinding.device_id).where(DeviceBinding.unbound_at.is_(None))))
    now = datetime.now(timezone.utc)
    result = []
    for device in devices:
        last_sync = device.last_sync_at
        if last_sync and last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        sync_state = "unbound" if device.id not in active_devices else "synced" if last_sync and now - last_sync <= timedelta(days=1) else "stale"
        latest_bridge = db.scalar(select(BridgeSession).where(BridgeSession.device_id == device.id).order_by(BridgeSession.created_at.desc()))
        bridge_last_seen = latest_bridge.last_seen_at if latest_bridge else None
        if bridge_last_seen and bridge_last_seen.tzinfo is None:
            bridge_last_seen = bridge_last_seen.replace(tzinfo=timezone.utc)
        bridge_stale = not bridge_last_seen or now - bridge_last_seen > timedelta(seconds=45)
        failed_syncs = db.scalar(select(func.count()).select_from(SyncLog).where(
            SyncLog.device_id == device.id, SyncLog.status == "failed"
        )) or 0
        result.append({
            "id": device.id,
            "name": device.name,
            "model": device.model,
            "firmwareVersion": device.firmware_version,
            "protocolVersion": device.sync_protocol_version,
            "battery": device.battery,
            "bound": device.id in active_devices,
            "lastSyncAt": device.last_sync_at.isoformat() if device.last_sync_at else None,
            "syncState": sync_state,
            "anomaly": "超过 24 小时未同步" if sync_state == "stale" else None,
            "syncFailureCount": failed_syncs,
            "bridge": {
                "state": latest_bridge.state if latest_bridge else "not_running",
                "connected": bool(latest_bridge and latest_bridge.connected and latest_bridge.running and not bridge_stale),
                "running": bool(latest_bridge and latest_bridge.running and not bridge_stale),
                "message": latest_bridge.message if latest_bridge else "未发现桥接会话",
                "lastSeenAt": latest_bridge.last_seen_at.isoformat() if latest_bridge and latest_bridge.last_seen_at else None,
                "lastSyncStatus": latest_bridge.last_sync_status if latest_bridge else None,
                "lastSyncAt": latest_bridge.last_sync_at.isoformat() if latest_bridge and latest_bridge.last_sync_at else None,
                "lastSyncMessage": latest_bridge.last_sync_message if latest_bridge else None,
            },
        })
    audit(db, admin, "view_devices")
    return result


@router.get("/metrics/ai-services")
def ai_metrics(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    end = date.today()
    start = end - timedelta(days=13)
    jobs = list(db.scalars(select(PetGenerationJob).where(
        PetGenerationJob.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc)
    )))
    events = list(db.scalars(select(UserEvent).where(
        UserEvent.event_type == "ai_coaching", UserEvent.event_date >= start
    )))
    rows = []
    cursor = start
    while cursor <= end:
        day_jobs = [job for job in jobs if job.created_at.date() == cursor]
        successful = sum(1 for job in day_jobs if job.status == "succeeded")
        rows.append({
            "date": cursor.isoformat(),
            "textCalls": sum(1 for event in events if event.event_date == cursor),
            "imageCalls": len(day_jobs),
            "successRate": successful / len(day_jobs) if day_jobs else 0,
            "failedJobs": sum(1 for job in day_jobs if job.status == "failed"),
            "cost": 0,
        })
        cursor += timedelta(days=1)
    audit(db, admin, "view_ai_metrics")
    return rows


@router.get("/metrics/retention")
def retention(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = list(db.scalars(select(User).where(User.role == "user")))
    cohorts: dict[date, list[User]] = defaultdict(list)
    for user in users:
        monday = user.created_at.date() - timedelta(days=user.created_at.date().weekday())
        cohorts[monday].append(user)
    result = []
    today = date.today()
    for cohort, cohort_users in sorted(cohorts.items())[-8:]:
        ids = {user.id for user in cohort_users}
        def rate(day_start: int, day_end: int) -> float:
            active = active_users_between(db, cohort + timedelta(days=day_start), cohort + timedelta(days=day_end))
            return len(ids & active) / len(ids) if ids else 0
        result.append({
            "cohort": f"{cohort:%m/%d}–{cohort + timedelta(days=6):%m/%d}",
            "day1": rate(1, 1) if today >= cohort + timedelta(days=1) else 0,
            "day7": rate(1, 7) if today >= cohort + timedelta(days=7) else 0,
            "day30": rate(1, 30) if today >= cohort + timedelta(days=30) else 0,
        })
    audit(db, admin, "view_retention")
    return result
