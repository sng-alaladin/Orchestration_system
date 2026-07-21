"""MCP Registry 스키마 (spec 04 §17)."""

from pydantic import BaseModel, Field

from app.core.enums import DataClassification, McpStatus, RiskLevel
from app.db.models.mcp_server import McpServer


class McpToolSpec(BaseModel):
    name: str
    write: bool = False
    requires_user_approval: bool = False


class McpServerSpec(BaseModel):
    id: str
    name: str
    status: McpStatus = McpStatus.APPROVED
    risk_level: RiskLevel = RiskLevel.LOW
    data_classification: DataClassification = DataClassification.INTERNAL
    external_network: bool = False
    read_permissions: list[str] = Field(default_factory=list)
    write_permissions: list[str] = Field(default_factory=list)
    tools: list[McpToolSpec] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: McpServer) -> "McpServerSpec":
        return cls(
            id=record.server_id,
            name=record.name,
            status=McpStatus(record.status),
            risk_level=RiskLevel(record.risk_level),
            data_classification=DataClassification(record.data_classification),
            external_network=record.external_network,
            read_permissions=list(record.read_permissions),
            write_permissions=list(record.write_permissions),
            tools=[
                McpToolSpec(
                    name=t.name, write=t.write, requires_user_approval=t.requires_user_approval
                )
                for t in record.tools
            ],
        )
