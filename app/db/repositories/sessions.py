"""sessions(로그인 세션) 저장소."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_session import UserSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> UserSession:
        user_session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(user_session)
        await self._session.flush()
        return user_session

    async def get_active(self, token_hash: str, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, user_session: UserSession, now: datetime) -> None:
        user_session.revoked_at = now
        await self._session.flush()
