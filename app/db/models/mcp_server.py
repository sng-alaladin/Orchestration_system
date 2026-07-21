"""mcp_servers / mcp_tools 테이블 — MCP Server·Tool Registry (spec 04 §17).

configs/mcp-servers.yaml 을 DB로 멱등 동기화한다. Core Agent는 직접 쓰지 못한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.core.enums import DataClassification, McpStatus, RiskLevel
from app.db.base import Base


class McpServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=McpStatus.PROPOSED)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default=RiskLevel.LOW)
    data_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataClassification.INTERNAL
    )
    external_network: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    read_permissions: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    write_permissions: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    tools: Mapped[list["McpTool"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class McpTool(Base):
    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint("server_pk", "name", name="uq_mcp_tool"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    server_pk: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("mcp_servers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    write: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False
    )

    server: Mapped[McpServer] = relationship(back_populates="tools")
