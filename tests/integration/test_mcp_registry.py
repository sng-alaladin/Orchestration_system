"""MCP Registry / Allowlist / 연결 Proposal / Health Check 테스트 (Phase 7)."""

from pathlib import Path

from app.core.enums import McpStatus, McpUsageType
from app.db.session import SessionFactory
from app.mcp.allowlist import McpAllowlist
from app.mcp.connection import build_connection_proposal
from app.mcp.health import check_health
from app.mcp.registry import McpRegistry
from app.mcp.schemas import McpServerSpec

SERVERS = Path("configs") / "mcp-servers.yaml"
ALLOWLIST = Path("configs") / "mcp-allowlist.yaml"


async def test_sync_from_config_is_idempotent(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = McpRegistry(session)
        first = await registry.sync_from_config(SERVERS)
        assert first > 0
        count_after = await registry.count()
        second = await registry.sync_from_config(SERVERS)
        assert second == first
        assert await registry.count() == count_after, "재동기화 시 서버 중복 생성 없음"
        # 도구도 중복 생성되지 않는다
        jira = await registry.get("jira-mcp")
        assert jira is not None
        assert len({t.name for t in jira.tools}) == len(jira.tools)
        await session.commit()


async def test_allowlist_membership() -> None:
    allowlist = McpAllowlist.load(ALLOWLIST)
    assert allowlist.contains("jira-mcp")
    assert allowlist.contains("internal-docs-mcp")
    assert not allowlist.contains("gmail-mcp")
    assert not allowlist.contains("internal-settlement-mcp")


async def test_usage_type_classification(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = McpRegistry(session)
        await registry.sync_from_config(SERVERS)

        docs = McpServerSpec.from_record(await _get(registry, "internal-docs-mcp"))
        jira = McpServerSpec.from_record(await _get(registry, "jira-mcp"))
        gmail = McpServerSpec.from_record(await _get(registry, "gmail-mcp"))

        # 유형 A: 기존 승인 MCP 읽기 전용 활성화
        a = build_connection_proposal(docs, in_allowlist=True, write_intent=False)
        assert a.usage_type == McpUsageType.A_READONLY_ACTIVATE
        # 유형 B: 기존 MCP 쓰기 기능 활성화
        b = build_connection_proposal(jira, in_allowlist=True, write_intent=True)
        assert b.usage_type == McpUsageType.B_WRITE_ACTIVATE
        # 유형 C: 신규 외부 MCP 연결 (PROPOSED 상태)
        c = build_connection_proposal(gmail, in_allowlist=False, write_intent=True)
        assert c.usage_type == McpUsageType.C_NEW_EXTERNAL


async def test_health_check_blocks_external_network(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        registry = McpRegistry(session)
        await registry.sync_from_config(SERVERS)
        docs = McpServerSpec.from_record(await _get(registry, "internal-docs-mcp"))
        assert check_health(docs).healthy is True

        external = McpServerSpec(
            id="x-mcp", name="외부", status=McpStatus.PROPOSED, external_network=True
        )
        assert check_health(external).healthy is False


async def _get(registry: McpRegistry, server_id: str):
    server = await registry.get(server_id)
    assert server is not None
    return server
