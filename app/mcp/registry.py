"""MCP Registry — configs/mcp-servers.yaml 을 DB로 멱등 동기화 (spec 04 §17).

Core Agent는 직접 쓰지 못한다. 서버·도구 등록/상태 변경은 이 서비스(코드)만 수행한다.
"""

from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import DataClassification, McpStatus, RiskLevel
from app.db.models.mcp_server import McpServer, McpTool
from app.mcp.schemas import McpServerSpec, McpToolSpec
from app.observability.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MCP_SERVERS_PATH = Path("configs") / "mcp-servers.yaml"


def load_mcp_specs(path: Path = DEFAULT_MCP_SERVERS_PATH) -> list[McpServerSpec]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    specs: list[McpServerSpec] = []
    for server_id, body in (raw.get("servers") or {}).items():
        body = body or {}
        specs.append(
            McpServerSpec(
                id=str(server_id),
                name=body.get("name", str(server_id)),
                status=McpStatus(body.get("status", "APPROVED")),
                risk_level=RiskLevel(body.get("risk_level", "LOW")),
                data_classification=DataClassification(
                    body.get("data_classification", "INTERNAL")
                ),
                external_network=bool(body.get("external_network", False)),
                read_permissions=list(body.get("read_permissions") or []),
                write_permissions=list(body.get("write_permissions") or []),
                tools=[McpToolSpec(**t) for t in (body.get("tools") or [])],
            )
        )
    return specs


class McpRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count(self) -> int:
        result = await self._session.scalar(select(func.count()).select_from(McpServer))
        return int(result or 0)

    async def get(self, server_id: str) -> McpServer | None:
        stmt = (
            select(McpServer)
            .where(McpServer.server_id == server_id)
            .options(selectinload(McpServer.tools))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[McpServer]:
        stmt = (
            select(McpServer).order_by(McpServer.server_id).options(selectinload(McpServer.tools))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def upsert(self, spec: McpServerSpec) -> McpServer:
        server = await self.get(spec.id)  # tools eager-load 포함
        is_new = server is None
        if server is None:
            server = McpServer(server_id=spec.id)
            self._session.add(server)
        server.name = spec.name
        server.status = spec.status
        server.risk_level = spec.risk_level
        server.data_classification = spec.data_classification
        server.external_network = spec.external_network
        server.read_permissions = list(spec.read_permissions)
        server.write_permissions = list(spec.write_permissions)
        await self._session.flush()

        # 신규 서버는 lazy 접근을 피한다(eager 상태만 사용, async lazy-load 방지)
        existing = {} if is_new else {t.name: t for t in server.tools}
        for tool in spec.tools:
            current = existing.get(tool.name)
            if current is None:
                self._session.add(
                    McpTool(
                        server_pk=server.id,
                        name=tool.name,
                        write=tool.write,
                        requires_user_approval=tool.requires_user_approval,
                    )
                )
            else:
                current.write = tool.write
                current.requires_user_approval = tool.requires_user_approval
        await self._session.flush()
        return server

    async def sync_from_config(self, path: Path = DEFAULT_MCP_SERVERS_PATH) -> int:
        specs = load_mcp_specs(path)
        for spec in specs:
            await self.upsert(spec)
        logger.info("mcp_registry_synced", count=len(specs), path=str(path))
        return len(specs)

    async def ensure_seeded(self, path: Path = DEFAULT_MCP_SERVERS_PATH) -> None:
        if await self.count() == 0:
            await self.sync_from_config(path)

    async def set_status(self, server_id: str, status: McpStatus) -> McpServer | None:
        server = await self.get(server_id)
        if server is None:
            return None
        server.status = status
        await self._session.flush()
        return server
