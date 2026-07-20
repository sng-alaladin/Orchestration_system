"""Agent/MCP 매칭 — 요구 Capability에 대해 최적 Provider를 고른다.

우선순위: priority 오름차순 → AGENT > MCP > LIBRARY (기존 Agent 재사용 우선, spec 04 §15.1)
→ 이름순(결정론 보장). status='available'인 Provider만 대상.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.schemas import MatchedProvider
from app.core.enums import ProviderType
from app.db.models.capability import Capability, CapabilityProvider

_TYPE_RANK = {ProviderType.AGENT: 0, ProviderType.MCP: 1, ProviderType.LIBRARY: 2}


class CapabilityMatcher:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def match(self, required: list[str]) -> dict[str, MatchedProvider | None]:
        result: dict[str, MatchedProvider | None] = {}
        for name in required:
            result[name] = await self._match_one(name)
        return result

    async def _match_one(self, capability_name: str) -> MatchedProvider | None:
        stmt = (
            select(CapabilityProvider)
            .join(Capability, Capability.id == CapabilityProvider.capability_id)
            .where(
                Capability.name == capability_name,
                CapabilityProvider.status == "available",
            )
        )
        providers = list((await self._session.execute(stmt)).scalars().all())
        if not providers:
            return None
        best = sorted(
            providers,
            key=lambda p: (
                p.priority,
                _TYPE_RANK.get(ProviderType(p.provider_type), 99),
                p.provider_name,
            ),
        )[0]
        return MatchedProvider(
            capability=capability_name,
            provider_name=best.provider_name,
            provider_type=ProviderType(best.provider_type),
        )
