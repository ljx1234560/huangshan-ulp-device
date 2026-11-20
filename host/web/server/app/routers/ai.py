from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import ActivityDaily, PetSnapshot, User, uuid4
from ..services.ai_provider import AiContext, MockAiProvider, get_ai_provider
from ..services.events import record_event

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/coaching")
def coaching(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    activities = list(db.scalars(
        select(ActivityDaily).where(ActivityDaily.user_id == user.id).order_by(ActivityDaily.activity_date.desc()).limit(7)
    ))
    snapshot = db.scalar(
        select(PetSnapshot).where(PetSnapshot.user_id == user.id).order_by(PetSnapshot.version.desc())
    )
    latest = activities[0] if activities else None
    average = round(sum(item.steps for item in activities) / len(activities)) if activities else 0
    context = AiContext(
        user_id=user.id,
        pet_name=snapshot.name if snapshot else "VelaPet",
        level=snapshot.level if snapshot else 1,
        current_exp=snapshot.current_exp if snapshot else 0,
        next_level_exp=snapshot.next_level_exp if snapshot else 1,
        today_steps=latest.steps if latest else 0,
        goal=latest.goal if latest else 10000,
        active_minutes=latest.active_minutes if latest else 0,
        streak_days=snapshot.streak_days if snapshot else 0,
        average_steps=average,
    )
    provider = get_ai_provider(settings)
    try:
        reply, source = provider.coaching(context)
    except (ValueError, KeyError, Exception):
        reply, _ = MockAiProvider().coaching(context)
        source = "local_fallback"
    remaining = max(0, context.goal - context.today_steps)
    record_event(db, user, "ai_coaching")
    return [
        {
            "id": uuid4(),
            "title": "今日运动建议",
            "content": reply,
            "evidence": [
                f"今日 {context.today_steps:,} 步",
                f"目标 {context.goal:,} 步",
                f"近 7 日平均 {context.average_steps:,} 步",
            ],
            "category": "today",
            "source": source,
        },
        {
            "id": uuid4(),
            "title": "本周保持稳定节奏",
            "content": f"以近 7 日平均 {context.average_steps:,} 步为基线，优先保持规律，再逐步提高目标。",
            "evidence": [f"近 7 日记录 {len(activities)} 天", f"今日活跃 {context.active_minutes} 分钟"],
            "category": "plan",
            "source": "mock" if settings.ai_provider == "mock" else "local_fallback",
        },
        {
            "id": uuid4(),
            "title": "久坐提醒",
            "content": "如果已经连续坐了约 60 分钟，可以起身走动 3–5 分钟。此建议不构成医疗判断。",
            "evidence": ["仅依据步数与活动时长", "未使用心率、血氧或 GPS"],
            "category": "sedentary",
            "source": "mock" if settings.ai_provider == "mock" else "local_fallback",
        },
        {
            "id": uuid4(),
            "title": f"{context.pet_name}的鼓励",
            "content": "今天目标已完成，星光已经点亮！" if remaining == 0 else f"再收集 {remaining:,} 个脚印，就能点亮今天的星轨啦！",
            "evidence": [f"当前完成 {round(context.today_steps / context.goal * 100) if context.goal else 0}%"],
            "category": "encouragement",
            "source": "mock" if settings.ai_provider == "mock" else "local_fallback",
        },
    ]
