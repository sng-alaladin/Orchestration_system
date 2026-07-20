"""workflow_events 테이블 — 적용된 상태 전환 이벤트 (Idempotency Key 포함).

동일 idempotency_key의 이벤트는 한 번만 적용된다 (spec 07 §23.4, 10 §40).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        Index("ix_workflow_events_subject", "subject_type", "subject_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    machine: Mapped[str] = mapped_column(String(20), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    from_state: Mapped[str] = mapped_column(String(40), nullable=False)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
