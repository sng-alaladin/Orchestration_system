"""Decision Log (spec 06 §20.1) — 모든 중요한 결정을 저장한다."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DecisionSource, DecisionStatus
from app.db.models.project_decision import ProjectDecision


class DecisionLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        project_id: uuid.UUID,
        *,
        title: str,
        decision: str,
        reason: str | None = None,
        source: DecisionSource = DecisionSource.USER_CONFIRMED,
    ) -> ProjectDecision:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ProjectDecision)
            .where(ProjectDecision.project_id == project_id)
        )
        entry = ProjectDecision(
            project_id=project_id,
            decision_key=f"DEC-{int(count or 0) + 1:03d}",
            title=title[:200],
            decision=decision,
            reason=reason,
            source=source,
            status=DecisionStatus.ACTIVE,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_active(self, project_id: uuid.UUID) -> list[ProjectDecision]:
        stmt = (
            select(ProjectDecision)
            .where(
                ProjectDecision.project_id == project_id,
                ProjectDecision.status == DecisionStatus.ACTIVE,
            )
            .order_by(ProjectDecision.decision_key)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def supersede(self, decision: ProjectDecision) -> None:
        decision.status = DecisionStatus.SUPERSEDED
        await self._session.flush()
