"""대기 상태 타임아웃 감시 테스트 — 알림 1회 발생, 상태 불변."""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.enums import AuditEventType, ProductState
from app.core.security import hash_password
from app.db.models.audit_log import AuditLog
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.workflow_event import WorkflowEvent
from app.db.session import SessionFactory
from app.orchestrator.timeout_checker import TimeoutChecker


async def _make_waiting_project(session: AsyncSession, entered_seconds_ago: int) -> Project:
    user = User(
        email=f"timeout-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("pw-123456"),
        display_name="타임아웃",
    )
    session.add(user)
    await session.flush()
    project = Project(
        user_id=user.id,
        name="타임아웃",
        idea_text="엑셀",
        status=ProductState.WAITING_REQUIREMENT_INPUT,
    )
    session.add(project)
    await session.flush()
    session.add(
        WorkflowEvent(
            subject_type="project",
            subject_id=project.id,
            machine="PRODUCT",
            event="DRAFT_HAS_UNKNOWNS",
            from_state="REQUIREMENT_DRAFTING",
            to_state="WAITING_REQUIREMENT_INPUT",
            created_at=utc_now() - timedelta(seconds=entered_seconds_ago),
        )
    )
    await session.flush()
    return project


async def test_timeout_notifies_once_and_keeps_state(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        # WAITING_REQUIREMENT_INPUT 제한(86400초)을 초과해 대기 중
        project = await _make_waiting_project(session, entered_seconds_ago=2 * 86400)
        checker = TimeoutChecker(session)
        now = utc_now()

        notification = await checker.check("project", project.id, project.status, now)
        assert notification is not None
        assert notification.limit_seconds == 86400
        assert project.status == ProductState.WAITING_REQUIREMENT_INPUT, "상태는 유지"

        # 같은 대기 구간에서는 중복 알림 없음
        assert await checker.check("project", project.id, project.status, now) is None

        stmt = select(AuditLog).where(
            AuditLog.subject_id == project.id,
            AuditLog.event_type == AuditEventType.TIMEOUT_NOTIFIED,
        )
        rows = list((await session.execute(stmt)).scalars().all())
        assert len(rows) == 1
        await session.commit()


async def test_no_timeout_before_limit(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        project = await _make_waiting_project(session, entered_seconds_ago=60)
        checker = TimeoutChecker(session)
        assert await checker.check("project", project.id, project.status, utc_now()) is None


async def test_non_waiting_state_is_ignored(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        project = await _make_waiting_project(session, entered_seconds_ago=10 * 86400)
        checker = TimeoutChecker(session)
        assert await checker.check("project", project.id, "REQUIREMENT_DRAFTING", utc_now()) is None
