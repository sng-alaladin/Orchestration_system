"""MCP Health Check (Mock) — 연결·활성화 전 상태 점검 (spec 04 §17).

실제 서버 핑/핸드셰이크는 실 Adapter 연동(Phase 9 이후) 시 대체한다.
여기서는 결정론적 규칙으로 활성화 가능 여부를 판정한다.
"""

from dataclasses import dataclass

from app.core.enums import McpStatus
from app.mcp.schemas import McpServerSpec


@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    detail: str


def check_health(server: McpServerSpec) -> HealthResult:
    if server.status == McpStatus.BLOCKED:
        return HealthResult(False, "정책상 차단된 서버입니다.")
    if server.status == McpStatus.DISABLED:
        return HealthResult(False, "비활성 상태의 서버입니다.")
    # MVP: 외부 네트워크 접근이 필요한 신규 서버는 기본 차단 (spec 04 §17.1 D)
    if server.external_network:
        return HealthResult(False, "외부 네트워크 접근이 필요해 MVP에서 자동 연결할 수 없습니다.")
    if server.status == McpStatus.PROPOSED:
        return HealthResult(True, "연결 제안 상태 — 판정·승인 후 활성화 가능합니다.")
    return HealthResult(True, "정상")
