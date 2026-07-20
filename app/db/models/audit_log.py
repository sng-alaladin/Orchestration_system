"""audit_logs 테이블 — Append-only 감사 기록.

모든 상태 전환·거부·멱등 재생·타임아웃 알림을 기록한다. 수정·삭제하지 않는다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_subject", "subject_type", "subject_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # project/task
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)  # AuditEventType
    event: Mapped[str | None] = mapped_column(String(60), nullable=True)  # 전환 이벤트명
    machine: Mapped[str | None] = mapped_column(String(20), nullable=True)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False, default=dict)
