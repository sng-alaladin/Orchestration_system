"""상태 머신 엔진 동작 테스트 — 불법 전이, Guard, Idempotency, 체크포인트, Retry, Audit."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditEventType, DevelopmentState, ProductState
from app.core.security import hash_password
from app.db.models.audit_log import AuditLog
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.task import Task
from app.db.models.user import User
from app.db.session import SessionFactory
from app.orchestrator.development_state_machine import build_development_state_machine
from app.orchestrator.product_state_machine import build_product_state_machine
from app.orchestrator.state_machine import GuardRejectedError, IllegalTransitionError


async def _make_project(session: AsyncSession, status: str) -> Project:
    user = User(
        email=f"sm-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=hash_password("pw-123456"),
        display_name="엔진 테스트",
    )
    session.add(user)
    await session.flush()
    project = Project(
        user_id=user.id, name="엔진 테스트", idea_text="엑셀 보고서", status=status
    )
    session.add(project)
    await session.flush()
    return project


async def _audit_rows(session: AsyncSession, subject_id: uuid.UUID) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.subject_id == subject_id)
        .order_by(AuditLog.occurred_at, AuditLog.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def test_illegal_transition_rejected_and_audited(
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.IDEA_RECEIVED)
        with pytest.raises(IllegalTransitionError):
            await machine.fire(project, "USER_ANSWERED")
        assert project.status == ProductState.IDEA_RECEIVED, "상태가 변하지 않아야 한다"
        rows = await _audit_rows(session, project.id)
        assert [r.event_type for r in rows] == [AuditEventType.TRANSITION_REJECTED]


async def test_guard_rejection_raises_and_audited(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.WAITING_REQUIREMENT_APPROVAL)
        # 승인 레코드 없이 REQUIREMENTS_APPROVED → Guard 거부
        with pytest.raises(GuardRejectedError):
            await machine.fire(project, "REQUIREMENTS_APPROVED")
        assert project.status == ProductState.WAITING_REQUIREMENT_APPROVAL
        rows = await _audit_rows(session, project.id)
        assert [r.event_type for r in rows] == [AuditEventType.GUARD_REJECTED]


async def test_successful_transition_is_audited(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.IDEA_RECEIVED)
        await machine.fire(project, "ANALYSIS_STARTED")
        rows = await _audit_rows(session, project.id)
        assert len(rows) == 1
        assert rows[0].event_type == AuditEventType.STATE_TRANSITION
        assert rows[0].from_state == "IDEA_RECEIVED"
        assert rows[0].to_state == "DOCUMENT_ANALYZING"
        assert rows[0].machine == "PRODUCT"


async def test_idempotency_key_prevents_double_apply(
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.IDEA_RECEIVED)

        first = await machine.fire(project, "ANALYSIS_STARTED", idempotency_key="evt-1")
        assert first.applied is True
        assert project.status == ProductState.DOCUMENT_ANALYZING

        # 동일 key 재적용 → 상태 변경 없이 재생 결과 반환 (불법 전이로도 안 터진다)
        replay = await machine.fire(project, "ANALYSIS_STARTED", idempotency_key="evt-1")
        assert replay.applied is False
        assert replay.idempotent_replay is True
        assert project.status == ProductState.DOCUMENT_ANALYZING

        rows = await _audit_rows(session, project.id)
        # 정확히 전환 1건 + 멱등 재생 1건이 기록된다.
        # (occurred_at 동률 시 상대순서는 보장되지 않으므로 다중집합으로 검증)
        assert sorted(r.event_type for r in rows) == sorted(
            [AuditEventType.STATE_TRANSITION, AuditEventType.IDEMPOTENT_REPLAY]
        )


async def test_checkpoint_saved_on_exception_and_resumed(
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.REQUIREMENT_DRAFTING)

        # 예외 상태 진입 → 직전 상태 체크포인트 자동 저장
        await machine.fire(project, "BUDGET_EXHAUSTED")
        assert project.status == ProductState.TOKEN_BUDGET_EXCEEDED
        checkpoint = await machine.checkpoints.latest("project", project.id)
        assert checkpoint is not None
        assert checkpoint.state == ProductState.REQUIREMENT_DRAFTING

        # 증액 승인 → 체크포인트 기반 직전 상태 복귀
        await machine.fire(project, "BUDGET_INCREASE_APPROVED")
        assert project.status == ProductState.REQUIREMENT_DRAFTING


async def test_checkpoint_resume_without_checkpoint_rejected(
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        # 체크포인트 없이 예외 상태에 직접 놓인 경우 복귀 불가 (명시적 거부)
        project = await _make_project(session, ProductState.BLOCKED)
        with pytest.raises(GuardRejectedError):
            await machine.fire(project, "BLOCK_RESOLVED")


async def test_retry_limit_enforced(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        machine = build_development_state_machine(session, max_retries=3)
        project = await _make_project(session, ProductState.READY_FOR_DEVELOPMENT)
        task = Task(
            project_id=project.id, title="재시도", status=DevelopmentState.IMPLEMENTING
        )
        session.add(task)
        await session.flush()

        for attempt in range(3):
            await machine.fire(task, "IMPLEMENT_FAILED")
            assert task.status == DevelopmentState.FAILED
            await machine.fire(task, "RETRY_SCHEDULED")
            assert task.status == DevelopmentState.IMPLEMENTING, f"{attempt + 1}회차 재시도 복귀"

        # 4번째 재시도는 한도 초과 → Guard 거부, 사용자 선택지는 열려 있다
        await machine.fire(task, "IMPLEMENT_FAILED")
        with pytest.raises(GuardRejectedError, match="한도"):
            await machine.fire(task, "RETRY_SCHEDULED")
        assert task.status == DevelopmentState.FAILED

        # 한도 초과 후 사용자 선택: 상담 패키지 경로는 여전히 가능
        await machine.fire(task, "RETRY_EXHAUSTED_CONSULT")
        assert task.status == DevelopmentState.WAITING_EXPERT_CONFIRMATION


async def test_expert_confirmed_prevents_reclassification_loop(
    session_factory: SessionFactory,
) -> None:
    """전문가 확인 완료 후 CLASSIFYING 재진입 시 무한 루프 방지 (추가 지시 2 연관)."""
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_project(session, ProductState.CLASSIFYING)
        session.add(
            ProjectClassification(
                project_id=project.id,
                automation_class="EXPERT_REVIEW_REQUIRED",
                gate="NEEDS_EXPERT",
                reasons=["사내 인증 연동"],
                prohibited_features=[],
                risky_features=[],
                user_message="전문가 확인 필요",
                expert_confirmed=True,  # 확인 완료 상태
            )
        )
        await session.flush()

        # 확인 완료 → CLASSIFIED_EXPERT_REVIEW 재진입은 Guard가 차단
        with pytest.raises(GuardRejectedError):
            await machine.fire(project, "CLASSIFIED_EXPERT_REVIEW")
        # EXPERT_CONFIRMED_PROCEED 경로로만 진행 가능
        await machine.fire(project, "EXPERT_CONFIRMED_PROCEED")
        assert project.status == ProductState.REQUIREMENT_DRAFTING
