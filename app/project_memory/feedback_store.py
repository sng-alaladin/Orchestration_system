"""project_feedback 저장."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_feedback import ProjectFeedback


class FeedbackStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        category: str = "general",
    ) -> ProjectFeedback:
        feedback = ProjectFeedback(
            project_id=project_id, user_id=user_id, content=content, category=category
        )
        self._session.add(feedback)
        await self._session.flush()
        return feedback

    async def list_for_project(self, project_id: uuid.UUID) -> list[ProjectFeedback]:
        stmt = (
            select(ProjectFeedback)
            .where(ProjectFeedback.project_id == project_id)
            .order_by(ProjectFeedback.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
