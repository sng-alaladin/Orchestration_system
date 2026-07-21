"""expert_consultations 테이블 — 전문가 상담 패키지·답변 기록 (spec 05 §19.5).

패키지 본문은 Secret 마스킹을 거친 뒤에만 저장한다 (원문 미저장).
질문·답변·조치 결과를 함께 남겨 이후 유사 상황에서 재참조한다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import ConsultationStatus
from app.db.base import Base


class ExpertConsultation(Base):
    __tablename__ = "expert_consultations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)  # ConsultationTrigger
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConsultationStatus.PENDING
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 마스킹 완료된 2계층 패키지 본문 (Markdown)
    package_markdown: Mapped[str] = mapped_column(Text(), nullable=False)
    # 질문 목록: [{key, question, options: [{label, action}]}]
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON(), nullable=False, default=list)
    # 답변 목록: [{question_key, answer, action, answered_at}]
    answers: Mapped[list[dict[str, Any]]] = mapped_column(JSON(), nullable=False, default=list)
    # 마스킹된 항목 요약 (검증·감사용): {"email": 2, "password": 1, ...}
    masking_summary: Mapped[dict[str, int]] = mapped_column(JSON(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
