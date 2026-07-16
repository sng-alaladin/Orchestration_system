"""기동 시 초기 데이터 시드.

관리자 계정은 환경변수(ORCH_ADMIN_EMAIL / ORCH_ADMIN_PASSWORD)로만 시드한다.
미설정 시 아무것도 만들지 않는다. 이미 존재하면 건너뛴다(멱등).
"""

from app.core.config import Settings
from app.core.security import hash_password
from app.db.repositories.users import UserRepository
from app.db.session import SessionFactory
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def seed_admin_user(session_factory: SessionFactory, settings: Settings) -> bool:
    """관리자 계정을 시드한다. 생성했으면 True."""
    if not settings.admin_email or not settings.admin_password:
        logger.info("admin_seed_skipped", reason="ORCH_ADMIN_EMAIL/PASSWORD 미설정")
        return False

    async with session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(settings.admin_email)
        if existing is not None:
            logger.info("admin_seed_skipped", reason="이미 존재", user_id=str(existing.id))
            return False
        user = await repo.create(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            display_name=settings.admin_display_name,
        )
        await session.commit()
        logger.info("admin_seed_created", user_id=str(user.id))
        return True
