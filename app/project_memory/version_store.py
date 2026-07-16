"""requirement_versions 기록/조회."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_requirement import ProjectRequirement, RequirementVersion


class VersionStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self, requirement: ProjectRequirement, change_reason: str | None = None
    ) -> RequirementVersion:
        version = RequirementVersion(
            requirement_id=requirement.id,
            version=requirement.version,
            description=requirement.description,
            status=requirement.status,
            change_reason=change_reason,
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def history(self, requirement_id: uuid.UUID) -> list[RequirementVersion]:
        stmt = (
            select(RequirementVersion)
            .where(RequirementVersion.requirement_id == requirement_id)
            .order_by(RequirementVersion.version)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
