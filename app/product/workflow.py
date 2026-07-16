"""Product Definition Workflow — 결정론적 오케스트레이션 (Phase 2 Mock 수준).

상태 이름과 전환은 IMPLEMENTATION_PLAN.md §6.1/6.3을 따른다.
- 상태 변경은 이 모듈의 코드로만 수행한다 (LLM이 상태를 바꾸지 않는다).
- 선언적 전환 테이블·체크포인트·Audit Log는 Phase 4(세션 3)에서 정식 구현하며,
  여기서는 허용 전이 집합으로 불법 전이만 차단한다.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.config import Settings
from app.core.enums import (
    ApprovalDecision,
    ApprovalType,
    ClassificationGate,
    DecisionSource,
    DocumentKind,
    DocumentType,
    ProductState,
    QuestionStatus,
    RequirementCategory,
    RequirementStatus,
)
from app.core.exceptions import AppError
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_document import ProjectDocument
from app.db.models.project_requirement import ProjectRequirement
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.observability.logging import get_logger
from app.product.backlog_generator import render_backlog_markdown
from app.product.classifier import Classifier
from app.product.core_agent import CoreAgent, MockCoreAgent
from app.product.question_generator import build_question_cards
from app.product.requirement_agent import MockRequirementAgent, RequirementAgent
from app.product.schemas import CoreAnalysis, ProjectInput, RequirementDraft, RequirementSet
from app.product.specification_agent import MockSpecificationAgent, SpecificationAgent
from app.project_memory.conflict_detector import DecisionConflict
from app.project_memory.service import ProjectMemoryService

logger = get_logger(__name__)


class IllegalTransitionError(AppError):
    """허용되지 않은 상태 전이."""


class WorkflowStateError(AppError):
    """현재 상태에서 수행할 수 없는 요청 (사용자 언어 메시지 포함)."""


_LEGAL_TRANSITIONS: set[tuple[str, str]] = {
    (ProductState.IDEA_RECEIVED, ProductState.DOCUMENT_ANALYZING),
    # AUTO_BLOCKED_BY_POLICY → ALTERNATIVE_ACCEPTED (축소 기획으로 재분석)
    (ProductState.AUTO_BLOCKED_BY_POLICY, ProductState.DOCUMENT_ANALYZING),
    (ProductState.DOCUMENT_ANALYZING, ProductState.CLASSIFYING),
    (ProductState.CLASSIFYING, ProductState.REQUIREMENT_DRAFTING),
    (ProductState.CLASSIFYING, ProductState.WAITING_APPROVAL),
    (ProductState.CLASSIFYING, ProductState.WAITING_EXPERT_CONFIRMATION),
    (ProductState.CLASSIFYING, ProductState.AUTO_BLOCKED_BY_POLICY),
    (ProductState.CLASSIFYING, ProductState.CANCELLED),
    (ProductState.WAITING_APPROVAL, ProductState.REQUIREMENT_DRAFTING),
    (ProductState.WAITING_APPROVAL, ProductState.CANCELLED),
    (ProductState.REQUIREMENT_DRAFTING, ProductState.WAITING_REQUIREMENT_INPUT),
    (ProductState.REQUIREMENT_DRAFTING, ProductState.WAITING_REQUIREMENT_APPROVAL),
    (ProductState.WAITING_REQUIREMENT_INPUT, ProductState.REQUIREMENT_DRAFTING),
    (ProductState.WAITING_REQUIREMENT_APPROVAL, ProductState.SPECIFICATION_GENERATING),
    (ProductState.WAITING_REQUIREMENT_APPROVAL, ProductState.REQUIREMENT_DRAFTING),
    (ProductState.SPECIFICATION_GENERATING, ProductState.CAPABILITY_ANALYZING),
    (ProductState.CAPABILITY_ANALYZING, ProductState.BACKLOG_GENERATING),
    # BOOTSTRAPPING(신규 Repo)은 Phase 8 범위 — 현재는 바로 READY_FOR_DEVELOPMENT
    (ProductState.BACKLOG_GENERATING, ProductState.READY_FOR_DEVELOPMENT),
}


def build_workflow(session: AsyncSession, settings: Settings) -> "ProductDefinitionWorkflow":
    if settings.agent_mode != "mock":
        # 미구현 기능 위장 금지: live 모드는 Phase 9(Model Adapter)에서 제공된다.
        raise AppError(
            f"agent_mode={settings.agent_mode!r}는 아직 지원되지 않는다. "
            "Phase 9 전까지는 'mock'만 사용 가능하다."
        )
    return ProductDefinitionWorkflow(
        session=session,
        classifier=Classifier(),
        core_agent=MockCoreAgent(),
        requirement_agent=MockRequirementAgent(),
        specification_agent=MockSpecificationAgent(),
    )


class ProductDefinitionWorkflow:
    def __init__(
        self,
        session: AsyncSession,
        classifier: Classifier,
        core_agent: CoreAgent,
        requirement_agent: RequirementAgent,
        specification_agent: SpecificationAgent,
    ) -> None:
        self._session = session
        self._classifier = classifier
        self._core = core_agent
        self._requirement = requirement_agent
        self._specification = specification_agent
        self._memory = ProjectMemoryService(session)

    # ── 1) 기획안 분석 + 적합도 분류 게이트 ─────────────────────────

    async def run_analysis(self, project: Project) -> Project:
        if project.status not in (
            ProductState.IDEA_RECEIVED,
            ProductState.AUTO_BLOCKED_BY_POLICY,
        ):
            raise WorkflowStateError(
                "이 프로젝트는 이미 분석이 시작되었습니다. 현재 단계에서 계속 진행해 주세요."
            )
        project_input = await self._collect_input(project)
        if not project_input.combined_text:
            raise WorkflowStateError(
                "분석할 기획 내용이 없습니다. 기획안 내용을 입력하거나 문서를 올려 주세요."
            )

        self._set_status(project, ProductState.DOCUMENT_ANALYZING)
        analysis = await self._core.analyze(project_input)

        self._set_status(project, ProductState.CLASSIFYING)
        classification = self._classifier.classify(project_input.combined_text)
        self._session.add(
            ProjectClassification(
                project_id=project.id,
                automation_class=classification.automation_class,
                gate=classification.gate,
                reasons=classification.reasons,
                prohibited_features=classification.prohibited_features,
                risky_features=classification.risky_features,
                user_message=classification.user_message,
            )
        )
        await self._session.flush()

        match classification.gate:
            case ClassificationGate.BLOCKED:
                self._set_status(
                    project, ProductState.AUTO_BLOCKED_BY_POLICY, classification.user_message
                )
            case ClassificationGate.UNSUPPORTED:
                self._set_status(project, ProductState.CANCELLED, classification.user_message)
            case ClassificationGate.NEEDS_EXPERT:
                # 상담 패키지 생성은 Phase 7(세션 4) 범위 — 상태와 사유만 기록한다.
                self._set_status(
                    project,
                    ProductState.WAITING_EXPERT_CONFIRMATION,
                    classification.user_message,
                )
            case ClassificationGate.NEEDS_APPROVAL:
                self._set_status(
                    project, ProductState.WAITING_APPROVAL, classification.user_message
                )
            case ClassificationGate.PROCEED:
                await self._draft_requirements(project, analysis)
        return project

    # ── 2) 요구사항 초안 + 질문 카드 ────────────────────────────────

    async def _draft_requirements(self, project: Project, analysis: CoreAnalysis) -> None:
        if project.status != ProductState.REQUIREMENT_DRAFTING:
            self._set_status(project, ProductState.REQUIREMENT_DRAFTING)
        answers = await self._collect_answers(project.id)
        requirement_set: RequirementSet = await self._requirement.refine(analysis, answers)

        conflicts = await self._memory.detect_conflicts(project.id, requirement_set.requirements)
        await self._memory.requirements.sync(
            project.id, requirement_set.requirements, change_reason="요구사항 초안 갱신"
        )
        await self._upsert_questions(project.id, requirement_set)
        await self._create_conflict_questions(project.id, conflicts)

        open_count = await self._count_open_questions(project.id)
        if open_count > 0:
            self._set_status(
                project,
                ProductState.WAITING_REQUIREMENT_INPUT,
                f"확인이 필요한 질문 {open_count}건에 답해 주세요.",
            )
        else:
            self._set_status(
                project,
                ProductState.WAITING_REQUIREMENT_APPROVAL,
                "정리된 요구사항을 확인하고 승인해 주세요.",
            )

    async def redraft(self, project: Project) -> Project:
        """답변 완료 또는 수정 요청 후 요구사항을 다시 정리한다."""
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        await self._draft_requirements(project, analysis)
        return project

    # ── 3) 질문 답변 ────────────────────────────────────────────────

    async def answer_question(
        self, project: Project, question_key: str, answer: str, user: User
    ) -> Project:
        if project.status != ProductState.WAITING_REQUIREMENT_INPUT:
            raise WorkflowStateError("지금은 질문에 답하는 단계가 아닙니다.")
        stmt = select(RequirementQuestion).where(
            RequirementQuestion.project_id == project.id,
            RequirementQuestion.question_key == question_key,
        )
        question = (await self._session.execute(stmt)).scalar_one_or_none()
        if question is None:
            raise WorkflowStateError("해당 질문을 찾을 수 없습니다.")
        if question.status == QuestionStatus.ANSWERED:
            raise WorkflowStateError("이미 답변한 질문입니다.")

        question.answer = answer
        question.status = QuestionStatus.ANSWERED
        question.answered_at = utc_now()
        await self._memory.decisions.add(
            project.id,
            title=question.question,
            decision=answer,
            reason=f"질문 {question.question_key}에 대한 사용자 답변",
            source=DecisionSource.USER_CONFIRMED,
        )
        await self._session.flush()

        if await self._count_open_questions(project.id) == 0:
            await self.redraft(project)
        return project

    # ── 4) 승인 처리 ────────────────────────────────────────────────

    async def decide_requirements(
        self,
        project: Project,
        user: User,
        decision: ApprovalDecision,
        comment: str | None,
    ) -> Project:
        if project.status != ProductState.WAITING_REQUIREMENT_APPROVAL:
            raise WorkflowStateError("지금은 요구사항 승인 단계가 아닙니다.")
        self._session.add(
            UserApproval(
                project_id=project.id,
                user_id=user.id,
                approval_type=ApprovalType.REQUIREMENTS,
                target_ref="requirements",
                decision=decision,
                comment=comment,
            )
        )
        await self._session.flush()

        if decision == ApprovalDecision.APPROVED:
            await self._generate_specification(project)
        else:
            if comment:
                await self._memory.feedback.add(
                    project.id, user.id, comment, category="requirement_review"
                )
            self._set_status(project, ProductState.REQUIREMENT_DRAFTING)
            await self.redraft(project)
        return project

    async def decide_reduced_scope(
        self,
        project: Project,
        user: User,
        decision: ApprovalDecision,
        comment: str | None,
    ) -> Project:
        if project.status != ProductState.WAITING_APPROVAL:
            raise WorkflowStateError("지금은 축소 범위 승인 단계가 아닙니다.")
        self._session.add(
            UserApproval(
                project_id=project.id,
                user_id=user.id,
                approval_type=ApprovalType.REDUCED_SCOPE,
                target_ref="reduced_scope",
                decision=decision,
                comment=comment,
            )
        )
        await self._session.flush()

        if decision == ApprovalDecision.APPROVED:
            classification = await self._latest_classification(project.id)
            excluded = ", ".join(classification.risky_features) if classification else ""
            await self._memory.decisions.add(
                project.id,
                title="위험 기능을 제외한 축소 범위로 진행",
                decision=f"첫 버전에서 제외: {excluded}" if excluded else "축소 범위로 진행",
                reason=comment,
                source=DecisionSource.USER_CONFIRMED,
            )
            project_input = await self._collect_input(project)
            analysis = await self._core.analyze(project_input)
            await self._draft_requirements(project, analysis)
        else:
            self._set_status(
                project,
                ProductState.CANCELLED,
                "축소 범위 제안이 거절되어 프로젝트를 중단했습니다. "
                "기획을 수정해 새로 시작할 수 있습니다.",
            )
        return project

    # ── 5) 명세(PRD) + Backlog 생성 ────────────────────────────────

    async def _generate_specification(self, project: Project) -> None:
        self._set_status(project, ProductState.SPECIFICATION_GENERATING)
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        requirements = await self._memory.requirements.list_active(project.id)
        # DB 상태를 기준으로 명세를 생성한다 (승인된 내용 그대로)
        drafts = [_to_draft(r) for r in requirements]
        decisions = [
            (d.title, d.decision) for d in await self._memory.decisions.list_active(project.id)
        ]
        spec = await self._specification.generate(
            project_name=project.name,
            project_goal=analysis.project_goal,
            deliverable_type=analysis.deliverable_type,
            requirements=drafts,
            decisions=decisions,
        )
        await self._save_generated_document(
            project, DocumentType.PRD, "PRD.md", spec.prd_markdown
        )

        # Capability Gap 분석은 Phase 5(세션 3) 범위 — 현재는 기존 역량으로 충분하다고
        # 판정하는 통과 스텁이며, 그 사실을 로그로 남긴다.
        self._set_status(project, ProductState.CAPABILITY_ANALYZING)
        logger.info(
            "capability_analysis_stub",
            project_id=str(project.id),
            note="Phase 5에서 Gap Analyzer로 대체 예정 (현재: NO_GAP_FOUND 고정)",
        )

        self._set_status(project, ProductState.BACKLOG_GENERATING)
        backlog_md = render_backlog_markdown(project.name, spec)
        await self._save_generated_document(
            project, DocumentType.BACKLOG, "BACKLOG.md", backlog_md
        )

        self._set_status(
            project,
            ProductState.READY_FOR_DEVELOPMENT,
            "요구사항이 승인되어 개발 준비가 끝났습니다. PRD와 Backlog를 확인할 수 있습니다.",
        )

    # ── 내부 유틸 ───────────────────────────────────────────────────

    def _set_status(
        self, project: Project, new_status: ProductState, reason: str | None = None
    ) -> None:
        current = ProductState(project.status)
        if (current, new_status) not in _LEGAL_TRANSITIONS:
            raise IllegalTransitionError(f"불법 상태 전이: {current} → {new_status}")
        logger.info(
            "product_state_changed",
            project_id=str(project.id),
            from_state=str(current),
            to_state=str(new_status),
        )
        project.status = new_status
        project.status_reason = reason

    async def _collect_input(self, project: Project) -> ProjectInput:
        stmt = (
            select(ProjectDocument)
            .where(
                ProjectDocument.project_id == project.id,
                ProjectDocument.kind == DocumentKind.UPLOADED,
            )
            .order_by(ProjectDocument.created_at)
        )
        documents = (await self._session.execute(stmt)).scalars().all()
        return ProjectInput(
            project_name=project.name,
            idea_text=project.idea_text or "",
            document_texts=[d.content for d in documents],
        )

    async def _collect_answers(self, project_id: uuid.UUID) -> dict[str, str]:
        stmt = select(RequirementQuestion).where(
            RequirementQuestion.project_id == project_id,
            RequirementQuestion.status == QuestionStatus.ANSWERED,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {q.question_key: q.answer or "" for q in rows}

    async def _upsert_questions(
        self, project_id: uuid.UUID, requirement_set: RequirementSet
    ) -> None:
        cards = build_question_cards(requirement_set)
        stmt = select(RequirementQuestion.question_key).where(
            RequirementQuestion.project_id == project_id
        )
        existing = {key for (key,) in (await self._session.execute(stmt)).all()}
        for card in cards:
            if card.key not in existing:
                self._session.add(
                    RequirementQuestion(
                        project_id=project_id,
                        question_key=card.key,
                        question=card.question,
                        reason=card.reason,
                        related_requirement_key=card.related_requirement_key,
                    )
                )
        await self._session.flush()

    async def _create_conflict_questions(
        self, project_id: uuid.UUID, conflicts: list[DecisionConflict]
    ) -> None:
        if not conflicts:
            return
        stmt = select(RequirementQuestion.question_key).where(
            RequirementQuestion.project_id == project_id
        )
        existing = {key for (key,) in (await self._session.execute(stmt)).all()}
        for conflict in conflicts:
            key = f"Q-C{conflict.decision_key.removeprefix('DEC-')}"[:20]
            if key in existing:
                continue
            self._session.add(
                RequirementQuestion(
                    project_id=project_id,
                    question_key=key,
                    question=conflict.message,
                    reason="기존 결정과 충돌 가능성이 감지되었습니다.",
                    related_requirement_key=conflict.requirement_key,
                )
            )
        await self._session.flush()

    async def _count_open_questions(self, project_id: uuid.UUID) -> int:
        stmt = select(RequirementQuestion).where(
            RequirementQuestion.project_id == project_id,
            RequirementQuestion.status == QuestionStatus.OPEN,
        )
        return len((await self._session.execute(stmt)).scalars().all())

    async def _latest_classification(
        self, project_id: uuid.UUID
    ) -> ProjectClassification | None:
        stmt = (
            select(ProjectClassification)
            .where(ProjectClassification.project_id == project_id)
            .order_by(ProjectClassification.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _save_generated_document(
        self, project: Project, doc_type: DocumentType, filename: str, content: str
    ) -> ProjectDocument:
        document = ProjectDocument(
            project_id=project.id,
            user_id=project.user_id,
            kind=DocumentKind.GENERATED,
            doc_type=doc_type,
            filename=filename,
            content_type="text/markdown",
            content=content,
        )
        self._session.add(document)
        await self._session.flush()
        return document


def _to_draft(requirement: ProjectRequirement) -> RequirementDraft:
    return RequirementDraft(
        key=requirement.req_key,
        description=requirement.description,
        status=RequirementStatus(requirement.status),
        category=RequirementCategory(requirement.category),
        priority=requirement.priority,
    )
