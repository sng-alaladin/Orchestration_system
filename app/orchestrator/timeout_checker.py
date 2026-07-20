"""대기 상태 타임아웃 감시.

configs/state-timeouts.yaml 에 정의된 대기 상태가 제한 시간을 초과하면
사용자 알림 이벤트(TIMEOUT_NOTIFIED)를 Audit Log에 기록한다. **상태는 바꾸지 않는다.**
(주기 실행 Worker는 Phase 14에서 연결한다 — 여기서는 검사기만 제공)
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditEventType
from app.db.models.audit_log import AuditLog
from app.db.models.workflow_event import WorkflowEvent
from app.orchestrator.audit import AuditLogger

DEFAULT_TIMEOUTS_PATH = Path("configs") / "state-timeouts.yaml"


@dataclass(frozen=True)
class TimeoutNotification:
    subject_type: str
    subject_id: uuid.UUID
    state: str
    entered_at: datetime
    limit_seconds: int


class TimeoutChecker:
    def __init__(
        self, session: AsyncSession, timeouts_path: Path = DEFAULT_TIMEOUTS_PATH
    ) -> None:
        self._session = session
        self._audit = AuditLogger(session)
        with open(timeouts_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self._limits: dict[str, int] = {
            str(state): int(seconds) for state, seconds in (raw.get("timeouts") or {}).items()
        }

    def limit_for(self, state: str) -> int | None:
        return self._limits.get(state)

    async def check(
        self, subject_type: str, subject_id: uuid.UUID, state: str, now: datetime
    ) -> TimeoutNotification | None:
        """현재 상태가 제한 시간을 넘겼으면 1회 알림을 기록하고 반환한다."""
        limit = self._limits.get(state)
        if limit is None:
            return None

        entered_at = await self._state_entered_at(subject_type, subject_id, state)
        if entered_at is None or now - entered_at <= timedelta(seconds=limit):
            return None

        if await self._already_notified(subject_type, subject_id, state, entered_at):
            return None

        await self._audit.record(
            event_type=AuditEventType.TIMEOUT_NOTIFIED,
            subject_type=subject_type,
            subject_id=subject_id,
            from_state=state,
            to_state=state,
            reason=(
                f"'{state}' 상태가 {limit}초를 초과했습니다. "
                "확인이 필요한 항목이 기다리고 있어요."
            ),
        )
        return TimeoutNotification(
            subject_type=subject_type,
            subject_id=subject_id,
            state=state,
            entered_at=entered_at,
            limit_seconds=limit,
        )

    async def _state_entered_at(
        self, subject_type: str, subject_id: uuid.UUID, state: str
    ) -> datetime | None:
        stmt = (
            select(WorkflowEvent.created_at)
            .where(
                WorkflowEvent.subject_type == subject_type,
                WorkflowEvent.subject_id == subject_id,
                WorkflowEvent.to_state == state,
            )
            .order_by(WorkflowEvent.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _already_notified(
        self, subject_type: str, subject_id: uuid.UUID, state: str, entered_at: datetime
    ) -> bool:
        stmt = (
            select(AuditLog.id)
            .where(
                AuditLog.subject_type == subject_type,
                AuditLog.subject_id == subject_id,
                AuditLog.event_type == AuditEventType.TIMEOUT_NOTIFIED,
                AuditLog.from_state == state,
                AuditLog.occurred_at >= entered_at,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
