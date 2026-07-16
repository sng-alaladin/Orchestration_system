"""세션 쿠키 기반 인증 의존성."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.config import Settings
from app.core.security import hash_session_token
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_db

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="로그인이 필요합니다.",
)


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_current_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UserSession:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _UNAUTHORIZED
    user_session = await SessionRepository(db).get_active(hash_session_token(token), utc_now())
    if user_session is None:
        raise _UNAUTHORIZED
    return user_session


async def get_current_user(
    user_session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = await UserRepository(db).get(user_session.user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user
