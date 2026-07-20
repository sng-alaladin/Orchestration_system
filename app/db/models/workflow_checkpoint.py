"""workflow_checkpoints 테이블 — 예외 상태 진입 직전 상태 저장.

spec 데이터 모델의 task_checkpoints 역할을 Product(project)까지 일반화한 테이블.
예외 상태에서 "직전 상태 (체크포인트)" 복귀의 근거가 된다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


class WorkflowCheckpoint(Base):
    __tablename__ = "workflow_checkpoints"
    __table_args__ = (
        Index("ix_workflow_checkpoints_subject", "subject_type", "subject_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid(), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)  # 복귀 대상 상태
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
