from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AdminAuditLog, User, UserEvent


def record_event(db: Session, user: User, event_type: str, occurred_at: datetime | None = None, payload: dict | None = None):
    timestamp = occurred_at or datetime.now(timezone.utc)
    event_date = timestamp.date()
    dedupe_key = f"{event_type}:{user.id}:{event_date.isoformat()}"
    db.add(UserEvent(
        user_id=user.id,
        event_type=event_type,
        event_date=event_date,
        occurred_at=timestamp,
        dedupe_key=dedupe_key,
        payload=payload or {},
        is_demo=user.is_demo,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def audit(db: Session, admin: User, action: str, target_type: str | None = None, target_id: str | None = None, details: dict | None = None):
    db.add(AdminAuditLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    ))
    db.commit()
