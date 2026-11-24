from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..deps import get_current_user, require_csrf
from ..models import ActivityDaily, CoachingGeneration, PetSnapshot, User, uuid4
from ..services.ai_provider import (
    ActivityInsight,
    TextAdvice,
    TextAiError,
    get_text_provider,
    insufficient_data_generation,
)
from ..services.events import record_event

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
LOOKBACK_DAYS = 30
MINIMUM_DATA_DAYS = 3


def _round_to_500(value: float) -> int:
    return max(500, round(value / 500) * 500)


def build_insight(activities: list[ActivityDaily]) -> ActivityInsight:
    ordered = sorted(activities, key=lambda item: item.activity_date)
    today_record = next((item for item in reversed(ordered) if item.activity_date == date.today()), None)
    count = len(ordered)
    average_steps = round(sum(item.steps for item in ordered) / count) if count else 0
    average_active = round(sum(item.active_minutes for item in ordered) / count) if count else 0
    current_goal = today_record.goal if today_record else (ordered[-1].goal if ordered else 10000)
    midpoint = max(1, count // 2)
    older = ordered[:midpoint]
    newer = ordered[midpoint:] or older
    older_average = sum(item.steps for item in older) / len(older) if older else 0
    newer_average = sum(item.steps for item in newer) / len(newer) if newer else 0
    trend = round((newer_average - older_average) / older_average * 100) if older_average else 0
    baseline = average_steps or min(current_goal, 8000)
    safe_min = max(3000, min(20000, _round_to_500(baseline * 0.9)))
    safe_max = max(safe_min, max(3000, min(20000, _round_to_500(baseline * 1.1))))
    return ActivityInsight(
        window_days=LOOKBACK_DAYS,
        days_with_data=count,
        today_steps=today_record.steps if today_record else 0,
        today_active_minutes=today_record.active_minutes if today_record else 0,
        current_goal=current_goal,
        average_steps=average_steps,
        average_active_minutes=average_active,
        completed_days=sum(1 for item in ordered if item.goal > 0 and item.steps >= item.goal),
        trend_percent=max(-100, min(100, trend)),
        safe_goal_min=safe_min,
        safe_goal_max=safe_max,
        sufficient_data=count >= MINIMUM_DATA_DAYS,
    )


def advice_payload(advice: TextAdvice, insight: ActivityInsight, source: str) -> list[dict]:
    common = [
        f"最近 {insight.days_with_data} 天有记录",
        f"日均 {insight.average_steps:,} 步",
        f"日均活跃 {insight.average_active_minutes} 分钟",
    ]
    return [
        {"id": uuid4(), "title": "今日运动情况", "content": advice.today_summary,
         "evidence": [f"今日 {insight.today_steps:,} 步", f"今日活跃 {insight.today_active_minutes} 分钟"],
         "category": "trend", "source": source},
        {"id": uuid4(), "title": "今日运动建议", "content": advice.today_advice,
         "evidence": [f"当前目标 {insight.current_goal:,} 步", *common], "category": "today", "source": source},
        {"id": uuid4(), "title": "推荐理由", "content": advice.reason,
         "evidence": [f"近期趋势 {insight.trend_percent:+d}%", f"完成目标 {insight.completed_days} 天"],
         "category": "goal", "source": source},
        {"id": uuid4(), "title": "每周运动计划", "content": advice.weekly_plan,
         "evidence": [f"安全目标范围 {insight.safe_goal_min:,}–{insight.safe_goal_max:,} 步", "不使用医疗数据"],
         "category": "plan", "source": source},
        {"id": uuid4(), "title": "萌宠鼓励", "content": advice.pet_encouragement,
         "evidence": ["鼓励文案不修改宠物等级或 EXP"], "category": "encouragement", "source": source},
    ]


def generation_payload(item: CoachingGeneration) -> dict:
    insight = item.insight_json or {}
    return {
        "id": item.id,
        "generatedAt": item.created_at.isoformat(),
        "source": item.provider,
        "model": item.model,
        "dataSufficient": bool(insight.get("sufficient_data", False)),
        "insight": insight,
        "advice": item.advice_json,
    }


def user_context(db: Session, user: User) -> tuple[ActivityInsight, str]:
    start = date.today() - timedelta(days=LOOKBACK_DAYS - 1)
    activities = list(db.scalars(
        select(ActivityDaily).where(
            ActivityDaily.user_id == user.id,
            ActivityDaily.activity_date >= start,
            ActivityDaily.activity_date <= date.today(),
        ).order_by(ActivityDaily.activity_date.asc())
    ))
    snapshot = db.scalar(
        select(PetSnapshot).where(PetSnapshot.user_id == user.id).order_by(PetSnapshot.version.desc())
    )
    return build_insight(activities), snapshot.name if snapshot else "VelaPet"


@router.post("/coaching")
def generate_coaching(
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    insight, pet_name = user_context(db, user)
    try:
        if not insight.sufficient_data and settings.text_ai_provider != "mock":
            generated = insufficient_data_generation(insight, pet_name)
        else:
            generated = get_text_provider(settings).generate(insight, pet_name)
    except TextAiError as exc:
        raise HTTPException(status_code=exc.http_status, detail=f"{exc}（{exc.code}）") from exc
    advice = advice_payload(generated.advice, insight, generated.provider)
    stored = CoachingGeneration(
        user_id=user.id,
        provider=generated.provider,
        model=generated.model,
        advice_json=advice,
        insight_json=asdict(insight),
        duration_ms=generated.duration_ms,
        prompt_tokens=generated.prompt_tokens,
        completion_tokens=generated.completion_tokens,
        total_tokens=generated.total_tokens,
        is_demo=user.is_demo,
    )
    db.add(stored)
    db.commit()
    db.refresh(stored)
    response = generation_payload(stored)
    record_event(db, user, "ai_coaching", payload={
        "provider": generated.provider,
        "model": generated.model,
        "duration_ms": generated.duration_ms,
        "total_tokens": generated.total_tokens,
    })
    return response


@router.get("/coaching")
def latest_coaching(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    latest = db.scalar(select(CoachingGeneration).where(
        CoachingGeneration.user_id == user.id,
    ).order_by(CoachingGeneration.created_at.desc()))
    return latest.advice_json if latest else []


@router.get("/coaching/history")
def coaching_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = list(db.scalars(select(CoachingGeneration).where(
        CoachingGeneration.user_id == user.id,
    ).order_by(CoachingGeneration.created_at.desc()).limit(30)))
    return [generation_payload(item) for item in items]
