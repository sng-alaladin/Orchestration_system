"""Policy Engine — 결정론적 4단 판정 (spec 05 §19).

판정 순서(가장 제한적인 규칙 우선, 첫 매칭이 결과):
  1) 자동 차단 (AUTO_BLOCKED)      — 정책상 금지 또는 MVP 차단 도메인
  2) 전문가 확인 필요 (EXPERT_REQUIRED) — 개발자 자문으로 진행 가능
  3) 사용자 승인 (USER_APPROVAL)   — 업무·기능·비용 관점에서 사용자가 판단 가능
  4) 자동 승인 (AUTO_APPROVE)      — 명시적 저위험 근거가 있을 때만
  (그 외 인식되지 않은 경우 안전하게 USER_APPROVAL로 강등 — 조용히 자동 승인하지 않음)

LLM(Supervisor)이 아니라 이 엔진이 최종 판정자다 (spec 04 §16).
결정은 상태 머신 이벤트로 매핑된다 (PRODUCT_EVENT_BY_DECISION / DEV_PLAN_EVENT_BY_DECISION).
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.enums import DataClassification, PolicyDecision, RiskLevel
from app.observability.logging import get_logger
from app.policy.schemas import ExpansionProposal, PolicyJudgment

logger = get_logger(__name__)


@dataclass(frozen=True)
class _Rule:
    name: str
    decision: PolicyDecision
    predicate: Callable[[ExpansionProposal], bool]
    reason: str
    alternatives: tuple[str, ...] = ()


_MVP_BLOCK_ALTS = (
    "차단된 기능을 제외한 나머지 범위로 먼저 진행하기",
    "해당 기능은 기존 외부 서비스 링크로 대체하기",
    "개발자에게 물어볼 상담 자료를 만들어 함께 계획 세우기",
)

# ── 판정 규칙 (위에서부터 평가, 첫 매칭 승) ────────────────────────
_RULES: tuple[_Rule, ...] = (
    # 1) 자동 차단 — 자문으로도 우회 불가 (spec 05 §19.4)
    _Rule(
        "block:policy_bypass", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.bypasses_policy,
        "정책 엔진을 우회하려는 요청은 허용되지 않습니다.",
    ),
    _Rule(
        "block:core_or_orchestrator", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.modifies_core_or_orchestrator,
        "Core Agent 또는 Orchestrator 자체를 바꾸는 작업은 허용되지 않습니다.",
    ),
    _Rule(
        "block:system_prompt", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.modifies_agent_system_prompt,
        "Agent의 동작 지침(System Prompt)을 바꾸는 작업은 허용되지 않습니다.",
    ),
    _Rule(
        "block:admin_privilege", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.admin_privilege,
        "관리자 권한이 필요한 작업은 이 시스템에서 자동으로 수행하지 않습니다.",
    ),
    _Rule(
        "block:secret_access", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.accesses_secret,
        "Secret(인증정보) 조회나 전달이 포함된 작업은 허용되지 않습니다.",
    ),
    _Rule(
        "block:external_network_server", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.external_network_server,
        "외부 네트워크에 접근하는 새 MCP 서버를 만드는 작업은 MVP에서 자동으로 진행하지 않습니다.",
        (
            "개발자와 함께 별도 프로젝트로 계획 세우기",
            "외부 연동 없이 파일(엑셀/CSV) 기반으로 범위 줄이기",
        ),
    ),
    _Rule(
        "block:mvp_domain", PolicyDecision.AUTO_BLOCKED,
        lambda p: p.mvp_blocked_domain,
        "결제·법적 민감정보·운영 DB 연동은 안전을 위해 이 시스템에서 자동으로 만들지 않습니다.",
        _MVP_BLOCK_ALTS,
    ),
    _Rule(
        "block:confidential_external_mcp", PolicyDecision.AUTO_BLOCKED,
        lambda p: (
            p.is_new_external_connection
            and not p.in_allowlist
            and (
                p.data_classification == DataClassification.CONFIDENTIAL
                or p.risk_level == RiskLevel.HIGH
            )
        ),
        "기밀 데이터에 접근하거나 위험도가 높은 외부 연결은 정책상 자동 연결할 수 없습니다.",
        (
            "기밀 데이터 대신 내보낸 사본 파일을 사용하기",
            "개발자 자문 후 별도 승인 절차로 진행하기",
        ),
    ),
    # 2) 전문가 확인 필요 — 개발자 자문으로 진행 가능 (spec 05 §19.3)
    _Rule(
        "expert:new_credentials", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.creates_credentials,
        "새 인증정보(로그인/연동 키) 설정이 필요해 개발자 확인이 필요합니다.",
    ),
    _Rule(
        "expert:permission_escalation", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.permission_escalation,
        "Agent 권한을 넓히는 작업이라 개발자 확인이 필요합니다.",
    ),
    _Rule(
        "expert:org_wide_registration", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.org_wide_registration,
        "조직 공통 자원으로 등록하는 작업이라 개발자 확인이 필요합니다.",
    ),
    _Rule(
        "expert:new_model_adapter", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.new_model_adapter,
        "새로운 모델 연동(Adapter) 등록이라 개발자 확인이 필요합니다.",
    ),
    _Rule(
        "expert:large_architecture", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.large_architecture_change,
        "대규모 구조 변경이 포함되어 개발자 확인이 필요합니다.",
    ),
    _Rule(
        "expert:external_mcp_not_allowlisted", PolicyDecision.EXPERT_REQUIRED,
        lambda p: p.is_new_external_connection and not p.in_allowlist,
        "허용 목록에 없는 외부 서비스 연결이라 개발자가 연결 방법을 확인해야 합니다.",
    ),
    # 3) 사용자 승인 — 업무·기능·비용 관점에서 사용자가 판단 가능 (spec 05 §19.2)
    _Rule(
        "user:allowlisted_write", PolicyDecision.USER_APPROVAL,
        lambda p: p.write_access and p.in_allowlist,
        "허용 목록에 있는 도구의 쓰기 기능을 켭니다. 무엇을 쓰는지 확인하고 승인해 주세요.",
    ),
    _Rule(
        "user:allowlisted_external", PolicyDecision.USER_APPROVAL,
        lambda p: p.is_new_external_connection and p.in_allowlist,
        "허용 목록에 있는 외부 서비스에 연결합니다. 기능·비용 관점에서 확인하고 승인해 주세요.",
    ),
    # 4) 자동 승인 — 명시적 저위험 근거 (spec 05 §19.1)
    _Rule(
        "auto:reuse_existing", PolicyDecision.AUTO_APPROVE,
        lambda p: p.reuse_existing,
        "이미 검증된 기존 자원을 그대로 재사용하므로 자동으로 진행합니다.",
    ),
    _Rule(
        "auto:readonly_lowrisk_mcp", PolicyDecision.AUTO_APPROVE,
        lambda p: (
            not p.write_access
            and p.in_allowlist
            and not p.is_new_external_connection
            and p.risk_level == RiskLevel.LOW
            and p.data_classification != DataClassification.CONFIDENTIAL
        ),
        "읽기 전용이며 위험도가 낮은 도구를 켜므로 자동으로 진행합니다.",
    ),
    _Rule(
        "auto:project_scoped_agent", PolicyDecision.AUTO_APPROVE,
        lambda p: (
            p.kind.value == "AGENT"
            and p.project_scoped
            and not p.accesses_secret
            and not p.permission_escalation
        ),
        "이 프로젝트 범위로만 동작하고 Secret 접근이 없는 Agent라 자동으로 등록합니다.",
    ),
)

# 그 외 인식되지 않은 경우: 안전하게 사용자 승인으로 강등한다 (조용히 자동 승인 금지)
_FALLBACK = PolicyJudgment(
    decision=PolicyDecision.USER_APPROVAL,
    matched_rule="fallback:needs_user",
    reason="자동으로 판단하기 어려운 요청이라 사용자 확인 후 진행합니다.",
)


class PolicyEngine:
    """확장 Proposal을 4단으로 판정하는 결정론적 엔진."""

    def decide(self, proposal: ExpansionProposal) -> PolicyJudgment:
        for rule in _RULES:
            if rule.predicate(proposal):
                judgment = PolicyJudgment(
                    decision=rule.decision,
                    matched_rule=rule.name,
                    reason=rule.reason,
                    alternatives=list(rule.alternatives),
                )
                logger.info(
                    "policy_decision",
                    proposal=proposal.name,
                    kind=str(proposal.kind),
                    decision=str(judgment.decision),
                    rule=rule.name,
                )
                return judgment
        logger.info(
            "policy_decision",
            proposal=proposal.name,
            kind=str(proposal.kind),
            decision=str(_FALLBACK.decision),
            rule=_FALLBACK.matched_rule,
        )
        return _FALLBACK


# ── 판정 → 상태 머신 이벤트 매핑 ──────────────────────────────────
# Product EXPANSION_PROPOSING 및 Development SUPERVISING 전환에 사용.

PRODUCT_EXPANSION_EVENT: dict[PolicyDecision, str] = {
    PolicyDecision.AUTO_APPROVE: "PROPOSAL_AUTO_APPROVED",
    PolicyDecision.USER_APPROVAL: "PROPOSAL_NEEDS_USER",
    PolicyDecision.EXPERT_REQUIRED: "PROPOSAL_NEEDS_EXPERT",
    PolicyDecision.AUTO_BLOCKED: "PROPOSAL_BLOCKED",
}

DEV_PLAN_EVENT: dict[PolicyDecision, str] = {
    PolicyDecision.AUTO_APPROVE: "PLAN_AUTO_APPROVED",
    PolicyDecision.USER_APPROVAL: "PLAN_NEEDS_USER",
    PolicyDecision.EXPERT_REQUIRED: "PLAN_NEEDS_EXPERT",
    PolicyDecision.AUTO_BLOCKED: "PLAN_BLOCKED",
}
