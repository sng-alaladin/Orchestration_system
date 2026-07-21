"""전환 테이블 전수 실행 테스트 — 모든 상태 전환 + 예외 복귀 경로.

transitions.py의 모든 전환에 대해: Guard 전제 조건을 준비하고 fire() 하면
정의된 목적지(체크포인트 복귀 포함)로 이동해야 한다.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductState
from app.core.security import hash_password
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_document import ProjectDocument
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.task import Task
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.db.session import SessionFactory
from app.orchestrator.development_state_machine import build_development_state_machine
from app.orchestrator.product_state_machine import build_product_state_machine
from app.orchestrator.state_machine import StateMachine
from app.orchestrator.transitions import (
    CHECKPOINT,
    DEVELOPMENT_TRANSITIONS,
    PRODUCT_TRANSITIONS,
    TransitionDef,
)

# 체크포인트 복귀 검증에 사용할 "직전 진행 상태"
PRODUCT_RESUME_STATE = "REQUIREMENT_DRAFTING"
DEV_RESUME_STATE = "IMPLEMENTING"


async def _make_user_project(session: AsyncSession, status: str) -> Project:
    user = User(
        email=f"matrix-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=hash_password("pw-123456"),
        display_name="매트릭스",
    )
    session.add(user)
    await session.flush()
    project = Project(
        user_id=user.id, name="매트릭스", idea_text="엑셀 보고서를 만들어줘", status=status
    )
    session.add(project)
    await session.flush()
    return project


async def _make_task(session: AsyncSession, status: str) -> Task:
    project = await _make_user_project(session, ProductState.READY_FOR_DEVELOPMENT)
    task = Task(project_id=project.id, title="테스트 태스크", status=status)
    session.add(task)
    await session.flush()
    return task


def _classification(
    project_id: uuid.UUID, *, prohibited: list[str] | None = None, expert_confirmed: bool = False
) -> ProjectClassification:
    return ProjectClassification(
        project_id=project_id,
        automation_class="SELF_SERVICE",
        gate="PROCEED",
        reasons=["테스트"],
        prohibited_features=prohibited or [],
        risky_features=[],
        user_message="테스트",
        expert_confirmed=expert_confirmed,
    )


def _approval(project_id: uuid.UUID, user_id: uuid.UUID, kind: str, decision: str) -> UserApproval:
    return UserApproval(
        project_id=project_id,
        user_id=user_id,
        approval_type=kind,
        target_ref="matrix",
        decision=decision,
    )


def _document(project_id: uuid.UUID, user_id: uuid.UUID, doc_type: str) -> ProjectDocument:
    return ProjectDocument(
        project_id=project_id,
        user_id=user_id,
        kind="GENERATED",
        doc_type=doc_type,
        filename=f"{doc_type}.md",
        content_type="text/markdown",
        content="# 문서",
    )


async def _prepare_guard(
    session: AsyncSession,
    machine: StateMachine,
    subject: Project | Task,
    tdef: TransitionDef,
    subject_type: str,
    resume_state: str,
) -> dict[str, Any]:
    """Guard 전제 조건을 만들고 fire()에 넘길 context를 반환한다."""
    guard = tdef.guard
    project_id = getattr(subject, "project_id", None) or subject.id
    user_id_stmt = subject.user_id if isinstance(subject, Project) else None
    if user_id_stmt is None:
        project = await session.get(Project, project_id)
        assert project is not None
        owner_id = project.user_id
    else:
        owner_id = user_id_stmt

    ctx: dict[str, Any] = {}
    needs_checkpoint = tdef.target == CHECKPOINT

    match guard:
        case None:
            pass
        case g if g and g.startswith("deferred:"):
            pass
        case "has_planning_input":
            pass  # 프로젝트 생성 시 idea_text 포함
        case "classification_saved":
            session.add(_classification(project_id))
        case "prohibited_detected":
            session.add(_classification(project_id, prohibited=["결제 기능"]))
        case "expert_not_confirmed":
            session.add(_classification(project_id, expert_confirmed=False))
        case "expert_confirmed":
            session.add(_classification(project_id, expert_confirmed=True))
        case "expert_confirmed_with_checkpoint":
            session.add(_classification(project_id, expert_confirmed=True))
            needs_checkpoint = True
        case "open_questions_exist":
            session.add(
                RequirementQuestion(
                    project_id=project_id, question_key="Q-901", question="질문?"
                )
            )
        case "no_open_questions":
            pass
        case "answered_question_exists":
            session.add(
                RequirementQuestion(
                    project_id=project_id,
                    question_key="Q-902",
                    question="질문?",
                    status="ANSWERED",
                    answer="답변",
                )
            )
        case "requirements_approval_exists":
            session.add(_approval(project_id, owner_id, "REQUIREMENTS", "APPROVED"))
        case "requirements_change_request_exists":
            session.add(_approval(project_id, owner_id, "REQUIREMENTS", "CHANGES_REQUESTED"))
        case "reduced_scope_approval_exists":
            session.add(_approval(project_id, owner_id, "REDUCED_SCOPE", "APPROVED"))
        case "expansion_approval_exists":
            session.add(_approval(project_id, owner_id, "EXPANSION", "APPROVED"))
        case "plan_approval_exists":
            session.add(_approval(project_id, owner_id, "PLAN", "APPROVED"))
        case "result_approval_exists":
            session.add(_approval(project_id, owner_id, "RESULT", "APPROVED"))
        case "prd_document_exists":
            session.add(_document(project_id, owner_id, "PRD"))
        case "backlog_document_exists":
            session.add(_document(project_id, owner_id, "BACKLOG"))
        case "capability_no_gap":
            ctx["capability_missing"] = []
        case "capability_gap_exists":
            ctx["capability_missing"] = ["email-send"]
        case "policy_decision_auto_approve":
            ctx["policy_decision"] = "AUTO_APPROVE"
        case "policy_decision_user_approval":
            ctx["policy_decision"] = "USER_APPROVAL"
        case "policy_decision_expert_required":
            ctx["policy_decision"] = "EXPERT_REQUIRED"
        case "policy_decision_auto_blocked":
            ctx["policy_decision"] = "AUTO_BLOCKED"
        case "checkpoint_exists" | "can_retry":
            needs_checkpoint = True
        case _:
            pytest.fail(f"매트릭스 테스트에 준비 로직이 없는 Guard: {guard}")

    if needs_checkpoint:
        await machine.checkpoints.save(subject_type, subject.id, state=resume_state)
    await session.flush()
    return ctx


@pytest.mark.parametrize(
    "tdef", PRODUCT_TRANSITIONS, ids=lambda t: f"{t.source}--{t.event}"
)
async def test_product_transition_fires(
    tdef: TransitionDef, session_factory: SessionFactory
) -> None:
    async with session_factory() as session:
        machine = build_product_state_machine(session)
        project = await _make_user_project(session, tdef.source)
        ctx = await _prepare_guard(
            session, machine, project, tdef, "project", PRODUCT_RESUME_STATE
        )
        result = await machine.fire(project, tdef.event, context=ctx)
        expected = PRODUCT_RESUME_STATE if tdef.target == CHECKPOINT else tdef.target
        assert result.applied is True
        assert project.status == expected
        await session.commit()


@pytest.mark.parametrize(
    "tdef", DEVELOPMENT_TRANSITIONS, ids=lambda t: f"{t.source}--{t.event}"
)
async def test_development_transition_fires(
    tdef: TransitionDef, session_factory: SessionFactory
) -> None:
    async with session_factory() as session:
        machine = build_development_state_machine(session)
        task = await _make_task(session, tdef.source)
        ctx = await _prepare_guard(session, machine, task, tdef, "task", DEV_RESUME_STATE)
        result = await machine.fire(task, tdef.event, context=ctx)
        expected = DEV_RESUME_STATE if tdef.target == CHECKPOINT else tdef.target
        assert result.applied is True
        assert task.status == expected
        await session.commit()
