"""관리자 계정 시드 테스트."""

from app.core.bootstrap import seed_admin_user
from app.core.config import Settings
from app.core.security import verify_password
from app.db.repositories.users import UserRepository
from app.db.session import SessionFactory


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite://",
        "admin_email": "admin@example.com",
        "admin_password": "admin-password-123",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


async def test_seed_creates_admin_once(session_factory: SessionFactory) -> None:
    settings = _settings()
    assert await seed_admin_user(session_factory, settings) is True
    # 멱등성: 두 번째 호출은 건너뛴다.
    assert await seed_admin_user(session_factory, settings) is False

    async with session_factory() as session:
        repo = UserRepository(session)
        assert await repo.count() == 1
        user = await repo.get_by_email("admin@example.com")
        assert user is not None
        assert user.password_hash != "admin-password-123"
        assert verify_password(user.password_hash, "admin-password-123")


async def test_seed_skipped_without_env(session_factory: SessionFactory) -> None:
    settings = _settings(admin_email=None, admin_password=None)
    assert await seed_admin_user(session_factory, settings) is False

    async with session_factory() as session:
        assert await UserRepository(session).count() == 0
