"""project_decisions 테이블 — Decision Log (spec 06 §20.1)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import DecisionStatus
from app.db.base import Base


class ProjectDecision(Base):
    __tablename__ = "project_decisions"
    __table_args__ = (UniqueConstraint("project_id", "decision_key", name="uq_decision_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    decision_key: Mapped[str] = mapped_column(String(20), nullable=False)  # DEC-001 등
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # user_confirmed/inferred
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DecisionStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
