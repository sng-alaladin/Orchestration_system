"""Policy Engine 4단 판정 테스트 (spec 05 §19).

자동 승인 / 사용자 승인 / 전문가 확인 필요 / 자동 차단 네 경로를 결정론적으로 검증한다.
"""

from app.core.enums import (
    DataClassification,
    PolicyDecision,
    ProposalType,
    RiskLevel,
)
from app.policy.engine import PRODUCT_EXPANSION_EVENT, PolicyEngine
from app.policy.schemas import ExpansionProposal

engine = PolicyEngine()


def _agent(**kw: object) -> ExpansionProposal:
    return ExpansionProposal(kind=ProposalType.AGENT, name="test-agent", **kw)  # type: ignore[arg-type]


def _mcp(**kw: object) -> ExpansionProposal:
    return ExpansionProposal(kind=ProposalType.MCP_CONNECTION, name="test-mcp", **kw)  # type: ignore[arg-type]


# ── 자동 승인 ──────────────────────────────────────────────────────


def test_auto_approve_project_scoped_agent() -> None:
    j = engine.decide(_agent(project_scoped=True, accesses_secret=False))
    assert j.decision == PolicyDecision.AUTO_APPROVE


def test_auto_approve_readonly_lowrisk_mcp() -> None:
    j = engine.decide(
        _mcp(write_access=False, in_allowlist=True, is_new_external_connection=False,
             risk_level=RiskLevel.LOW)
    )
    assert j.decision == PolicyDecision.AUTO_APPROVE


def test_auto_approve_reuse_existing() -> None:
    j = engine.decide(_mcp(reuse_existing=True))
    assert j.decision == PolicyDecision.AUTO_APPROVE


# ── 사용자 승인 ────────────────────────────────────────────────────


def test_user_approval_allowlisted_write() -> None:
    j = engine.decide(_mcp(write_access=True, in_allowlist=True))
    assert j.decision == PolicyDecision.USER_APPROVAL


def test_user_approval_allowlisted_new_external() -> None:
    j = engine.decide(_mcp(is_new_external_connection=True, in_allowlist=True))
    assert j.decision == PolicyDecision.USER_APPROVAL


# ── 전문가 확인 필요 ────────────────────────────────────────────────


def test_expert_required_external_not_allowlisted() -> None:
    j = engine.decide(_mcp(is_new_external_connection=True, in_allowlist=False))
    assert j.decision == PolicyDecision.EXPERT_REQUIRED


def test_expert_required_new_credentials() -> None:
    j = engine.decide(_mcp(creates_credentials=True))
    assert j.decision == PolicyDecision.EXPERT_REQUIRED


def test_expert_required_permission_escalation() -> None:
    j = engine.decide(_agent(permission_escalation=True))
    assert j.decision == PolicyDecision.EXPERT_REQUIRED


def test_expert_required_org_wide() -> None:
    j = engine.decide(_agent(org_wide_registration=True))
    assert j.decision == PolicyDecision.EXPERT_REQUIRED


# ── 자동 차단 ──────────────────────────────────────────────────────


def test_auto_blocked_secret_access() -> None:
    j = engine.decide(_agent(accesses_secret=True))
    assert j.decision == PolicyDecision.AUTO_BLOCKED


def test_auto_blocked_policy_bypass() -> None:
    j = engine.decide(_agent(bypasses_policy=True))
    assert j.decision == PolicyDecision.AUTO_BLOCKED


def test_auto_blocked_mvp_domain_has_alternatives() -> None:
    j = engine.decide(_mcp(mvp_blocked_domain=True))
    assert j.decision == PolicyDecision.AUTO_BLOCKED
    assert j.alternatives, "MVP 차단은 대안을 제시해야 한다"


def test_auto_blocked_confidential_external_mcp() -> None:
    j = engine.decide(
        _mcp(is_new_external_connection=True, in_allowlist=False,
             data_classification=DataClassification.CONFIDENTIAL, risk_level=RiskLevel.HIGH)
    )
    assert j.decision == PolicyDecision.AUTO_BLOCKED


def test_auto_blocked_external_network_server() -> None:
    j = engine.decide(_mcp(external_network_server=True))
    assert j.decision == PolicyDecision.AUTO_BLOCKED


# ── 규칙 우선순위 (가장 제한적인 규칙 우선) ────────────────────────


def test_block_beats_expert_and_user() -> None:
    # secret 접근(차단) + 신규 인증정보(전문가) 동시 → 차단이 우선
    j = engine.decide(_mcp(accesses_secret=True, creates_credentials=True))
    assert j.decision == PolicyDecision.AUTO_BLOCKED


def test_expert_beats_user() -> None:
    # allowlist 밖 외부 연결(전문가) + 쓰기(사용자) → 전문가가 우선
    j = engine.decide(
        _mcp(is_new_external_connection=True, in_allowlist=False, write_access=True)
    )
    assert j.decision == PolicyDecision.EXPERT_REQUIRED


def test_decision_maps_to_state_event() -> None:
    for decision, event in PRODUCT_EXPANSION_EVENT.items():
        assert event.startswith("PROPOSAL_")
        assert decision in PolicyDecision
