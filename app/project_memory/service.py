"""Project Memory Facade — 요구사항·결정·피드백·버전을 한 곳에서 다룬다."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_decision import ProjectDecision
from app.product.schemas import RequirementDraft
from app.project_memory.conflict_detector import DecisionConflict, find_conflicts
from app.project_memory.decision_log import DecisionLog
from app.project_memory.feedback_store import FeedbackStore
from app.project_memory.requirement_store import RequirementStore
from app.project_memory.version_store import VersionStore


class ProjectMemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.requirements = RequirementStore(session)
        self.versions = VersionStore(session)
        self.decisions = DecisionLog(session)
        self.feedback = FeedbackStore(session)

    async def detect_conflicts(
        self, project_id: uuid.UUID, drafts: list[RequirementDraft]
    ) -> list[DecisionConflict]:
        active: list[ProjectDecision] = await self.decisions.list_active(project_id)
        return find_conflicts(drafts, active)
