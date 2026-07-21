"""MCP Connection Proposal — MCP 사용 유형 분류 + Policy 판정용 Proposal 생성 (spec 04 §17).

사용 유형(A/B/C/D)을 결정론적으로 분류하고, 위험 신호를 채운 ExpansionProposal을 만든다.
판정 자체는 Policy Engine이 수행한다.
"""

from dataclasses import dataclass

from app.core.enums import McpStatus, McpUsageType, ProposalType
from app.mcp.schemas import McpServerSpec
from app.policy.schemas import ExpansionProposal


@dataclass(frozen=True)
class ConnectionProposal:
    usage_type: McpUsageType
    proposal: ExpansionProposal


def classify_usage_type(
    server: McpServerSpec, *, is_new_connection: bool, write_intent: bool
) -> McpUsageType:
    if is_new_connection and server.external_network:
        return McpUsageType.D_NEW_SERVER  # 신규 외부 네트워크 서버 개발
    if is_new_connection:
        return McpUsageType.C_NEW_EXTERNAL  # 신규 외부 MCP 연결
    if write_intent:
        return McpUsageType.B_WRITE_ACTIVATE  # 기존 MCP 쓰기 기능 활성화
    return McpUsageType.A_READONLY_ACTIVATE  # 기존 MCP 읽기 전용 활성화


def build_connection_proposal(
    server: McpServerSpec,
    *,
    in_allowlist: bool,
    write_intent: bool,
    reason: str = "",
) -> ConnectionProposal:
    """서버 스펙 + allowlist 여부 + 쓰기 의도로 연결 Proposal을 만든다.

    is_new_connection: 아직 승인되지 않은(PROPOSED) 서버를 새로 연결하는 경우로 본다.
    """
    is_new_connection = server.status != McpStatus.APPROVED
    usage_type = classify_usage_type(
        server, is_new_connection=is_new_connection, write_intent=write_intent
    )
    proposal = ExpansionProposal(
        kind=ProposalType.MCP_CONNECTION,
        name=server.id,
        reason=reason or f"'{server.name}' 연결/활성화 제안",
        write_access=write_intent,
        in_allowlist=in_allowlist,
        is_new_external_connection=is_new_connection,
        external_network_server=is_new_connection and server.external_network,
        risk_level=server.risk_level,
        data_classification=server.data_classification,
        requested_permissions=(
            list(server.write_permissions) if write_intent else list(server.read_permissions)
        ),
    )
    return ConnectionProposal(usage_type=usage_type, proposal=proposal)
