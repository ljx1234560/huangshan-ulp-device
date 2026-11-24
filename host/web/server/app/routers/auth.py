from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..deps import as_utc, get_current_session, get_current_user, require_csrf
from ..models import AuthSession, DeviceBinding, User
from ..schemas import LoginRequest, RegisterRequest
from ..security import hash_password, hash_token, new_token, verify_password
from ..services.events import record_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def user_payload(db: Session, user: User) -> dict:
    device_bound = db.scalar(
        select(DeviceBinding.id).where(DeviceBinding.user_id == user.id, DeviceBinding.unbound_at.is_(None))
    ) is not None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "registeredAt": user.created_at.isoformat(),
        "lastActiveAt": user.last_active_at.isoformat(),
        "deviceBound": device_bound,
    }


def set_session_cookies(response: Response, access: str, refresh: str, csrf: str, settings: Settings):
    common = {"secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie(
        "velapet_session", access, httponly=True, max_age=settings.access_session_minutes * 60, **common
    )
    response.set_cookie(
        "velapet_refresh", refresh, httponly=True, max_age=settings.refresh_session_days * 86400, **common
    )
    response.set_cookie(
        "velapet_csrf", csrf, httponly=False, max_age=settings.refresh_session_days * 86400, **common
    )


def clear_session_cookies(response: Response, settings: Settings):
    for name in ("velapet_session", "velapet_refresh", "velapet_csrf"):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


def create_session(db: Session, user: User, response: Response, settings: Settings) -> AuthSession:
    access = new_token()
    refresh = new_token()
    csrf = new_token()
    now = datetime.now(timezone.utc)
    session = AuthSession(
        user_id=user.id,
        access_token_hash=hash_token(access),
        refresh_token_hash=hash_token(refresh),
        csrf_token_hash=hash_token(csrf),
        expires_at=now + timedelta(minutes=settings.access_session_minutes),
        refresh_expires_at=now + timedelta(days=settings.refresh_session_days),
    )
    db.add(session)
    user.last_active_at = now
    db.commit()
    db.refresh(session)
    set_session_cookies(response, access, refresh, csrf, settings)
    return session


def auth_payload(db: Session, user: User, session: AuthSession) -> dict:
    return {
        "demo": user.is_demo,
        "user": user_payload(db, user),
        "expiresAt": session.expires_at.isoformat(),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = payload.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
    user = User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    session = create_session(db, user, response, settings)
    record_event(db, user, "web_active")
    return auth_payload(db, user, session)


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    session = create_session(db, user, response, settings)
    record_event(db, user, "web_active")
    return auth_payload(db, user, session)


@router.get("/me")
def me(
    user: User = Depends(get_current_user),
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    record_event(db, user, "web_active")
    return auth_payload(db, user, auth_session)


@router.post("/refresh")
def refresh_session(
    response: Response,
    velapet_refresh: str | None = Cookie(default=None),
    velapet_csrf: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not velapet_refresh or not velapet_csrf or velapet_csrf != x_csrf_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新会话失败")
    session = db.scalar(
        select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(velapet_refresh))
    )
    now = datetime.now(timezone.utc)
    if (
        not session
        or session.revoked_at
        or as_utc(session.refresh_expires_at) <= now
        or session.csrf_token_hash != hash_token(velapet_csrf)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新会话已过期")
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    session.revoked_at = now
    db.commit()
    next_session = create_session(db, user, response, settings)
    return auth_payload(db, user, next_session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    auth_session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    clear_session_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
