"""Agent Definition 검증기 (spec 04 §16).

검증 체인: Schema(→pydantic) → 권한 → 모델 사용 가능 → MCP 의존성 → Token Budget → Sandbox.
검증 실패는 등록 거부(AGENT_VALIDATION_FAILED)로 이어진다 — Policy 판정 이전 단계다.
관리자 권한/미검증 권한 값 등 정책 불변 위반은 여기서 하드 차단한다 (spec 05 §31).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.agents.schemas import (
    ALLOWED_MODEL_PROVIDERS,
    FILESYSTEM_LEVELS,
    NETWORK_LEVELS,
    SHELL_LEVELS,
    AgentDefinition,
)

# Token Budget 상한 (프로젝트 정의 Agent 기준). 초과 시 검증 실패.
MAX_INPUT_TOKENS_CAP = 200_000
MAX_OUTPUT_TOKENS_CAP = 64_000


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field: str = ""


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def add(self, code: str, message: str, field_name: str = "") -> None:
        self.issues.append(ValidationIssue(code=code, message=message, field=field_name))

    def messages(self) -> list[str]:
        return [i.message for i in self.issues]


def validate_permissions(defn: AgentDefinition, report: ValidationReport) -> None:
    perms = defn.permissions
    # 하드 불변: Agent 관리자 권한 금지 (spec 05 §31)
    if perms.admin:
        report.add("perm.admin", "Agent에게 관리자 권한을 부여할 수 없습니다.", "permissions.admin")
    # 하드 불변: Secret 접근 정의 금지 (Secret은 Agent Context에 전달하지 않는다)
    if perms.accesses_secret:
        report.add(
            "perm.secret",
            "Agent 정의에 Secret 접근을 포함할 수 없습니다.",
            "permissions.accesses_secret",
        )
    if perms.filesystem not in FILESYSTEM_LEVELS:
        report.add(
            "perm.fs",
            f"허용되지 않는 filesystem 권한: {perms.filesystem}",
            "permissions.filesystem",
        )
    if perms.network not in NETWORK_LEVELS:
        report.add(
            "perm.net", f"허용되지 않는 network 권한: {perms.network}", "permissions.network"
        )
    if perms.shell not in SHELL_LEVELS:
        report.add("perm.shell", f"허용되지 않는 shell 권한: {perms.shell}", "permissions.shell")
    # 쓰기 권한은 반드시 경로 범위(allowed_paths)로 제한되어야 한다 (Worktree 외부 접근 제한)
    if perms.filesystem == "read_write_scoped" and not defn.scope.allowed_paths:
        report.add(
            "perm.unscoped_write",
            "쓰기 권한 Agent는 허용 경로(allowed_paths)를 반드시 지정해야 합니다.",
            "scope.allowed_paths",
        )


def validate_model(defn: AgentDefinition, report: ValidationReport) -> None:
    if defn.model.provider not in ALLOWED_MODEL_PROVIDERS:
        report.add(
            "model.provider",
            f"사용할 수 없는 모델 provider입니다: {defn.model.provider} "
            f"(허용: {', '.join(sorted(ALLOWED_MODEL_PROVIDERS))})",
            "model.provider",
        )


def validate_mcp_dependencies(
    defn: AgentDefinition, known_mcp_ids: Iterable[str], report: ValidationReport
) -> None:
    known = set(known_mcp_ids)
    for dep in defn.mcp_dependencies:
        if dep not in known:
            report.add(
                "mcp.unknown",
                f"등록되지 않은 MCP 의존성입니다: {dep}. 먼저 MCP Registry에 등록/연결해야 합니다.",
                "mcp_dependencies",
            )


def validate_token_budget(defn: AgentDefinition, report: ValidationReport) -> None:
    if defn.token_budget.max_input_tokens > MAX_INPUT_TOKENS_CAP:
        report.add(
            "budget.input",
            f"max_input_tokens가 상한({MAX_INPUT_TOKENS_CAP})을 초과했습니다.",
            "token_budget.max_input_tokens",
        )
    if defn.token_budget.max_output_tokens > MAX_OUTPUT_TOKENS_CAP:
        report.add(
            "budget.output",
            f"max_output_tokens가 상한({MAX_OUTPUT_TOKENS_CAP})을 초과했습니다.",
            "token_budget.max_output_tokens",
        )


def validate_sandbox(defn: AgentDefinition, report: ValidationReport) -> None:
    """Sandbox Test(Mock) — 실제 실행 없이 결정론적 스모크 검증.

    실 Sandbox 실행은 Phase 9(Model Adapter)/Phase 12(Quality Gate)에서 연동한다.
    여기서는 등록 전에 반드시 만족해야 할 최소 조건을 검사한다.
    """
    if not defn.capabilities:
        report.add(
            "sandbox.no_capability",
            "Agent가 제공하는 capability가 하나도 없습니다.",
            "capabilities",
        )
    # 쓰기 권한 Agent는 최소한의 품질 게이트를 선언해야 한다
    if defn.permissions.filesystem == "read_write_scoped" and not defn.quality_gates:
        report.add(
            "sandbox.no_quality_gate",
            "코드를 수정하는 Agent는 품질 게이트(quality_gates)를 선언해야 합니다.",
            "quality_gates",
        )


def run_validation_chain(
    defn: AgentDefinition,
    *,
    known_mcp_ids: Iterable[str] = (),
) -> ValidationReport:
    """전체 검증 체인 실행. 반환된 report.ok 가 False면 등록을 거부한다."""
    report = ValidationReport()
    validate_permissions(defn, report)
    validate_model(defn, report)
    validate_mcp_dependencies(defn, known_mcp_ids, report)
    validate_token_budget(defn, report)
    validate_sandbox(defn, report)
    return report
