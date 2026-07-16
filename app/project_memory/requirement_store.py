"""project_requirements 저장 — 버전 관리 포함.

동일 req_key의 내용·상태가 바뀌면 version을 올리고 requirement_versions에 기록한다.
초안에서 사라진 요구사항은 삭제하지 않고 is_active=False로 보존한다.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_requirement import ProjectRequirement
from app.product.schemas import RequirementDraft
from app.project_memory.version_store import VersionStore


class RequirementStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._versions = VersionStore(session)

    async def list_active(self, project_id: uuid.UUID) -> list[ProjectRequirement]:
        stmt = (
            select(ProjectRequirement)
            .where(
                ProjectRequirement.project_id == project_id,
                ProjectRequirement.is_active.is_(True),
            )
            .order_by(ProjectRequirement.req_key)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def sync(
        self,
        project_id: uuid.UUID,
        drafts: list[RequirementDraft],
        change_reason: str,
    ) -> list[ProjectRequirement]:
        """초안 전체를 현재 상태로 동기화한다 (생성/갱신/비활성화 + 버전 기록)."""
        stmt = select(ProjectRequirement).where(ProjectRequirement.project_id == project_id)
        result = await self._session.execute(stmt)
        existing = {r.req_key: r for r in result.scalars().all()}

        synced: list[ProjectRequirement] = []
        draft_keys: set[str] = set()
        for draft in drafts:
            draft_keys.add(draft.key)
            current = existing.get(draft.key)
            if current is None:
                current = ProjectRequirement(
                    project_id=project_id,
                    req_key=draft.key,
                    category=draft.category,
                    description=draft.description,
                    status=draft.status,
                    priority=draft.priority,
                    version=1,
                    is_active=True,
                )
                self._session.add(current)
                await self._session.flush()
                await self._versions.record(current, change_reason)
            elif (
                current.description != draft.description
                or current.status != draft.status
                or current.category != draft.category
                or current.priority != draft.priority
                or not current.is_active
            ):
                current.description = draft.description
                current.status = draft.status
                current.category = draft.category
                current.priority = draft.priority
                current.is_active = True
                current.version += 1
                await self._session.flush()
                await self._versions.record(current, change_reason)
            synced.append(current)

        for req_key, requirement in existing.items():
            if req_key not in draft_keys and requirement.is_active:
                requirement.is_active = False
                requirement.version += 1
                await self._versions.record(requirement, f"{change_reason} (초안에서 제외됨)")
        await self._session.flush()
        return synced
