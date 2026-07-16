"""인증 API — 로그인 / 로그아웃 / 현재 사용자 (spec 02 §3.4)."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_app_settings, get_current_session, get_current_user
from app.core.clock import utc_now
from app.core.config import Settings
from app.core.security import (
    generate_session_token,
    hash_session_token,
    spend_dummy_verification,
    verify_password,
)
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, display_name=user.display_name)


_LOGIN_FAILED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="이메일 또는 비밀번호가 올바르지 않습니다.",
)


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UserResponse:
    user = await UserRepository(db).get_by_email(payload.email)
    if user is None:
        spend_dummy_verification()
        raise _LOGIN_FAILED
    if not verify_password(user.password_hash, payload.password):
        logger.info("login_failed", user_id=str(user.id))
        raise _LOGIN_FAILED
    if not user.is_active:
        raise _LOGIN_FAILED

    token = generate_session_token()
    ttl = timedelta(hours=settings.session_ttl_hours)
    await SessionRepository(db).create(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=utc_now() + ttl,
    )
    await db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
    logger.info("login_succeeded", user_id=str(user.id))
    return UserResponse.from_user(user)


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user_session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> None:
    await SessionRepository(db).revoke(user_session, utc_now())
    await db.commit()
    response.delete_cookie(settings.session_cookie_name)
    logger.info("logout_succeeded", user_id=str(user_session.user_id))
