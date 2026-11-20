from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ActivityDaily,
    ActivityRecord,
    Device,
    DeviceBinding,
    PetAsset,
    PetGenerationJob,
    PetSnapshot,
    SyncLog,
    User,
    UserEvent,
)
from ..security import hash_password, hash_token


def seed_demo_data(db: Session):
    if db.scalar(select(User.id).where(User.email == "demo@velapet.cn")):
        return
    now = datetime.now(timezone.utc)
    admin = User(
        email="admin@velapet.cn",
        name="Demo 运营管理员",
        password_hash=hash_password("VelaPetAdmin123!"),
        role="admin",
        is_demo=True,
        created_at=now - timedelta(days=120),
    )
    user = User(
        email="demo@velapet.cn",
        name="林晓满（Demo）",
        password_hash=hash_password("VelaPetDemo123!"),
        role="user",
        is_demo=True,
        created_at=now - timedelta(days=96),
    )
    second_user = User(
        email="second-demo@velapet.cn",
        name="隔离测试用户（Demo）",
        password_hash=hash_password("VelaPetDemo123!"),
        role="user",
        is_demo=True,
        created_at=now - timedelta(days=20),
    )
    db.add_all([admin, user, second_user])
    db.flush()
    device = Device(
        serial_number="VP-52U-2400168",
        name="我的 VelaPet（Demo）",
        model="SF32LB52-ULP",
        firmware_version="0.3.2-demo",
        battery=78,
        device_token_hash=hash_token("demo-device-token"),
        claim_code_hash=hash_token("demo-claim-code"),
        last_sync_at=now - timedelta(minutes=18),
        is_demo=True,
    )
    spare_device = Device(
        serial_number="VP-52U-UNBOUND-DEMO",
        name="待绑定 VelaPet（Demo）",
        model="SF32LB52-ULP",
        firmware_version="0.3.2-demo",
        device_token_hash=hash_token("spare-device-token"),
        claim_code_hash=hash_token("spare-claim-code"),
        is_demo=True,
    )
    db.add_all([device, spare_device])
    db.flush()
    db.add(DeviceBinding(device_id=device.id, user_id=user.id, bound_at=now - timedelta(days=90)))

    pattern = [6210, 9840, 7420, 10680, 8930, 12460, 8362]
    for index, steps in enumerate(pattern):
        day = date.today() - timedelta(days=len(pattern) - index - 1)
        occurred = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=8)
        record = ActivityRecord(
            external_record_id=f"demo-record-{day.isoformat()}",
            device_id=device.id,
            user_id=user.id,
            occurred_at=occurred,
            activity_date=day,
            steps=steps,
            active_minutes=round(steps / 185),
            goal=10000,
            timezone_offset_minutes=480,
            is_demo=True,
        )
        daily = ActivityDaily(
            user_id=user.id,
            device_id=device.id,
            activity_date=day,
            steps=steps,
            active_minutes=round(steps / 185),
            goal=10000,
            last_record_at=occurred,
            is_demo=True,
        )
        db.add_all([record, daily])
        db.add(UserEvent(
            user_id=user.id,
            event_type="web_active",
            event_date=day,
            occurred_at=occurred,
            dedupe_key=f"web_active:{user.id}:{day.isoformat()}",
            payload={"source": "demo_seed"},
            is_demo=True,
        ))

    snapshot = PetSnapshot(
        snapshot_id="demo-snapshot-v7",
        device_id=device.id,
        user_id=user.id,
        version=7,
        pet_instance_id="pet_lumi_demo",
        name="露米",
        level=7,
        current_exp=680,
        next_level_exp=1000,
        title="星光散步家",
        skins=["星云围巾", "晨光铃铛", "薄荷脚印"],
        tasks=[
            {"id": "t1", "title": "今天走到 10,000 步", "progress": 8362, "target": 10000, "rewardLabel": "设备规则奖励", "status": "active"},
            {"id": "t2", "title": "保持活跃 45 分钟", "progress": 45, "target": 45, "rewardLabel": "等待设备确认", "status": "completed"},
        ],
        total_steps=486320,
        streak_days=6,
        captured_at=now - timedelta(minutes=18),
        is_demo=True,
    )
    db.add(snapshot)
    job = PetGenerationJob(
        user_id=user.id,
        pet_instance_id="pet_lumi_demo",
        status="succeeded",
        progress=100,
        input_json={"species": "fox", "color": "lavender", "style": "celestial", "personality": "energetic", "name": "露米", "description": "Demo 内置示例"},
        provider="mock",
        source="mock_asset",
        is_demo=True,
        completed_at=now - timedelta(days=1),
    )
    db.add(job)
    db.flush()
    asset = PetAsset(
        owner_id=user.id,
        generation_job_id=job.id,
        image_url="/pets/lumi.png",
        name="露米",
        favorite=True,
        source="mock_asset",
        is_demo=True,
    )
    db.add(asset)
    db.flush()
    job.asset_id = asset.id
    user.current_pet_asset_id = asset.id
    db.add(SyncLog(
        device_id=device.id,
        user_id=user.id,
        upload_id="demo-seed-upload",
        source="device_upload",
        status="success",
        cursor=7,
        record_count=7,
        message="Demo 种子数据上传",
        is_demo=True,
        created_at=now - timedelta(minutes=18),
    ))
    db.commit()
