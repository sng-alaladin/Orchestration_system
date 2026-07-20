"""Capability Registry — 시스템이 제공 가능한 역량과 Provider 관리 (spec 04 §18).

configs/capabilities.yaml 을 DB(capabilities/capability_providers)로 동기화한다(멱등).
Core Agent는 Registry에 직접 쓰지 못한다 — 등록·동기화는 이 서비스(코드)만 수행한다.
"""

from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.schemas import CapabilitySpec, ProviderSpec
from app.db.models.capability import Capability, CapabilityProvider
from app.observability.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CAPABILITIES_PATH = Path("configs") / "capabilities.yaml"


def load_capability_specs(path: Path = DEFAULT_CAPABILITIES_PATH) -> list[CapabilitySpec]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    specs: list[CapabilitySpec] = []
    for name, body in (raw.get("capabilities") or {}).items():
        body = body or {}
        specs.append(
            CapabilitySpec(
                name=str(name),
                description=body.get("description"),
                providers=[ProviderSpec(**p) for p in (body.get("providers") or [])],
            )
        )
    return specs


class CapabilityRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count(self) -> int:
        result = await self._session.scalar(select(func.count()).select_from(Capability))
        return int(result or 0)

    async def get_by_name(self, name: str) -> Capability | None:
        stmt = select(Capability).where(Capability.name == name)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[Capability]:
        stmt = select(Capability).order_by(Capability.name)
        return list((await self._session.execute(stmt)).scalars().all())

    async def upsert(self, spec: CapabilitySpec) -> Capability:
        capability = await self.get_by_name(spec.name)
        if capability is None:
            capability = Capability(name=spec.name, description=spec.description)
            self._session.add(capability)
            await self._session.flush()
        elif spec.description and capability.description != spec.description:
            capability.description = spec.description

        stmt = select(CapabilityProvider).where(
            CapabilityProvider.capability_id == capability.id
        )
        existing = {p.provider_name: p for p in (await self._session.execute(stmt)).scalars()}
        for provider in spec.providers:
            current = existing.get(provider.name)
            if current is None:
                self._session.add(
                    CapabilityProvider(
                        capability_id=capability.id,
                        provider_name=provider.name,
                        provider_type=provider.type,
                        status=provider.status,
                        priority=provider.priority,
                    )
                )
            else:
                current.provider_type = provider.type
                current.status = provider.status
                current.priority = provider.priority
        await self._session.flush()
        return capability

    async def sync_from_config(self, path: Path = DEFAULT_CAPABILITIES_PATH) -> int:
        """설정 파일의 역량 정의를 DB로 동기화한다(멱등). 반환: 처리한 capability 수."""
        specs = load_capability_specs(path)
        for spec in specs:
            await self.upsert(spec)
        logger.info("capability_registry_synced", count=len(specs), path=str(path))
        return len(specs)

    async def ensure_seeded(self, path: Path = DEFAULT_CAPABILITIES_PATH) -> None:
        """Registry가 비어 있으면 설정 파일로 초기화한다 (테스트·최초 기동 대응)."""
        if await self.count() == 0:
            await self.sync_from_config(path)
