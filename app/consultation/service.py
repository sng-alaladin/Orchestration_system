"""ConsultationService — 상담 패키지 영속화 + 답변 기록 (spec 05 §19.5).

패키지 본문은 마스킹된 상태로만 저장한다. 게이트 해제/조정 등 상태 전환은
Product/Development Workflow가 상태 머신을 통해 수행한다(여기서는 기록만).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.consultation.package import ConsultationContext, ConsultationPackage, build_package
from app.core.clock import utc_now
from app.core.enums import AuditEventType, ConsultationStatus, ConsultationTrigger
from app.db.models.expert_consultation import ExpertConsultation
from app.observability.logging import get_logger
from app.orchestrator.audit import AuditLogger

logger = get_logger(__name__)


class ConsultationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditLogger(session)

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        trigger: ConsultationTrigger,
        context: ConsultationContext,
        task_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> ExpertConsultation:
        package: ConsultationPackage = build_package(context)
        consultation = ExpertConsultation(
            project_id=project_id,
            task_id=task_id,
            trigger=trigger,
            status=ConsultationStatus.PENDING,
            title=package.title,
            package_markdown=package.markdown,
            questions=package.questions,
            answers=[],
            masking_summary=package.masking_summary,
        )
        self._session.add(consultation)
        await self._session.flush()
        await self._audit.record(
            event_type=AuditEventType.CONSULTATION_CREATED,
            subject_type="task" if task_id else "project",
            subject_id=task_id or project_id,
            actor_type="user" if actor_id else "system",
            actor_id=actor_id,
            reason=f"상담 패키지 생성(trigger={trigger}), 마스킹 항목={package.masking_summary}",
        )
        logger.info(
            "consultation_created",
            project_id=str(project_id),
            trigger=str(trigger),
            masking=package.masking_summary,
        )
        return consultation

    async def latest_for_project(
        self, project_id: uuid.UUID
    ) -> ExpertConsultation | None:
        stmt = (
            select(ExpertConsultation)
            .where(ExpertConsultation.project_id == project_id)
            .order_by(ExpertConsultation.created_at.desc(), ExpertConsultation.id.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def record_answer(
        self,
        consultation: ExpertConsultation,
        *,
        question_key: str,
        answer: str,
        action: str,
        actor_id: uuid.UUID | None = None,
    ) -> ExpertConsultation:
        now = utc_now()
        entry = {
            "question_key": question_key,
            "answer": answer,
            "action": action,
            "answered_at": now.isoformat(),
        }
        # JSON 컬럼은 재할당으로 변경을 추적한다.
        consultation.answers = [*consultation.answers, entry]
        consultation.status = ConsultationStatus.ANSWERED
        consultation.answered_at = now
        await self._session.flush()
        await self._audit.record(
            event_type=AuditEventType.EXPERT_ANSWER_RECORDED,
            subject_type="project",
            subject_id=consultation.project_id,
            actor_type="user" if actor_id else "system",
            actor_id=actor_id,
            reason=f"자문 답변 기록: {question_key} → {action}",
        )
        return consultation

    async def mark_applied(self, consultation: ExpertConsultation) -> ExpertConsultation:
        consultation.status = ConsultationStatus.APPLIED
        consultation.resolved_at = utc_now()
        await self._session.flush()
        return consultation
