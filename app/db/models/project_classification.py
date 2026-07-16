"""project_classification 테이블 — 적합도 분류 결과 (spec 01 §37)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


class ProjectClassification(Base):
    __tablename__ = "project_classification"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    automation_class: Mapped[str] = mapped_column(String(40), nullable=False)
    gate: Mapped[str] = mapped_column(String(20), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    prohibited_features: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    risky_features: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    user_message: Mapped[str] = mapped_column(Text(), nullable=False)
    # 전문가 확인 완료 플래그 — 재분류 무한 루프 방지 (IMPLEMENTATION_PLAN §6.1/6.3)
    expert_confirmed: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
