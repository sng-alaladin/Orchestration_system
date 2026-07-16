"""공통 테스트 픽스처.

기본 테스트는 외부 자원 없이 SQLite in-memory로 실행된다.
(Docker/PostgreSQL 필요 테스트는 @pytest.mark.integration으로 분리)
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.security import hash_password
from app.db import models  # noqa: F401  (모델 등록)
from app.db.base import Base
from app.db.repositories.users import UserRepository
from app.db.session import SessionFactory, get_db
from app.main import create_app

TEST_USER_EMAIL = "user@example.com"
TEST_USER_PASSWORD = "test-password-123"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        env="test",
        database_url="sqlite+aiosqlite://",
        log_json=False,
        admin_email=None,
        admin_password=None,
    )


@pytest.fixture
async def session_factory() -> AsyncIterator[SessionFactory]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(test_settings: Settings, session_factory: SessionFactory) -> FastAPI:
    application = create_app(test_settings)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    # 테스트는 lifespan을 실행하지 않으므로 state를 직접 구성한다.
    application.state.session_factory = session_factory
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
async def seeded_user(session_factory: SessionFactory) -> str:
    """테스트 사용자를 만들고 이메일을 반환한다."""
    async with session_factory() as session:
        await UserRepository(session).create(
            email=TEST_USER_EMAIL,
            password_hash=hash_password(TEST_USER_PASSWORD),
            display_name="테스트 사용자",
        )
        await session.commit()
    return TEST_USER_EMAIL
