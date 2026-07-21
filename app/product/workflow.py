"""Product Definition Workflow — 결정론적 오케스트레이션.

상태 변경은 전부 Orchestrator 상태 머신(`app/orchestrator/`)의 fire()로 수행한다.
전환의 단일 진실 원천은 `app/orchestrator/transitions.py` 이며,
이 모듈은 어떤 이벤트를 언제 발생시킬지(비즈니스 순서)만 결정한다.
LLM(Agent)은 구조화 결과만 반환하고 상태를 변경하지 않는다.
"""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.gap_analyzer import GapAnalyzer
from app.capabilities.registry import CapabilityRegistry
from app.consultation.package import ConsultationContext, ConsultationOption, ConsultationQuestion
from app.consultation.service import ConsultationService
from app.core.clock import utc_now
from app.core.config import Settings
from app.core.enums import (
    ApprovalDecision,
    ApprovalType,
    ClassificationGate,
    ConsultationTrigger,
    DecisionSource,
    DocumentKind,
    DocumentType,
    PolicyDecision,
    ProductState,
    QuestionStatus,
    RequirementCategory,
    RequirementStatus,
)
from app.core.exceptions import AppError
from app.db.models.expert_consultation import ExpertConsultation
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_document import ProjectDocument
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.expansion.service import ExpansionResolution, build_expansion_service
from app.observability.logging import get_logger
from app.orchestrator.product_state_machine import build_product_state_machine
from app.orchestrator.state_machine import StateMachine
from app.product.backlog_generator import render_backlog_markdown
from app.product.classifier import Classifier
from app.product.core_agent import CoreAgent, MockCoreAgent
from app.product.question_generator import build_question_cards
from app.product.requirement_agent import MockRequirementAgent, RequirementAgent
from app.product.schemas import (
    CoreAnalysis,
    ProjectInput,
    RequirementDraft,
    RequirementSet,
    SpecificationResult,
)
from app.product.specification_agent import MockSpecificationAgent, SpecificationAgent
from app.project_memory.conflict_detector import DecisionConflict
from app.project_memory.service import ProjectMemoryService

logger = get_logger(__name__)

# 전문가 자문 답변의 처리 방향 (spec 05 §19.3)
ANSWER_UNBLOCK = "UNBLOCK"  # 게이트 해제 후 진행
ANSWER_ADJUST_SCOPE = "ADJUST_SCOPE"  # 범위 조정 후 재계획
ANSWER_STOP = "STOP"  # 중단
ANSWER_RESOLUTIONS = frozenset({ANSWER_UNBLOCK, ANSWER_ADJUST_SCOPE, ANSWER_STOP})


class WorkflowStateError(AppError):
    """현재 상태에서 수행할 수 없는 요청 (사용자 언어 메시지 포함)."""


def build_workflow(session: AsyncSession, settings: Settings) -> "ProductDefinitionWorkflow":
    if settings.agent_mode != "mock":
        # 미구현 기능 위장 금지: live 모드는 Phase 9(Model Adapter)에서 제공된다.
        raise AppError(
            f"agent_mode={settings.agent_mode!r}는 아직 지원되지 않는다. "
            "Phase 9 전까지는 'mock'만 사용 가능하다."
        )
    return ProductDefinitionWorkflow(
        session=session,
        settings=settings,
        classifier=Classifier(),
        core_agent=MockCoreAgent(),
        requirement_agent=MockRequirementAgent(),
        specification_agent=MockSpecificationAgent(),
    )


class ProductDefinitionWorkflow:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        classifier: Classifier,
        core_agent: CoreAgent,
        requirement_agent: RequirementAgent,
        specification_agent: SpecificationAgent,
    ) -> None:
        self._session = session
        self._settings = settings
        self._classifier = classifier
        self._core = core_agent
        self._requirement = requirement_agent
        self._specification = specification_agent
        self._memory = ProjectMemoryService(session)
        self._consultation = ConsultationService(session)
        self._expansion = build_expansion_service(session, settings)
        self._machine: StateMachine = build_product_state_machine(
            session, max_retries=settings.max_retry_attempts
        )

    # ── 1) 기획안 분석 + 적합도 분류 게이트 ─────────────────────────

    async def run_analysis(self, project: Project, actor_id: uuid.UUID | None = None) -> Project:
        if project.status == ProductState.IDEA_RECEIVED:
            entry_event = "ANALYSIS_STARTED"
        elif project.status == ProductState.AUTO_BLOCKED_BY_POLICY:
            # §6.3: ALTERNATIVE_ACCEPTED — 수정된 기획으로 재분석 (재분류 게이트 재통과 필수)
            entry_event = "ALTERNATIVE_ACCEPTED"
        else:
            raise WorkflowStateError(
                "이 프로젝트는 이미 분석이 시작되었습니다. 현재 단계에서 계속 진행해 주세요."
            )

        await self._fire(project, entry_event, actor_id=actor_id)
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        await self._fire(project, "ANALYSIS_COMPLETED", actor_id=actor_id)

        classification = self._classifier.classify(project_input.combined_text)
        previous = await self._latest_classification(project.id)
        carried_expert_confirmed = bool(previous and previous.expert_confirmed)
        self._session.add(
            ProjectClassification(
                project_id=project.id,
                automation_class=classification.automation_class,
                gate=classification.gate,
                reasons=classification.reasons,
                prohibited_features=classification.prohibited_features,
                risky_features=classification.risky_features,
                user_message=classification.user_message,
                # 전문가 확인 완료 이력은 재분류 시에도 유지한다 (무한 루프 방지)
                expert_confirmed=carried_expert_confirmed,
            )
        )
        await self._session.flush()

        match classification.gate:
            case ClassificationGate.BLOCKED:
                await self._fire(
                    project, "PROHIBITED_SCOPE_DETECTED",
                    reason=classification.user_message, actor_id=actor_id,
                )
            case ClassificationGate.UNSUPPORTED:
                await self._fire(
                    project, "CLASSIFIED_UNSUPPORTED",
                    reason=classification.user_message, actor_id=actor_id,
                )
            case ClassificationGate.NEEDS_EXPERT:
                if carried_expert_confirmed:
                    # 이미 전문가 확인이 끝난 프로젝트 — 재차 대기시키지 않는다 (§6.1)
                    await self._fire(project, "EXPERT_CONFIRMED_PROCEED", actor_id=actor_id)
                    await self._draft_requirements(project, analysis, actor_id)
                else:
                    await self._create_gate_consultation(project, analysis, classification)
                    await self._fire(
                        project, "CLASSIFIED_EXPERT_REVIEW",
                        reason=(
                            f"{classification.user_message}\n"
                            "개발자에게 전달할 상담 자료를 생성했습니다. 자문 화면에서 "
                            "다운로드/복사해 전달하고, 답변을 입력하면 진행을 재개합니다."
                        ),
                        actor_id=actor_id,
                    )
            case ClassificationGate.NEEDS_APPROVAL:
                await self._fire(
                    project, "CLASSIFIED_AI_ASSISTED",
                    reason=classification.user_message, actor_id=actor_id,
                )
            case ClassificationGate.PROCEED:
                await self._fire(project, "CLASSIFIED_SELF_SERVICE", actor_id=actor_id)
                await self._draft_requirements(project, analysis, actor_id)
        return project

    # ── 2) 요구사항 초안 + 질문 카드 ────────────────────────────────

    async def _draft_requirements(
        self, project: Project, analysis: CoreAnalysis, actor_id: uuid.UUID | None
    ) -> None:
        assert project.status == ProductState.REQUIREMENT_DRAFTING, (
            f"요구사항 초안은 REQUIREMENT_DRAFTING에서만 작성한다 (현재: {project.status})"
        )
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
            await self._fire(
                project, "DRAFT_HAS_UNKNOWNS",
                reason=f"확인이 필요한 질문 {open_count}건에 답해 주세요.",
                actor_id=actor_id,
            )
        else:
            await self._fire(
                project, "DRAFT_COMPLETED",
                reason="정리된 요구사항을 확인하고 승인해 주세요.",
                actor_id=actor_id,
            )

    async def redraft(self, project: Project, actor_id: uuid.UUID | None = None) -> Project:
        """답변 완료 또는 수정 요청 후 요구사항을 다시 정리한다."""
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        await self._draft_requirements(project, analysis, actor_id)
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
            await self._fire(project, "USER_ANSWERED", actor_id=user.id)
            await self.redraft(project, actor_id=user.id)
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
            await self._fire(project, "REQUIREMENTS_APPROVED", actor_id=user.id)
            await self._generate_specification(project, actor_id=user.id)
        else:
            if comment:
                await self._memory.feedback.add(
                    project.id, user.id, comment, category="requirement_review"
                )
            await self._fire(project, "CHANGES_REQUESTED", actor_id=user.id)
            await self.redraft(project, actor_id=user.id)
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
            await self._fire(project, "APPROVAL_GRANTED", actor_id=user.id)
            await self.redraft(project, actor_id=user.id)
        else:
            await self._fire(
                project, "APPROVAL_DENIED",
                reason=(
                    "축소 범위 제안이 거절되어 프로젝트를 중단했습니다. "
                    "기획을 수정해 새로 시작할 수 있습니다."
                ),
                actor_id=user.id,
            )
        return project

    async def decide_expansion(
        self,
        project: Project,
        user: User,
        decision: ApprovalDecision,
        comment: str | None,
    ) -> Project:
        """확장 Proposal 사용자 승인 (WAITING_EXPANSION_APPROVAL)."""
        if project.status != ProductState.WAITING_EXPANSION_APPROVAL:
            raise WorkflowStateError("지금은 확장 승인 단계가 아닙니다.")
        self._session.add(
            UserApproval(
                project_id=project.id,
                user_id=user.id,
                approval_type=ApprovalType.EXPANSION,
                target_ref="expansion",
                decision=decision,
                comment=comment,
            )
        )
        await self._session.flush()

        if decision == ApprovalDecision.APPROVED:
            # 승인된 사용자-승인 확장을 활성화한 뒤 Backlog 생성으로 진행
            await self._activate_pending_expansions(project)
            await self._fire(project, "EXPANSION_APPROVED", actor_id=user.id)
            spec = await self._rebuild_spec(project)
            await self._generate_backlog(project, spec, user.id)
        else:
            await self._fire(
                project, "EXPANSION_DENIED",
                reason=(
                    "확장 제안이 거절되었습니다. 기존 기능만으로 범위를 줄여 다시 진행하거나 "
                    "중단할 수 있습니다."
                ),
                actor_id=user.id,
            )
        return project

    # ── 자문 답변 반영 (전문가 확인 게이트 해제/조정/중단) ──────────

    async def apply_consultation_answer(
        self,
        project: Project,
        user: User,
        question_key: str,
        answer: str,
        resolution: str,
    ) -> Project:
        if project.status != ProductState.WAITING_EXPERT_CONFIRMATION:
            raise WorkflowStateError("지금은 전문가 자문 답변을 반영하는 단계가 아닙니다.")
        if resolution not in ANSWER_RESOLUTIONS:
            raise WorkflowStateError(
                "답변 방향은 진행(UNBLOCK)/범위조정(ADJUST_SCOPE)/중단(STOP) 중 하나여야 합니다."
            )
        consultation = await self._consultation.latest_for_project(project.id)
        if consultation is None:
            raise WorkflowStateError("연결된 상담 패키지를 찾을 수 없습니다.")
        action_text = {
            ANSWER_UNBLOCK: "게이트 해제 후 진행",
            ANSWER_ADJUST_SCOPE: "범위 조정 후 재작성",
            ANSWER_STOP: "중단",
        }[resolution]
        await self._consultation.record_answer(
            consultation, question_key=question_key, answer=answer,
            action=action_text, actor_id=user.id,
        )

        if resolution == ANSWER_STOP:
            await self._fire(
                project, "EXPERT_ANSWER_STOPS",
                reason="개발자 자문 결과에 따라 프로젝트를 중단했습니다.", actor_id=user.id,
            )
        elif resolution == ANSWER_ADJUST_SCOPE:
            await self._fire(
                project, "EXPERT_ANSWER_ADJUSTS_SCOPE",
                reason="개발자 자문 결과에 따라 범위를 조정해 요구사항을 다시 정리합니다.",
                actor_id=user.id,
            )
            await self.redraft(project, actor_id=user.id)
        else:  # UNBLOCK
            await self._unblock_after_expert(project, consultation, user)
        await self._consultation.mark_applied(consultation)
        return project

    async def _unblock_after_expert(
        self, project: Project, consultation: ExpertConsultation, user: User
    ) -> None:
        """전문가 확인 완료 → 체크포인트 복귀 후 진행 (spec 05 §19.3)."""
        # expert_confirmed 플래그 설정 (게이트 재진입 방지 + Guard 통과 근거)
        classification = await self._latest_classification(project.id)
        if classification is not None:
            classification.expert_confirmed = True
            await self._session.flush()

        await self._fire(
            project, "EXPERT_ANSWER_UNBLOCKS",
            reason="개발자 확인이 완료되어 진행을 재개합니다.", actor_id=user.id,
        )
        # 체크포인트 복귀 지점에 따라 이어서 진행
        if project.status == ProductState.CLASSIFYING:
            await self._fire(project, "EXPERT_CONFIRMED_PROCEED", actor_id=user.id)
            await self.redraft(project, actor_id=user.id)
        elif project.status == ProductState.EXPANSION_PROPOSING:
            # 전문가가 확장 연결을 승인 → 대기 중이던 확장을 활성화하고 진행
            await self._activate_pending_expansions(project)
            await self._fire(
                project, "PROPOSAL_AUTO_APPROVED",
                context={"policy_decision": PolicyDecision.AUTO_APPROVE.value},
                reason="개발자 확인이 완료되어 확장을 반영하고 개발 준비를 진행합니다.",
                actor_id=user.id,
            )
            spec = await self._rebuild_spec(project)
            await self._generate_backlog(project, spec, user.id)

    # ── 5) 명세(PRD) + Capability Gap + Backlog ────────────────────

    async def _build_spec(self, project: Project) -> SpecificationResult:
        """활성 요구사항·결정으로 명세(PRD 등)를 생성한다 (부작용 없음)."""
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        requirements = await self._memory.requirements.list_active(project.id)
        drafts = [
            RequirementDraft(
                key=r.req_key,
                description=r.description,
                status=RequirementStatus(r.status),
                category=RequirementCategory(r.category),
                priority=r.priority,
            )
            for r in requirements
        ]
        decisions = [
            (d.title, d.decision) for d in await self._memory.decisions.list_active(project.id)
        ]
        return await self._specification.generate(
            project_name=project.name,
            project_goal=analysis.project_goal,
            deliverable_type=analysis.deliverable_type,
            requirements=drafts,
            decisions=decisions,
        )

    async def _rebuild_spec(self, project: Project) -> SpecificationResult:
        return await self._build_spec(project)

    async def _generate_specification(
        self, project: Project, actor_id: uuid.UUID | None
    ) -> None:
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        spec = await self._build_spec(project)
        await self._save_generated_document(
            project, DocumentType.PRD, "PRD.md", spec.prd_markdown
        )
        await self._fire(project, "SPEC_COMPLETED", actor_id=actor_id)

        # Capability Gap 분석 (Phase 5)
        registry = CapabilityRegistry(self._session)
        await registry.ensure_seeded(Path(self._settings.capabilities_config))
        gap = await GapAnalyzer(self._session).analyze(analysis.required_capabilities)
        gap_ctx: dict[str, object] = {"capability_missing": gap.missing}

        if gap.has_gap:
            await self._fire(project, "GAP_FOUND", context=gap_ctx, actor_id=actor_id)
            await self._resolve_expansion(project, spec, gap.missing, actor_id)
            return

        await self._fire(project, "NO_GAP_FOUND", context=gap_ctx, actor_id=actor_id)
        await self._generate_backlog(project, spec, actor_id)

    async def _generate_backlog(
        self, project: Project, spec: "SpecificationResult", actor_id: uuid.UUID | None
    ) -> None:
        backlog_md = render_backlog_markdown(project.name, spec)
        await self._save_generated_document(
            project, DocumentType.BACKLOG, "BACKLOG.md", backlog_md
        )
        # Repository 부트스트랩(신규 Repo, BACKLOG_READY_NEW_REPO → BOOTSTRAPPING)은
        # Phase 8(세션 5) 범위 — 현재는 기존 Repo 경로만 사용한다.
        await self._fire(
            project, "BACKLOG_READY_EXISTING",
            reason=(
                "요구사항이 승인되어 개발 준비가 끝났습니다. "
                "PRD와 Backlog를 확인할 수 있습니다."
            ),
            actor_id=actor_id,
        )

    # ── 6) 확장 Proposal → Policy 판정 → 라우팅 (Phase 7) ───────────

    async def _resolve_expansion(
        self,
        project: Project,
        spec: SpecificationResult,
        missing: list[str],
        actor_id: uuid.UUID | None,
    ) -> None:
        """EXPANSION_PROPOSING에서 부족 역량을 판정하고 4단 경로로 라우팅한다."""
        resolution = await self._expansion.plan_and_judge(project.id, missing)
        ctx: dict[str, object] = {"policy_decision": resolution.decision.value}

        match resolution.decision:
            case PolicyDecision.AUTO_APPROVE:
                await self._expansion.activate(resolution)
                await self._fire(
                    project, "PROPOSAL_AUTO_APPROVED", context=ctx,
                    reason=resolution.reason or "필요한 확장을 자동으로 준비했습니다.",
                    actor_id=actor_id,
                )
                await self._generate_backlog(project, spec, actor_id)
            case PolicyDecision.USER_APPROVAL:
                await self._fire(
                    project, "PROPOSAL_NEEDS_USER", context=ctx,
                    reason=(
                        f"{resolution.reason}\n"
                        "승인 화면에서 이 확장을 진행할지 결정해 주세요."
                    ),
                    actor_id=actor_id,
                )
            case PolicyDecision.EXPERT_REQUIRED:
                await self._create_expansion_consultation(project, resolution)
                await self._fire(
                    project, "PROPOSAL_NEEDS_EXPERT", context=ctx,
                    reason=resolution.reason,
                    actor_id=actor_id,
                )
            case PolicyDecision.AUTO_BLOCKED:
                alt_text = (
                    "\n대안: " + " / ".join(resolution.alternatives)
                    if resolution.alternatives
                    else ""
                )
                await self._fire(
                    project, "PROPOSAL_BLOCKED", context=ctx,
                    reason=f"{resolution.reason}{alt_text}",
                    actor_id=actor_id,
                )

    async def _activate_pending_expansions(self, project: Project) -> None:
        """대기(PENDING_USER/PENDING_EXPERT) 확장 Proposal을 승인·활성화한다 (서비스 위임)."""
        await self._expansion.approve_pending(project.id)

    # ── 전문가 상담 패키지 생성 ─────────────────────────────────────

    async def create_manual_consultation(
        self, project: Project, user: User
    ) -> ExpertConsultation:
        """사용자가 직접 '개발자에게 물어볼 자료 만들기'를 요청한 경우 (spec 05 §19.5).

        상태를 바꾸지 않는다 — 어떤 단계에서도 자료를 만들 수 있다.
        """
        project_input = await self._collect_input(project)
        analysis = await self._core.analyze(project_input)
        classification = await self._latest_classification(project.id)
        context = ConsultationContext(
            project_name=project.name,
            situation_summary="사용자가 개발자에게 물어볼 자료를 직접 요청했습니다.",
            why_expert_needed=(
                classification.user_message if classification else "사용자 직접 요청"
            ),
            key_questions=[
                ConsultationQuestion(
                    key="MANUAL",
                    question="이 프로젝트에 대해 개발자에게 확인하고 싶은 점을 정리했습니다.",
                    options=[],
                )
            ],
            project_overview=analysis.project_goal,
            requirements_summary=project.idea_text or "",
            failure_point=f"현재 상태: {project.status}",
            environment="Orchestrator (사용자 요청 자문)",
        )
        return await self._consultation.create(
            project_id=project.id,
            trigger=ConsultationTrigger.USER_REQUESTED,
            context=context,
            actor_id=user.id,
        )

    async def _create_gate_consultation(
        self,
        project: Project,
        analysis: CoreAnalysis,
        classification: object,
    ) -> ExpertConsultation:
        """적합도 게이트 전문가 확인용 상담 패키지 (spec 05 §19.3)."""
        user_message = getattr(classification, "user_message", "")
        idea = project.idea_text or ""
        question = ConsultationQuestion(
            key="GATE-EXPERT",
            question="이 프로젝트를 개발자 확인 후 그대로 진행할까요?",
            options=[
                ConsultationOption(
                    label="A. 확인했고 그대로 진행한다",
                    action="자문 화면에서 A(UNBLOCK) 선택 → 게이트 해제 후 요구사항 정리를 진행",
                ),
                ConsultationOption(
                    label="B. 범위를 조정해 진행한다",
                    action="자문 화면에서 B(ADJUST_SCOPE) 선택 → 범위를 조정해 요구사항 재작성",
                ),
                ConsultationOption(
                    label="C. 중단한다",
                    action="자문 화면에서 C(STOP) 선택 → 프로젝트를 중단합니다.",
                ),
            ],
        )
        context = ConsultationContext(
            project_name=project.name,
            situation_summary="이 기획에는 개발자 확인이 필요한 부분이 있어 진행을 멈췄습니다.",
            why_expert_needed=user_message,
            key_questions=[question],
            project_overview=analysis.project_goal,
            requirements_summary=idea,
            failure_point="현재 상태: WAITING_EXPERT_CONFIRMATION (적합도 게이트)",
            environment="Orchestrator Product Definition 단계",
        )
        return await self._consultation.create(
            project_id=project.id,
            trigger=ConsultationTrigger.EXPERT_REQUIRED,
            context=context,
        )

    async def _create_expansion_consultation(
        self, project: Project, resolution: ExpansionResolution
    ) -> ExpertConsultation:
        """확장(신규 연결) 전문가 확인용 상담 패키지 (spec 05 §19.3)."""
        questions = self._expansion.build_expert_questions(resolution)
        context = ConsultationContext(
            project_name=project.name,
            situation_summary="요청하신 기능에 새 외부 연결이 필요해 개발자 확인이 필요합니다.",
            why_expert_needed=resolution.reason,
            key_questions=questions,
            project_overview=project.idea_text or "",
            failure_point="현재 상태: EXPANSION_PROPOSING (확장 연결 — 전문가 확인 필요)",
            environment="Orchestrator Capability 확장 단계",
        )
        return await self._consultation.create(
            project_id=project.id,
            trigger=ConsultationTrigger.EXPERT_REQUIRED,
            context=context,
        )

    # ── 내부 유틸 ───────────────────────────────────────────────────

    async def _fire(
        self,
        project: Project,
        event: str,
        *,
        reason: str | None = None,
        context: dict[str, object] | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> None:
        await self._machine.fire(
            project,
            event,
            reason=reason,
            context=context,
            actor_type="user" if actor_id else "system",
            actor_id=actor_id,
        )

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
            .order_by(ProjectClassification.created_at.desc(), ProjectClassification.id.desc())
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
