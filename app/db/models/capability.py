"""capabilities / capability_providers 테이블 (spec 04 §18)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    providers: Mapped[list["CapabilityProvider"]] = relationship(
        back_populates="capability", cascade="all, delete-orphan"
    )


class CapabilityProvider(Base):
    __tablename__ = "capability_providers"
    __table_args__ = (
        UniqueConstraint("capability_id", "provider_name", name="uq_capability_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    capability_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("capabilities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(10), nullable=False)  # AGENT/MCP/LIBRARY
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    # 낮을수록 우선. 기존 자원 재사용 우선순위(spec 04 §15.1)를 표현한다.
    priority: Mapped[int] = mapped_column(Integer(), nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    capability: Mapped[Capability] = relationship(back_populates="providers")
