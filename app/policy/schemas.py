"""Policy Engine 입출력 스키마 (spec 04 §16~17, 05 §19).

ExpansionProposal은 Agent 생성 또는 MCP 연결 제안을 정규화한 결정론적 위험 신호 집합이다.
LLM은 이 신호를 만들 수 있어도 판정은 하지 못한다 — 판정은 PolicyEngine(코드)만 수행한다.
"""

from pydantic import BaseModel, Field

from app.core.enums import (
    DataClassification,
    PolicyDecision,
    ProposalType,
    RiskLevel,
)


class ExpansionProposal(BaseModel):
    """확장 제안 — Policy Engine 판정 입력.

    모든 위험 신호는 결정론적으로 채워진다 (Agent Factory / MCP 연결 계층에서 산출).
    """

    kind: ProposalType
    name: str
    reason: str = ""

    # ── 공통 위험 신호 ────────────────────────────────────────────
    # 자동 승인 근거
    reuse_existing: bool = False  # 기존 Agent/MCP 재사용
    project_scoped: bool = True  # 프로젝트 범위로 제한됨
    # 하드 차단 신호 (자문으로도 우회 불가 — spec 05 §19.4)
    accesses_secret: bool = False  # Secret 조회/Context 전달
    bypasses_policy: bool = False  # Policy Engine 우회
    modifies_core_or_orchestrator: bool = False  # Core/Orchestrator 자체 변경
    modifies_agent_system_prompt: bool = False  # Agent System Prompt 변경
    admin_privilege: bool = False  # 관리자 권한 요구
    mvp_blocked_domain: bool = False  # 결제/민감정보/운영 DB (MVP 차단)
    # 전문가 확인 신호 (개발자 자문으로 진행 가능 — spec 05 §19.3)
    creates_credentials: bool = False  # 신규 인증정보 생성
    permission_escalation: bool = False  # Agent 권한 확장
    org_wide_registration: bool = False  # 조직 공통 Agent/MCP 등록
    new_model_adapter: bool = False  # 새로운 Model Adapter 등록
    large_architecture_change: bool = False  # 대규모 Architecture 변경

    # ── MCP 연결 전용 신호 (spec 04 §17) ──────────────────────────
    write_access: bool = False  # 쓰기 기능 포함
    in_allowlist: bool = True  # curated allowlist 등록 여부
    is_new_external_connection: bool = False  # 신규 외부 MCP 연결
    external_network_server: bool = False  # 신규 MCP Server(외부 네트워크) 개발
    risk_level: RiskLevel = RiskLevel.LOW
    data_classification: DataClassification = DataClassification.INTERNAL
    requested_permissions: list[str] = Field(default_factory=list)


class PolicyJudgment(BaseModel):
    """Policy Engine 판정 결과."""

    decision: PolicyDecision
    matched_rule: str  # 어떤 규칙이 판정을 내렸는지 (감사용)
    reason: str  # 사용자 언어 설명
    alternatives: list[str] = Field(default_factory=list)  # 차단 시 대안
