"""users 저장소."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self._session.scalar(select(func.count()).select_from(User))
        return int(result or 0)

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        return user
