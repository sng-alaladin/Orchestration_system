"""전환 Guard — 전환 테이블의 Guard 조건을 코드로 검증한다.

Guard는 (session, subject, context) 를 받아 GuardResult를 반환한다.
"deferred:<설명>@<phase>" 이름은 아직 검증 근거 데이터가 없는 Guard로,
통과시키되 로그를 남긴다. 해당 Phase에서 실제 구현으로 교체한다.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApprovalDecision, ApprovalType, PolicyDecision, QuestionStatus
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_document import ProjectDocument
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.user_approval import UserApproval
from app.db.models.workflow_checkpoint import WorkflowCheckpoint
from app.db.models.workflow_event import WorkflowEvent
from app.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str = ""


class StateSubject(Protocol):
    id: uuid.UUID
    status: str


GuardFn = Callable[[AsyncSession, Any, dict[str, Any]], Awaitable[GuardResult]]


def _project_id_of(subject: Any) -> uuid.UUID:
    """Guard 대상의 프로젝트 id (Project는 자기 자신, Task는 project_id)."""
    project_id: uuid.UUID = getattr(subject, "project_id", None) or subject.id
    return project_id


# ── 개별 Guard 구현 ─────────────────────────────────────────────────


async def has_planning_input(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if getattr(subject, "idea_text", None):
        return GuardResult(True)
    count = await session.scalar(
        select(func.count())
        .select_from(ProjectDocument)
        .where(ProjectDocument.project_id == subject.id, ProjectDocument.kind == "UPLOADED")
    )
    if int(count or 0) > 0:
        return GuardResult(True)
    return GuardResult(
        False, "분석할 기획 내용이 없습니다. 기획안을 입력하거나 문서를 올려 주세요."
    )


async def _latest_classification(
    session: AsyncSession, project_id: uuid.UUID
) -> ProjectClassification | None:
    stmt = (
        select(ProjectClassification)
        .where(ProjectClassification.project_id == project_id)
        .order_by(ProjectClassification.created_at.desc(), ProjectClassification.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def classification_saved(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    row = await _latest_classification(session, subject.id)
    if row is None:
        return GuardResult(False, "분류 결과가 저장되지 않았습니다.")
    return GuardResult(True)


async def prohibited_detected(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    row = await _latest_classification(session, subject.id)
    if row is None or not row.prohibited_features:
        return GuardResult(False, "자동 차단 항목이 감지되지 않았습니다.")
    return GuardResult(True)


async def expert_not_confirmed(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    row = await _latest_classification(session, subject.id)
    if row is None:
        return GuardResult(False, "분류 결과가 없습니다.")
    if row.expert_confirmed:
        return GuardResult(
            False,
            "이미 전문가 확인이 완료된 프로젝트입니다 (EXPERT_CONFIRMED_PROCEED로 진행).",
        )
    return GuardResult(True)


async def expert_confirmed(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    row = await _latest_classification(session, subject.id)
    if row is None or not row.expert_confirmed:
        return GuardResult(False, "전문가 확인이 완료되지 않았습니다.")
    return GuardResult(True)


async def _count_questions(
    session: AsyncSession, project_id: uuid.UUID, status: QuestionStatus
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(RequirementQuestion)
        .where(
            RequirementQuestion.project_id == project_id,
            RequirementQuestion.status == status,
        )
    )
    return int(count or 0)


async def open_questions_exist(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if await _count_questions(session, subject.id, QuestionStatus.OPEN) > 0:
        return GuardResult(True)
    return GuardResult(False, "열려 있는 질문이 없습니다.")


async def no_open_questions(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if await _count_questions(session, subject.id, QuestionStatus.OPEN) == 0:
        return GuardResult(True)
    return GuardResult(False, "아직 답변하지 않은 질문이 남아 있습니다.")


async def answered_question_exists(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if await _count_questions(session, subject.id, QuestionStatus.ANSWERED) > 0:
        return GuardResult(True)
    return GuardResult(False, "저장된 답변이 없습니다.")


def _approval_guard(approval_type: ApprovalType, decision: ApprovalDecision | None) -> GuardFn:
    async def guard(session: AsyncSession, subject: Any, ctx: dict[str, Any]) -> GuardResult:
        stmt = select(func.count()).select_from(UserApproval).where(
            UserApproval.project_id == _project_id_of(subject),
            UserApproval.approval_type == approval_type,
        )
        if decision is not None:
            stmt = stmt.where(UserApproval.decision == decision)
        else:
            stmt = stmt.where(UserApproval.decision != ApprovalDecision.APPROVED)
        count = await session.scalar(stmt)
        if int(count or 0) > 0:
            return GuardResult(True)
        return GuardResult(False, f"{approval_type} 승인 레코드가 없습니다.")

    return guard


async def _document_exists(
    session: AsyncSession, project_id: uuid.UUID, doc_type: str
) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(ProjectDocument)
        .where(
            ProjectDocument.project_id == project_id,
            ProjectDocument.kind == "GENERATED",
            ProjectDocument.doc_type == doc_type,
        )
    )
    return int(count or 0) > 0


async def prd_document_exists(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if await _document_exists(session, subject.id, "PRD"):
        return GuardResult(True)
    return GuardResult(False, "PRD 산출물이 생성되지 않았습니다.")


async def backlog_document_exists(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    if await _document_exists(session, subject.id, "BACKLOG"):
        return GuardResult(True)
    return GuardResult(False, "Backlog 산출물이 생성되지 않았습니다.")


async def capability_no_gap(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    missing = ctx.get("capability_missing")
    if missing is None:
        return GuardResult(False, "Capability Gap 분석 결과가 컨텍스트에 없습니다.")
    if missing:
        return GuardResult(False, f"부족한 Capability가 있습니다: {', '.join(missing)}")
    return GuardResult(True)


async def capability_gap_exists(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    missing = ctx.get("capability_missing")
    if missing is None:
        return GuardResult(False, "Capability Gap 분석 결과가 컨텍스트에 없습니다.")
    if not missing:
        return GuardResult(False, "Capability Gap이 없습니다.")
    return GuardResult(True)


async def checkpoint_exists(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    subject_type = ctx["_subject_type"]
    stmt = (
        select(func.count())
        .select_from(WorkflowCheckpoint)
        .where(
            WorkflowCheckpoint.subject_type == subject_type,
            WorkflowCheckpoint.subject_id == subject.id,
        )
    )
    count = await session.scalar(stmt)
    if int(count or 0) > 0:
        return GuardResult(True)
    return GuardResult(False, "복귀할 체크포인트가 없습니다.")


async def expert_confirmed_with_checkpoint(
    session: AsyncSession, subject: Any, ctx: dict[str, Any]
) -> GuardResult:
    confirmed = await expert_confirmed(session, subject, ctx)
    if not confirmed.ok:
        return confirmed
    return await checkpoint_exists(session, subject, ctx)


def _policy_decision_guard(expected: PolicyDecision) -> GuardFn:
    """Policy Engine(결정론적)이 내린 판정이 이 전환을 인가하는지 검증한다 (spec 04 §16).

    판정 값은 ctx["policy_decision"]로 전달된다. Policy Engine만 이 값을 계산하며,
    LLM/Agent는 fire()를 호출하지 않는다. 잘못된 이벤트를 쏘면 Guard가 거부(안전 실패).
    """

    async def guard(session: AsyncSession, subject: Any, ctx: dict[str, Any]) -> GuardResult:
        decision = ctx.get("policy_decision")
        if decision == expected:
            return GuardResult(True)
        return GuardResult(
            False,
            f"Policy Engine 판정({decision})이 이 전환({expected})을 인가하지 않습니다.",
        )

    return guard


async def can_retry(session: AsyncSession, subject: Any, ctx: dict[str, Any]) -> GuardResult:
    cp = await checkpoint_exists(session, subject, ctx)
    if not cp.ok:
        return cp
    max_retries: int = ctx["_max_retries"]
    subject_type: str = ctx["_subject_type"]
    count = await session.scalar(
        select(func.count())
        .select_from(WorkflowEvent)
        .where(
            WorkflowEvent.subject_type == subject_type,
            WorkflowEvent.subject_id == subject.id,
            WorkflowEvent.event == "RETRY_SCHEDULED",
        )
    )
    if int(count or 0) >= max_retries:
        return GuardResult(
            False,
            f"재시도 한도({max_retries}회)를 초과했습니다. "
            "범위 축소 / 중단 / 개발자에게 물어볼 자료 만들기 중에서 선택해 주세요.",
        )
    return GuardResult(True)


# ── Registry ───────────────────────────────────────────────────────


class GuardRegistry:
    def __init__(self) -> None:
        self._guards: dict[str, GuardFn] = {
            "has_planning_input": has_planning_input,
            "classification_saved": classification_saved,
            "prohibited_detected": prohibited_detected,
            "expert_not_confirmed": expert_not_confirmed,
            "expert_confirmed": expert_confirmed,
            "expert_confirmed_with_checkpoint": expert_confirmed_with_checkpoint,
            "open_questions_exist": open_questions_exist,
            "no_open_questions": no_open_questions,
            "answered_question_exists": answered_question_exists,
            "requirements_approval_exists": _approval_guard(
                ApprovalType.REQUIREMENTS, ApprovalDecision.APPROVED
            ),
            "requirements_change_request_exists": _approval_guard(
                ApprovalType.REQUIREMENTS, None
            ),
            "reduced_scope_approval_exists": _approval_guard(
                ApprovalType.REDUCED_SCOPE, ApprovalDecision.APPROVED
            ),
            "expansion_approval_exists": _approval_guard(
                ApprovalType.EXPANSION, ApprovalDecision.APPROVED
            ),
            "plan_approval_exists": _approval_guard(
                ApprovalType.PLAN, ApprovalDecision.APPROVED
            ),
            "result_approval_exists": _approval_guard(
                ApprovalType.RESULT, ApprovalDecision.APPROVED
            ),
            "prd_document_exists": prd_document_exists,
            "backlog_document_exists": backlog_document_exists,
            "capability_no_gap": capability_no_gap,
            "capability_gap_exists": capability_gap_exists,
            "checkpoint_exists": checkpoint_exists,
            "can_retry": can_retry,
            # Policy Engine 4단 판정 Guard (Phase 7에서 deferred:policy-engine@phase7 대체)
            "policy_decision_auto_approve": _policy_decision_guard(
                PolicyDecision.AUTO_APPROVE
            ),
            "policy_decision_user_approval": _policy_decision_guard(
                PolicyDecision.USER_APPROVAL
            ),
            "policy_decision_expert_required": _policy_decision_guard(
                PolicyDecision.EXPERT_REQUIRED
            ),
            "policy_decision_auto_blocked": _policy_decision_guard(
                PolicyDecision.AUTO_BLOCKED
            ),
        }

    def known_names(self) -> set[str]:
        return set(self._guards)

    async def evaluate(
        self, name: str, session: AsyncSession, subject: Any, ctx: dict[str, Any]
    ) -> GuardResult:
        if name.startswith("deferred:"):
            # 미구현 위장 금지 원칙에 따라 통과 사실을 명시적으로 로그에 남긴다.
            logger.info(
                "guard_deferred",
                guard=name,
                subject_id=str(subject.id),
                note="해당 Phase에서 실제 Guard로 교체 예정",
            )
            return GuardResult(True, f"deferred guard: {name}")
        guard = self._guards.get(name)
        if guard is None:
            return GuardResult(False, f"알 수 없는 Guard: {name}")
        return await guard(session, subject, ctx)
