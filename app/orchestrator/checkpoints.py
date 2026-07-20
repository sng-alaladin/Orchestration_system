"""체크포인트 저장소 — 예외 상태 진입 직전 상태를 저장하고 복귀에 사용한다."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow_checkpoint import WorkflowCheckpoint


class CheckpointStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        subject_type: str,
        subject_id: uuid.UUID,
        state: str,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowCheckpoint:
        checkpoint = WorkflowCheckpoint(
            subject_type=subject_type,
            subject_id=subject_id,
            state=state,
            payload=payload or {},
        )
        self._session.add(checkpoint)
        await self._session.flush()
        return checkpoint

    async def latest(
        self, subject_type: str, subject_id: uuid.UUID
    ) -> WorkflowCheckpoint | None:
        stmt = (
            select(WorkflowCheckpoint)
            .where(
                WorkflowCheckpoint.subject_type == subject_type,
                WorkflowCheckpoint.subject_id == subject_id,
            )
            .order_by(WorkflowCheckpoint.created_at.desc(), WorkflowCheckpoint.id.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
