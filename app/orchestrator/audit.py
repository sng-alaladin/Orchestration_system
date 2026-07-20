"""Audit Logger — Append-only 감사 기록 (모든 전환·거부·재생·타임아웃)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditEventType
from app.db.models.audit_log import AuditLog
from app.observability.logging import get_logger

logger = get_logger(__name__)


class AuditLogger:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        event_type: AuditEventType,
        subject_type: str,
        subject_id: uuid.UUID,
        machine: str | None = None,
        event: str | None = None,
        from_state: str | None = None,
        to_state: str | None = None,
        actor_type: str = "system",
        actor_id: uuid.UUID | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            machine=machine,
            event=event,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            payload=payload or {},
        )
        self._session.add(entry)
        await self._session.flush()
        logger.info(
            "audit",
            event_type=str(event_type),
            subject_type=subject_type,
            subject_id=str(subject_id),
            transition_event=event,
            from_state=from_state,
            to_state=to_state,
        )
        return entry
