from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ActivityDaily, User
from ..services.events import record_event

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


def resolve_dates(range_name: str, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    end = end_date or date.today()
    days = {"day": 1, "week": 7, "month": 30}.get(range_name)
    if days is None:
        raise HTTPException(status_code=422, detail="range 必须为 day、week 或 month")
    start = start_date or (end - timedelta(days=days - 1))
    if start > end:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    if (end - start).days > 366:
        raise HTTPException(status_code=422, detail="单次查询最多 367 天")
    return start, end


def get_rows(db: Session, user: User, start: date, end: date) -> list[ActivityDaily]:
    return list(db.scalars(
        select(ActivityDaily)
        .where(
            ActivityDaily.user_id == user.id,
            ActivityDaily.activity_date >= start,
            ActivityDaily.activity_date <= end,
        )
        .order_by(ActivityDaily.activity_date)
    ))


def summary_payload(rows: list[ActivityDaily]) -> dict:
    if not rows:
        return {
            "todaySteps": 0,
            "goal": 10000,
            "activeMinutes": 0,
            "streakDays": 0,
            "completionRate": 0,
            "lastSyncAt": "",
            "syncState": "pending",
            "dataSource": "empty",
            "points": [],
        }
    latest = rows[-1]
    dates = {row.activity_date for row in rows if row.steps > 0}
    streak = 0
    cursor = latest.activity_date
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return {
        "todaySteps": latest.steps,
        "goal": latest.goal,
        "activeMinutes": latest.active_minutes,
        "streakDays": streak,
        "completionRate": latest.steps / latest.goal if latest.goal else 0,
        "lastSyncAt": latest.last_record_at.isoformat(),
        "syncState": "synced",
        "dataSource": latest.data_source,
        "points": [
            {
                "date": row.activity_date.isoformat(),
                "steps": row.steps,
                "activeMinutes": row.active_minutes,
                "goal": row.goal,
                "source": row.data_source,
            }
            for row in rows
        ],
    }


@router.get("/daily")
def daily(
    range: str = Query(default="week"),
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = resolve_dates(range, start_date, end_date)
    record_event(db, user, "web_active")
    return summary_payload(get_rows(db, user, start, end))


@router.get("/trends")
def trends(
    range: str = Query(default="week"),
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = resolve_dates(range, start_date, end_date)
    record_event(db, user, "web_active")
    return summary_payload(get_rows(db, user, start, end))


@router.get("/weekly-summary")
def weekly_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = resolve_dates("week", start_date, end_date)
    rows = get_rows(db, user, start, end)
    previous_days = (end - start).days + 1
    previous_rows = get_rows(db, user, start - timedelta(days=previous_days), start - timedelta(days=1))
    average = round(sum(row.steps for row in rows) / len(rows)) if rows else 0
    previous_average = round(sum(row.steps for row in previous_rows) / len(previous_rows)) if previous_rows else 0
    delta = (average - previous_average) / previous_average if previous_average else 0
    return {
        "averageSteps": average,
        "totalActiveMinutes": sum(row.active_minutes for row in rows),
        "completedDays": sum(1 for row in rows if row.steps >= row.goal),
        "previousPeriodDelta": delta,
    }
