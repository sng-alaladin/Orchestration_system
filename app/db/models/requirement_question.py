"""requirement_questions 테이블 — 비개발자용 질문 카드."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import QuestionStatus
from app.db.base import Base


class RequirementQuestion(Base):
    __tablename__ = "requirement_questions"
    __table_args__ = (UniqueConstraint("project_id", "question_key", name="uq_question_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_key: Mapped[str] = mapped_column(String(20), nullable=False)  # Q-001 등
    question: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    related_requirement_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    answer: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=QuestionStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
