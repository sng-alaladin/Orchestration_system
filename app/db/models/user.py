"""users 테이블 (spec 06 — 핵심 데이터 모델)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user_session import UserSession


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
