from datetime import datetime, timezone

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, BridgeSession, Device, User
from .security import hash_token


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_current_session(
    velapet_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not velapet_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或会话已过期")
    session = db.scalar(select(AuthSession).where(AuthSession.access_token_hash == hash_token(velapet_session)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at or as_utc(session.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或会话已过期")
    return session


def get_current_user(
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, auth_session.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user


def require_csrf(
    request: Request,
    auth_session: AuthSession = Depends(get_current_session),
    velapet_csrf: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> AuthSession:
    if not velapet_csrf or not x_csrf_token or velapet_csrf != x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")
    if hash_token(x_csrf_token) != auth_session.csrf_token_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")
    return auth_session


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def get_authenticated_device(
    serial_number: str,
    x_velapet_device_token: str | None,
    db: Session,
) -> Device:
    device = db.scalar(select(Device).where(Device.serial_number == serial_number))
    if not device or not x_velapet_device_token or device.device_token_hash != hash_token(x_velapet_device_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="设备认证失败")
    return device


def get_upload_device(
    serial_number: str,
    x_velapet_device_token: str | None,
    authorization: str | None,
    db: Session,
) -> tuple[Device, BridgeSession | None, str]:
    """Authenticate either a legacy device token or a short-lived bridge token."""
    device = db.scalar(select(Device).where(Device.serial_number == serial_number))
    if not device:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="设备认证失败")
    if x_velapet_device_token and device.device_token_hash == hash_token(x_velapet_device_token):
        return device, None, "direct_api"
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        bridge = db.scalar(select(BridgeSession).where(BridgeSession.token_hash == hash_token(token)))
        now = datetime.now(timezone.utc)
        if (
            bridge
            and bridge.device_id == device.id
            and bridge.revoked_at is None
            and as_utc(bridge.expires_at) > now
        ):
            bridge.last_seen_at = now
            return device, bridge, "ble_bridge"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="设备或桥接会话认证失败")
