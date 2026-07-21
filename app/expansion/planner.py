"""ProposalPlanner — 부족 Capability를 해결 Proposal로 변환 (spec 04 §15.1).

expansion-catalog.yaml로 해결 전략을 조회하고, MCP Registry·Allowlist를 참조해
Policy Engine 판정 입력(ExpansionProposal)을 만든다. 카탈로그에 없으면 전문가 확인 대상이다.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import McpUsageType, ProposalType
from app.mcp.allowlist import McpAllowlist
from app.mcp.connection import build_connection_proposal
from app.mcp.registry import McpRegistry
from app.mcp.schemas import McpServerSpec
from app.policy.schemas import ExpansionProposal


@dataclass
class PlannedProposal:
    capability: str
    proposal: ExpansionProposal
    strategy: str  # MCP_CONNECTION | AGENT | UNKNOWN
    usage_type: McpUsageType | None = None
    server_id: str | None = None


def _load_catalog(path: Path) -> dict[str, dict[str, object]]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return dict(raw.get("resolutions") or {})


class ProposalPlanner:
    def __init__(
        self,
        session: AsyncSession,
        *,
        allowlist: McpAllowlist,
        catalog_path: Path,
    ) -> None:
        self._registry = McpRegistry(session)
        self._allowlist = allowlist
        self._catalog = _load_catalog(catalog_path)

    async def plan(self, capability: str) -> PlannedProposal:
        entry = self._catalog.get(capability)
        if entry is None:
            return self._unknown(capability)

        strategy = str(entry.get("strategy", "UNKNOWN"))
        if strategy == "MCP_CONNECTION":
            return await self._plan_mcp(capability, entry)
        # AGENT 전략 등은 Phase 확장 여지 — 현재는 전문가 확인 대상으로 안전 강등
        return self._unknown(capability, strategy=strategy)

    async def _plan_mcp(
        self, capability: str, entry: dict[str, object]
    ) -> PlannedProposal:
        server_id = str(entry.get("mcp_server", ""))
        write_intent = bool(entry.get("write", False))
        record = await self._registry.get(server_id)
        if record is None:
            return self._unknown(capability, strategy="MCP_CONNECTION")
        spec = McpServerSpec.from_record(record)
        conn = build_connection_proposal(
            spec,
            in_allowlist=self._allowlist.contains(server_id),
            write_intent=write_intent,
            reason=f"'{capability}' 역량을 위해 '{spec.name}' 연결/활성화",
        )
        return PlannedProposal(
            capability=capability,
            proposal=conn.proposal,
            strategy="MCP_CONNECTION",
            usage_type=conn.usage_type,
            server_id=server_id,
        )

    def _unknown(self, capability: str, *, strategy: str = "UNKNOWN") -> PlannedProposal:
        # 해결 방법이 정의되지 않은 역량: 개발자가 확인해야 진행 가능
        proposal = ExpansionProposal(
            kind=ProposalType.MCP_CONNECTION,
            name=capability,
            reason=f"'{capability}' 역량을 제공할 방법이 아직 정의되지 않았습니다.",
            is_new_external_connection=True,
            in_allowlist=False,
        )
        return PlannedProposal(
            capability=capability, proposal=proposal, strategy=strategy
        )
