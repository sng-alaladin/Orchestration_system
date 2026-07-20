"""선언적 상태 전환 테이블 — **상태 전환의 단일 진실 원천(Single Source of Truth)**.

IMPLEMENTATION_PLAN.md §6.1~6.4 테이블을 1:1로 인코딩한다.
- §6.1 + §6.3 → PRODUCT_TRANSITIONS
- §6.2 + §6.4 → DEVELOPMENT_TRANSITIONS
- "직전 상태 (체크포인트)" 목적지는 CHECKPOINT 센티널로 표기하고 실행 시 해석한다.
- 테이블과 코드의 일치는 tests/unit/test_transitions_match_plan.py 가 강제한다.

Guard 이름은 transition_guard.py 의 GuardRegistry 에서 해석된다.
아직 구현 근거 데이터가 없는 Guard는 "deferred:<설명>@<phase>" 로 표기한다
(통과시키되 로그를 남긴다 — 해당 Phase에서 실제 Guard로 교체).
"""

from dataclasses import dataclass
from enum import StrEnum

# "직전 상태 (체크포인트)" 복귀 목적지 센티널
CHECKPOINT = "CHECKPOINT"


class MachineType(StrEnum):
    PRODUCT = "PRODUCT"
    DEVELOPMENT = "DEVELOPMENT"


@dataclass(frozen=True)
class TransitionDef:
    source: str
    event: str
    target: str  # 상태 이름 또는 CHECKPOINT
    guard: str | None = None
    description: str = ""


_T = TransitionDef

# ── §6.1 Product Definition 상태 전환 ──────────────────────────────

_PRODUCT_MAIN: list[TransitionDef] = [
    _T("IDEA_RECEIVED", "ANALYSIS_STARTED", "DOCUMENT_ANALYZING",
       "has_planning_input", "기획 텍스트 또는 문서 ≥ 1 존재, 프로젝트 활성"),
    _T("DOCUMENT_ANALYZING", "ANALYSIS_COMPLETED", "CLASSIFYING",
       "deferred:core-output-schema@phase9", "Core Agent 출력 Schema 검증 통과"),
    _T("DOCUMENT_ANALYZING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "JSON 보정 재요청 2회 실패"),
    _T("DOCUMENT_ANALYZING", "ANALYSIS_FAILED", "FAILED",
       "deferred:retry-policy@phase9", "재시도 정책 소진"),
    _T("CLASSIFYING", "CLASSIFIED_SELF_SERVICE", "REQUIREMENT_DRAFTING",
       "classification_saved", "분류 결과 저장(project_classification)"),
    _T("CLASSIFYING", "CLASSIFIED_AI_ASSISTED", "WAITING_APPROVAL",
       "classification_saved", "위험 기능 제외한 축소 범위안 생성 완료"),
    _T("CLASSIFYING", "CLASSIFIED_EXPERT_REVIEW", "WAITING_EXPERT_CONFIRMATION",
       "expert_not_confirmed", "전문가 확인 미완료 + 상담 패키지 생성(MVP 자동 차단 항목 미포함)"),
    _T("CLASSIFYING", "EXPERT_CONFIRMED_PROCEED", "REQUIREMENT_DRAFTING",
       "expert_confirmed", "전문가 확인 완료 — 재분류 무한 루프 방지"),
    _T("CLASSIFYING", "CLASSIFIED_UNSUPPORTED", "CANCELLED",
       "classification_saved", "사유·대안 설명 생성 완료"),
    _T("CLASSIFYING", "PROHIBITED_SCOPE_DETECTED", "AUTO_BLOCKED_BY_POLICY",
       "prohibited_detected", "결제/법적 민감정보/운영 DB 감지"),
    _T("REQUIREMENT_DRAFTING", "DRAFT_HAS_UNKNOWNS", "WAITING_REQUIREMENT_INPUT",
       "open_questions_exist", "UNKNOWN 요구사항 ≥ 1, 질문 카드 생성됨"),
    _T("REQUIREMENT_DRAFTING", "DRAFT_COMPLETED", "WAITING_REQUIREMENT_APPROVAL",
       "no_open_questions", "UNKNOWN 없음, CONFIRMED/INFERRED 구분 저장"),
    _T("REQUIREMENT_DRAFTING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "보정 2회 실패"),
    _T("WAITING_REQUIREMENT_INPUT", "USER_ANSWERED", "REQUIREMENT_DRAFTING",
       "answered_question_exists", "답변이 requirement_questions에 저장됨"),
    _T("WAITING_REQUIREMENT_APPROVAL", "REQUIREMENTS_APPROVED", "SPECIFICATION_GENERATING",
       "requirements_approval_exists", "user_approvals에 승인 레코드 존재"),
    _T("WAITING_REQUIREMENT_APPROVAL", "CHANGES_REQUESTED", "REQUIREMENT_DRAFTING",
       "requirements_change_request_exists", "사용자 피드백 저장됨"),
    _T("SPECIFICATION_GENERATING", "SPEC_COMPLETED", "CAPABILITY_ANALYZING",
       "prd_document_exists", "PRD·AC·산출물 유형 생성, Schema 검증 통과"),
    _T("SPECIFICATION_GENERATING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "보정 2회 실패"),
    _T("CAPABILITY_ANALYZING", "NO_GAP_FOUND", "BACKLOG_GENERATING",
       "capability_no_gap", "기존 Agent/MCP로 충족 판정"),
    _T("CAPABILITY_ANALYZING", "GAP_FOUND", "EXPANSION_PROPOSING",
       "capability_gap_exists", "Capability Gap 목록 생성"),
    _T("EXPANSION_PROPOSING", "PROPOSAL_AUTO_APPROVED", "BACKLOG_GENERATING",
       "deferred:policy-engine@phase7", "Policy Engine 자동 승인 + Sandbox 검증 통과"),
    _T("EXPANSION_PROPOSING", "PROPOSAL_NEEDS_USER", "WAITING_EXPANSION_APPROVAL",
       "deferred:policy-engine@phase7", "사용자 판단 가능 항목(기능·비용)"),
    _T("EXPANSION_PROPOSING", "PROPOSAL_NEEDS_EXPERT", "WAITING_EXPERT_CONFIRMATION",
       "deferred:policy-engine@phase7", "전문가 확인 필요 판정, 상담 패키지 생성"),
    _T("EXPANSION_PROPOSING", "PROPOSAL_BLOCKED", "AUTO_BLOCKED_BY_POLICY",
       "deferred:policy-engine@phase7", "자동 차단 정책 해당"),
    _T("WAITING_EXPANSION_APPROVAL", "EXPANSION_APPROVED", "BACKLOG_GENERATING",
       "expansion_approval_exists", "승인 레코드 + Registry 등록 완료"),
    _T("WAITING_EXPANSION_APPROVAL", "EXPANSION_DENIED", "EXPANSION_REJECTED",
       None, "—"),
    _T("BACKLOG_GENERATING", "BACKLOG_READY_NEW_REPO", "BOOTSTRAPPING",
       "deferred:bootstrap@phase8", "Ticket 생성 완료, 신규 프로젝트"),
    _T("BACKLOG_GENERATING", "BACKLOG_READY_EXISTING", "READY_FOR_DEVELOPMENT",
       "backlog_document_exists", "Ticket 생성 완료, 기존 Repo 프로젝트"),
    _T("BOOTSTRAPPING", "BOOTSTRAP_COMPLETED", "READY_FOR_DEVELOPMENT",
       "deferred:bootstrap@phase8", "Repo 생성 + 스캐폴딩 + install/lint/test 통과"),
    _T("BOOTSTRAPPING", "BOOTSTRAP_FAILED", "FAILED",
       "deferred:bootstrap@phase8", "재시도 소진"),
]

# §6.1 마지막 행: LLM 호출 상태 공통 Budget 소진 (다중 소스 → 개별 전환으로 전개)
_PRODUCT_BUDGET_SOURCES = (
    "DOCUMENT_ANALYZING",
    "CLASSIFYING",
    "REQUIREMENT_DRAFTING",
    "SPECIFICATION_GENERATING",
    "CAPABILITY_ANALYZING",
    "EXPANSION_PROPOSING",
    "BACKLOG_GENERATING",
)
_PRODUCT_MAIN += [
    _T(source, "BUDGET_EXHAUSTED", "TOKEN_BUDGET_EXCEEDED",
       "deferred:budget-manager@phase9", "project_definition_limit의 hard_stop_ratio 도달")
    for source in _PRODUCT_BUDGET_SOURCES
]

# ── §6.3 Product 예외 상태 복귀 경로 ───────────────────────────────

_PRODUCT_RECOVERY: list[TransitionDef] = [
    _T("WAITING_APPROVAL", "APPROVAL_GRANTED", "REQUIREMENT_DRAFTING",
       "reduced_scope_approval_exists", "축소 범위(AI_ASSISTED) 승인 레코드 존재"),
    _T("WAITING_APPROVAL", "APPROVAL_DENIED", "CANCELLED",
       None, "거절 사유 기록"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_UNBLOCKS", CHECKPOINT,
       "expert_confirmed_with_checkpoint",
       "답변 기록 + expert_confirmed=true 후 체크포인트 복귀 (동일 사유 재진입 금지)"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_ADJUSTS_SCOPE", "REQUIREMENT_DRAFTING",
       None, "답변에 따른 범위 조정을 반영해 요구사항 재작성"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_STOPS", "CANCELLED",
       None, "장기 미응답 시 리마인드 알림(상태 유지)"),
    _T("BLOCKED", "BLOCK_RESOLVED", CHECKPOINT,
       "checkpoint_exists", "차단 원인 해소. 시간 초과 시 사용자 알림"),
    _T("FAILED", "RETRY_SCHEDULED", CHECKPOINT,
       "can_retry", "recovery_worker, 재시도 정책 한도 내"),
    _T("FAILED", "RETRY_EXHAUSTED_SCOPE_DOWN", "REQUIREMENT_DRAFTING",
       None, "사용자 선택: 범위 축소 후 요구사항 재작성"),
    _T("FAILED", "RETRY_EXHAUSTED_CONSULT", "WAITING_EXPERT_CONFIRMATION",
       None, "사용자 선택: 상담 패키지 생성"),
    _T("FAILED", "RETRY_EXHAUSTED_STOP", "CANCELLED",
       None, "사용자 선택: 중단"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_INCREASE_APPROVED", CHECKPOINT,
       "checkpoint_exists", "증액 승인 후 체크포인트 복귀. 저성능 모델 자동 전환 금지"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_INCREASE_DENIED", "REQUIREMENT_DRAFTING",
       None, "범위 축소 제안 수락 시 요구사항 재작성"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_DENIED_STOP", "CANCELLED",
       None, "축소 제안도 거절"),
    _T("EXPANSION_REJECTED", "SCOPE_REDUCED_RETRY", "BACKLOG_GENERATING",
       None, "기존 Capability만으로 축소 Backlog 재생성"),
    _T("EXPANSION_REJECTED", "REJECT_ACCEPTED_STOP", "CANCELLED",
       None, "—"),
    _T("MCP_CONNECTION_FAILED", "MCP_RETRY_SUCCEEDED", CHECKPOINT,
       "checkpoint_exists", "Sandbox/health check 통과"),
    _T("MCP_CONNECTION_FAILED", "MCP_ALTERNATIVE_SELECTED", "EXPANSION_PROPOSING",
       None, "기존 MCP 대안으로 Proposal 재작성"),
    _T("MCP_CONNECTION_FAILED", "MCP_RETRY_EXHAUSTED", "WAITING_EXPERT_CONFIRMATION",
       None, "상담 패키지 생성"),
    _T("AGENT_VALIDATION_FAILED", "CORRECTION_SUCCEEDED", CHECKPOINT,
       "checkpoint_exists", "보정 재요청(최대 2회) 내 성공. 원본 출력은 Audit Log 저장"),
    _T("AGENT_VALIDATION_FAILED", "CORRECTION_EXHAUSTED", "FAILED",
       None, "FAILED 복귀 경로를 따름"),
    _T("AUTO_BLOCKED_BY_POLICY", "ALTERNATIVE_ACCEPTED", "DOCUMENT_ANALYZING",
       "has_planning_input", "수정된 기획으로 재분석 — 재분류 게이트 재통과 필수"),
    _T("AUTO_BLOCKED_BY_POLICY", "BLOCK_ACKNOWLEDGED_STOP", "CANCELLED",
       None, "사유·대안은 사용자 언어로 설명(우회 불가)"),
]

PRODUCT_TRANSITIONS: tuple[TransitionDef, ...] = tuple(_PRODUCT_MAIN + _PRODUCT_RECOVERY)

# ── §6.2 Development 상태 전환 ─────────────────────────────────────

_DEV_MAIN: list[TransitionDef] = [
    _T("RECEIVED", "TASK_ACCEPTED", "VALIDATING",
       "deferred:ticket-lock@phase14", "Ticket Lock 획득, Repo 동시 실행 한도 내"),
    _T("VALIDATING", "VALIDATION_PASSED", "CONTEXT_BUILDING",
       "deferred:task-schema@phase10", "Task Schema·범위·의존성 유효"),
    _T("VALIDATING", "VALIDATION_FAILED", "FAILED",
       None, "결함 사유 기록"),
    _T("VALIDATING", "DEPENDENCY_UNMET", "WAITING_DEPENDENCY",
       "deferred:dependency-check@phase10", "선행 Ticket 미완료"),
    _T("CONTEXT_BUILDING", "CONTEXT_READY", "SUPERVISING",
       "deferred:context-package@phase10", "Context Package 생성(Hash 캐시 확인)"),
    _T("CONTEXT_BUILDING", "INFO_MISSING", "WAITING_INFORMATION",
       None, "필수 정보 부재, 사용자 질문 생성"),
    _T("SUPERVISING", "PLAN_AUTO_APPROVED", "WORKSPACE_CREATING",
       "deferred:policy-engine@phase7", "실행 계획 Schema 통과 + Policy 자동 승인"),
    _T("SUPERVISING", "PLAN_NEEDS_USER", "WAITING_PLAN_APPROVAL",
       None, "사용자 판단 대상(기능 동작·비용)"),
    _T("SUPERVISING", "PLAN_NEEDS_EXPERT", "WAITING_EXPERT_CONFIRMATION",
       None, "전문가 확인 필요 판정"),
    _T("SUPERVISING", "PLAN_BLOCKED", "AUTO_BLOCKED_BY_POLICY",
       None, "금지 항목 포함"),
    _T("SUPERVISING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "보정 2회 실패"),
    _T("WAITING_PLAN_APPROVAL", "PLAN_APPROVED", "WORKSPACE_CREATING",
       "plan_approval_exists", "승인 레코드 존재"),
    _T("WAITING_PLAN_APPROVAL", "PLAN_REJECTED", "SUPERVISING",
       "deferred:replan-limit@phase10", "피드백 반영 재계획(횟수 제한 내)"),
    _T("WORKSPACE_CREATING", "WORKSPACE_READY", "IMPLEMENTING",
       "deferred:worktree@phase8", "Worktree+Branch 생성, File Intent Lock 획득"),
    _T("WORKSPACE_CREATING", "LOCK_CONFLICT", "CONFLICTED",
       None, "충돌 파일 Lock 보유자 존재"),
    _T("IMPLEMENTING", "CODE_COMPLETED", "LOCAL_VALIDATING",
       "deferred:scope-guard@phase8", "Scope Guard 통과(승인 범위 밖 변경 없음)"),
    _T("IMPLEMENTING", "BUDGET_EXHAUSTED", "TOKEN_BUDGET_EXCEEDED",
       "deferred:budget-manager@phase9", "hard_stop_ratio 도달"),
    _T("IMPLEMENTING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "보정 2회 실패"),
    _T("IMPLEMENTING", "IMPLEMENT_FAILED", "FAILED",
       None, "Coder 재시도 소진"),
    _T("LOCAL_VALIDATING", "QUALITY_GATE_PASSED", "COMMITTING",
       "deferred:quality-gate@phase12", "테스트·정적분석·보안검사 전체 통과"),
    _T("LOCAL_VALIDATING", "QUALITY_GATE_FAILED", "REPAIRING",
       "deferred:repair-limit@phase10", "repair 시도 < max_test_repairs"),
    _T("LOCAL_VALIDATING", "REPAIR_LIMIT_EXCEEDED", "WAITING_USER_REVIEW",
       None, "한도 초과 → 선택지 제시"),
    _T("COMMITTING", "PUSHED", "PR_CREATING",
       "deferred:git-push@phase11", "Commit·Push 성공 (main 직접 Push 아님)"),
    _T("COMMITTING", "BASE_DRIFT_DETECTED", "CONFLICTED",
       None, "Base Branch Drift 검사 실패"),
    _T("PR_CREATING", "PR_CREATED", "CI_RUNNING",
       "deferred:pr-idempotency@phase11",
       "멱등: tasks.pr_id 존재 시 기존 PR 재사용(Push만), 없을 때만 Draft PR 생성"),
    _T("PR_CREATING", "PR_CREATE_FAILED", "FAILED",
       None, "재시도 소진"),
    _T("CI_RUNNING", "CI_PASSED", "REVIEWING",
       "deferred:webhook-idempotency@phase11", "CI 결과 수신(Webhook Idempotent 처리)"),
    _T("CI_RUNNING", "CI_FAILED", "REPAIRING",
       "deferred:repair-limit@phase10", "repair 시도 한도 내"),
    _T("REVIEWING", "REVIEW_APPROVED", "PACKAGING",
       "deferred:review-schema@phase10", "Reviewer 결과 Schema 통과, 차단 Finding 없음"),
    _T("REVIEWING", "REVIEW_CHANGES_REQUESTED", "REPAIRING",
       "deferred:repair-limit@phase10", "review repair < max_review_repairs"),
    _T("REVIEWING", "AGENT_OUTPUT_INVALID", "AGENT_VALIDATION_FAILED",
       "deferred:json-correction@phase9", "보정 2회 실패"),
    _T("REPAIRING", "REPAIR_COMPLETED", "LOCAL_VALIDATING",
       "deferred:repair-limit@phase10", "총 시도 ≤ max_total_attempts(5)"),
    _T("REPAIRING", "REPAIR_LIMIT_EXCEEDED", "WAITING_USER_REVIEW",
       None, "한도 초과, 상황·선택지 사용자 언어 제시"),
    _T("REPAIRING", "BUDGET_EXHAUSTED", "TOKEN_BUDGET_EXCEEDED",
       "deferred:budget-manager@phase9", "hard_stop_ratio 도달"),
    _T("PACKAGING", "PACKAGE_READY", "WAITING_USER_REVIEW",
       "deferred:packaging@phase13", "산출물 패키징 + 스모크 테스트 통과"),
    _T("PACKAGING", "PACKAGING_FAILED", "REPAIRING",
       "deferred:repair-limit@phase10", "시도 한도 내, 아니면 FAILED"),
    _T("WAITING_USER_REVIEW", "USER_APPROVED", "READY_FOR_MERGE",
       "result_approval_exists", "결과 승인 레코드 존재"),
    _T("WAITING_USER_REVIEW", "USER_FEEDBACK", "REPAIRING",
       "deferred:repair-limit@phase10", "feedback repair < max_user_feedback_repairs"),
    _T("WAITING_USER_REVIEW", "USER_CANCELLED", "CANCELLED",
       None, "—"),
    _T("READY_FOR_MERGE", "MERGE_COMPLETED", "MERGED",
       "result_approval_exists", "사용자 승인 레코드 필수, PR Lock 획득"),
    _T("READY_FOR_MERGE", "MERGE_CONFLICT", "CONFLICTED",
       None, "—"),
    _T("MERGED", "DELIVERED_TO_USER", "DELIVERED",
       "deferred:artifact-store@phase13", "산출물 다운로드 가능, Release 설명 생성"),
    _T("DELIVERED", "MEMORY_UPDATED", "CLEANUP",
       "deferred:memory-update@phase10", "Project Memory·Decision Log 갱신 완료"),
    _T("CLEANUP", "CLEANUP_COMPLETED", "COMPLETED",
       "deferred:cleanup@phase8", "Worktree 제거, 모든 Lock 해제"),
]

# ── §6.4 Development 예외 상태 복귀 경로 ───────────────────────────

_DEV_RECOVERY: list[TransitionDef] = [
    _T("WAITING_INFORMATION", "INFO_PROVIDED", CHECKPOINT,
       "checkpoint_exists", "답변 저장 완료. 장기 미응답 시 리마인드 알림"),
    _T("WAITING_DEPENDENCY", "DEPENDENCY_RESOLVED", CHECKPOINT,
       "checkpoint_exists", "선행 Ticket 완료 이벤트. 시간 초과 시 사용자 알림"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_UNBLOCKS", CHECKPOINT,
       "checkpoint_exists", "답변 기록 + 확인 완료 플래그 → 동일 사유 재진입 금지"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_ADJUSTS_SCOPE", "SUPERVISING",
       None, "범위 조정 후 재계획 재진입"),
    _T("WAITING_EXPERT_CONFIRMATION", "EXPERT_ANSWER_STOPS", "CANCELLED",
       None, "장기 미응답 시 리마인드 알림(상태 유지)"),
    _T("BLOCKED", "BLOCK_RESOLVED", CHECKPOINT,
       "checkpoint_exists", "차단 원인 해소. 시간 초과 시 사용자 알림"),
    _T("CONFLICTED", "REBASE_SUCCEEDED", "LOCAL_VALIDATING",
       "deferred:rebase@phase8", "Base Drift rebase 성공 → 재검증부터 재개"),
    _T("CONFLICTED", "REBASE_FAILED", "SUPERVISING",
       None, "Supervisor 재계획"),
    _T("FAILED", "RETRY_SCHEDULED", CHECKPOINT,
       "can_retry", "recovery_worker, 재시도 정책 한도 내"),
    _T("FAILED", "RETRY_EXHAUSTED_SCOPE_DOWN", "SUPERVISING",
       None, "사용자 선택: 범위 축소 후 재계획"),
    _T("FAILED", "RETRY_EXHAUSTED_CONSULT", "WAITING_EXPERT_CONFIRMATION",
       None, "사용자 선택: 상담 패키지 생성"),
    _T("FAILED", "RETRY_EXHAUSTED_STOP", "CANCELLED",
       None, "사용자 선택: 중단"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_INCREASE_APPROVED", CHECKPOINT,
       "checkpoint_exists", "증액 승인. 저성능 모델 자동 전환 금지"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_INCREASE_DENIED", "SUPERVISING",
       None, "범위 축소 제안 수락 시 재계획"),
    _T("TOKEN_BUDGET_EXCEEDED", "BUDGET_DENIED_STOP", "CANCELLED",
       None, "축소 제안도 거절"),
    _T("MCP_CONNECTION_FAILED", "MCP_RETRY_SUCCEEDED", CHECKPOINT,
       "checkpoint_exists", "health check 통과"),
    _T("MCP_CONNECTION_FAILED", "MCP_ALTERNATIVE_SELECTED", "SUPERVISING",
       None, "기존 MCP 대안을 반영해 재계획"),
    _T("MCP_CONNECTION_FAILED", "MCP_RETRY_EXHAUSTED", "WAITING_EXPERT_CONFIRMATION",
       None, "상담 패키지 생성"),
    _T("AGENT_VALIDATION_FAILED", "CORRECTION_SUCCEEDED", CHECKPOINT,
       "checkpoint_exists", "보정 재요청(최대 2회) 내 성공. 원본 출력은 Audit Log 저장"),
    _T("AGENT_VALIDATION_FAILED", "CORRECTION_EXHAUSTED", "FAILED",
       None, "FAILED 복귀 경로를 따름"),
    _T("AUTO_BLOCKED_BY_POLICY", "ALTERNATIVE_ACCEPTED", "SUPERVISING",
       None, "차단 요소를 제외한 대안 범위로 재계획"),
    _T("AUTO_BLOCKED_BY_POLICY", "REQUIREMENT_CHANGE_NEEDED", "CANCELLED",
       None, "요구사항 자체 변경 필요 → Task 종결, Product 흐름 신규 재시작"),
    _T("AUTO_BLOCKED_BY_POLICY", "BLOCK_ACKNOWLEDGED_STOP", "CANCELLED",
       None, "사유·대안은 사용자 언어로 설명(우회 불가)"),
]

DEVELOPMENT_TRANSITIONS: tuple[TransitionDef, ...] = tuple(_DEV_MAIN + _DEV_RECOVERY)

# ── 예외 상태 집합 (spec 07 §23.3 / PLAN §6.3·6.4 서문) ────────────
# 예외 상태로 "진입"할 때 직전 상태를 체크포인트로 저장한다.

PRODUCT_EXCEPTION_STATES: frozenset[str] = frozenset({
    "WAITING_APPROVAL",
    "WAITING_EXPERT_CONFIRMATION",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
    "TOKEN_BUDGET_EXCEEDED",
    "EXPANSION_REJECTED",
    "MCP_CONNECTION_FAILED",
    "AGENT_VALIDATION_FAILED",
    "AUTO_BLOCKED_BY_POLICY",
})

DEVELOPMENT_EXCEPTION_STATES: frozenset[str] = frozenset({
    "WAITING_INFORMATION",
    "WAITING_DEPENDENCY",
    "WAITING_EXPERT_CONFIRMATION",
    "BLOCKED",
    "CONFLICTED",
    "FAILED",
    "CANCELLED",
    "TOKEN_BUDGET_EXCEEDED",
    "MCP_CONNECTION_FAILED",
    "AGENT_VALIDATION_FAILED",
    "AUTO_BLOCKED_BY_POLICY",
})

# 터미널 상태 — 어떤 전환도 정의하지 않는다 (재시작은 신규 요청/Ticket)
PRODUCT_TERMINAL_STATES: frozenset[str] = frozenset({"CANCELLED"})
DEVELOPMENT_TERMINAL_STATES: frozenset[str] = frozenset({"CANCELLED", "COMPLETED"})


def transitions_for(machine: MachineType) -> tuple[TransitionDef, ...]:
    return PRODUCT_TRANSITIONS if machine == MachineType.PRODUCT else DEVELOPMENT_TRANSITIONS


def exception_states_for(machine: MachineType) -> frozenset[str]:
    if machine == MachineType.PRODUCT:
        return PRODUCT_EXCEPTION_STATES
    return DEVELOPMENT_EXCEPTION_STATES
