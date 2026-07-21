"""agent_definitions 테이블 — Agent Registry (spec 04 §16).

Core Agent는 이 테이블에 직접 쓰지 못한다. Agent Factory(코드)만 등록한다.
정의 전문은 JSON으로 보존하고, 조회·수명주기 제어에 필요한 필드는 컬럼으로 승격한다.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import AgentStatus
from app.db.base import Base


class AgentDefinitionRecord(Base):
    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("agent_id", "project_id", name="uq_agent_definition_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AgentStatus.REGISTERED
    )
    lifecycle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_after_project: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
