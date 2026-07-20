"""Capability Registry / Matcher / Gap Analyzer 테스트 (Phase 5)."""

from pathlib import Path

from app.capabilities.gap_analyzer import GapAnalyzer
from app.capabilities.matcher import CapabilityMatcher
from app.capabilities.registry import CapabilityRegistry
from app.capabilities.schemas import CapabilitySpec, ProviderSpec
from app.core.enums import ProviderType
from app.db.session import SessionFactory

CONFIG_PATH = Path("configs") / "capabilities.yaml"


async def test_sync_from_config_is_idempotent(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = CapabilityRegistry(session)
        first = await registry.sync_from_config(CONFIG_PATH)
        assert first > 0
        count_after_first = await registry.count()

        second = await registry.sync_from_config(CONFIG_PATH)
        assert second == first
        assert await registry.count() == count_after_first, "재동기화 시 중복 생성 없음"
        await session.commit()


async def test_matcher_prefers_agent_and_priority(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = CapabilityRegistry(session)
        await registry.upsert(
            CapabilitySpec(
                name="test-cap",
                description="테스트",
                providers=[
                    ProviderSpec(name="some-library", type=ProviderType.LIBRARY, priority=10),
                    ProviderSpec(name="some-agent", type=ProviderType.AGENT, priority=10),
                    ProviderSpec(name="cheap-agent", type=ProviderType.AGENT, priority=50),
                ],
            )
        )
        matches = await CapabilityMatcher(session).match(["test-cap"])
        matched = matches["test-cap"]
        assert matched is not None
        # 같은 priority에서는 AGENT 우선 (기존 Agent 재사용 우선)
        assert matched.provider_name == "some-agent"
        assert matched.provider_type == ProviderType.AGENT


async def test_unavailable_providers_are_skipped(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = CapabilityRegistry(session)
        await registry.upsert(
            CapabilitySpec(
                name="paused-cap",
                providers=[
                    ProviderSpec(
                        name="paused-agent", type=ProviderType.AGENT, status="disabled"
                    )
                ],
            )
        )
        matches = await CapabilityMatcher(session).match(["paused-cap"])
        assert matches["paused-cap"] is None


async def test_gap_analyzer_detects_missing(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = CapabilityRegistry(session)
        await registry.sync_from_config(CONFIG_PATH)

        result = await GapAnalyzer(session).analyze(
            ["excel-read", "document-generate", "email-send"]
        )
        assert result.has_gap
        assert result.missing == ["email-send"], "email-send는 의도적으로 미등록 (세션 4 확장 대상)"
        assert {m.capability for m in result.matched} == {"excel-read", "document-generate"}


async def test_gap_analyzer_no_gap_for_registered(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = CapabilityRegistry(session)
        await registry.sync_from_config(CONFIG_PATH)
        result = await GapAnalyzer(session).analyze(["excel-read", "general-automation"])
        assert not result.has_gap
        assert result.missing == []
