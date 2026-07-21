"""Agent Registry — 검증·판정을 통과한 Agent Definition을 저장·조회한다 (spec 04 §16).

Core Agent는 여기에 직접 쓰지 못한다. AgentFactory(코드)만 register()를 호출한다.
Lifecycle: project_scoped Agent는 프로젝트 종료 시 만료(expire_for_project) 처리한다.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AgentDefinition
from app.core.enums import AgentStatus
from app.db.models.agent_definition import AgentDefinitionRecord


class AgentRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self, agent_id: str, project_id: uuid.UUID | None
    ) -> AgentDefinitionRecord | None:
        stmt = select(AgentDefinitionRecord).where(
            AgentDefinitionRecord.agent_id == agent_id,
            AgentDefinitionRecord.project_id == project_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_project(
        self, project_id: uuid.UUID
    ) -> list[AgentDefinitionRecord]:
        stmt = (
            select(AgentDefinitionRecord)
            .where(AgentDefinitionRecord.project_id == project_id)
            .order_by(AgentDefinitionRecord.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def register(
        self,
        definition: AgentDefinition,
        *,
        project_id: uuid.UUID | None,
        status: AgentStatus = AgentStatus.ACTIVE,
    ) -> AgentDefinitionRecord:
        """정의를 등록하거나(멱등) 같은 (agent_id, project_id)면 갱신한다."""
        existing = await self.get(definition.id, project_id)
        payload = definition.model_dump(mode="json")
        if existing is not None:
            existing.name = definition.name
            existing.version = definition.version
            existing.status = status
            existing.lifecycle_type = definition.lifecycle.type
            existing.expires_after_project = definition.lifecycle.expires_after_project
            existing.definition = payload
            await self._session.flush()
            return existing

        record = AgentDefinitionRecord(
            agent_id=definition.id,
            project_id=project_id,
            name=definition.name,
            version=definition.version,
            status=status,
            lifecycle_type=definition.lifecycle.type,
            expires_after_project=definition.lifecycle.expires_after_project,
            definition=payload,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def expire_for_project(self, project_id: uuid.UUID) -> int:
        """프로젝트 종료 시 project_scoped Agent를 만료 처리한다. 반환: 만료 건수."""
        records = await self.list_for_project(project_id)
        count = 0
        for record in records:
            if record.expires_after_project and record.status != AgentStatus.EXPIRED:
                record.status = AgentStatus.EXPIRED
                count += 1
        await self._session.flush()
        return count
