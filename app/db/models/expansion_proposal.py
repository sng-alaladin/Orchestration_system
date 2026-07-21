"""expansion_proposals 테이블 — 확장 Proposal과 Policy Engine 판정 기록 (감사).

확장 흐름(제안 → 판정 → 등록/차단/자문)의 근거를 남긴다. 상태 머신 Guard는
이 판정을 신뢰의 원천으로 삼지 않고 ctx로 전달받은 결정을 검증한다(이 표는 감사·조회용).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.enums import ExpansionStatus
from app.db.base import Base


class ExpansionProposalRecord(Base):
    __tablename__ = "expansion_proposals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # ProposalType
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # PolicyDecision
    matched_rule: Mapped[str] = mapped_column(String(60), nullable=False)
    policy_reason: Mapped[str] = mapped_column(Text(), nullable=False)
    alternatives: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    signals: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExpansionStatus.PROPOSED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
