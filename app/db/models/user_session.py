"""sessions 테이블 — 로그인 세션 (spec 02 §3.4, 06 §35).

쿠키 토큰 원문은 저장하지 않고 SHA-256 해시만 저장한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now
from app.db.base import Base
from app.db.models.user import User


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, default=None)

    user: Mapped[User] = relationship(back_populates="sessions")
