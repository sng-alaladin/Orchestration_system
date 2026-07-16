"""DB 엔진·세션 팩토리와 FastAPI 의존성."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.exceptions import NotInitializedError

SessionFactory = async_sessionmaker[AsyncSession]


def create_engine_and_factory(settings: Settings) -> tuple[AsyncEngine, SessionFactory]:
    engine = create_async_engine(settings.database_url, echo=settings.db_echo)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """요청 단위 DB 세션. 쓰기는 엔드포인트에서 명시적으로 commit한다."""
    factory: SessionFactory | None = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise NotInitializedError("DB 세션 팩토리가 초기화되지 않았다 (lifespan 미실행).")
    async with factory() as session:
        yield session
