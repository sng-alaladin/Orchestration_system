"""공통 Enum 정의.

상태 이름은 IMPLEMENTATION_PLAN.md §6(상태 전환 테이블)의 정의를 따른다.
Phase 2에서는 Product 상태를 단순 상태 필드로만 사용하고,
선언적 전환 테이블·체크포인트는 Phase 4(세션 3)에서 구현한다.
"""

from enum import StrEnum


class ProductState(StrEnum):
    IDEA_RECEIVED = "IDEA_RECEIVED"
    DOCUMENT_ANALYZING = "DOCUMENT_ANALYZING"
    CLASSIFYING = "CLASSIFYING"
    REQUIREMENT_DRAFTING = "REQUIREMENT_DRAFTING"
    WAITING_REQUIREMENT_INPUT = "WAITING_REQUIREMENT_INPUT"
    WAITING_REQUIREMENT_APPROVAL = "WAITING_REQUIREMENT_APPROVAL"
    SPECIFICATION_GENERATING = "SPECIFICATION_GENERATING"
    CAPABILITY_ANALYZING = "CAPABILITY_ANALYZING"
    EXPANSION_PROPOSING = "EXPANSION_PROPOSING"
    WAITING_EXPANSION_APPROVAL = "WAITING_EXPANSION_APPROVAL"
    BACKLOG_GENERATING = "BACKLOG_GENERATING"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    READY_FOR_DEVELOPMENT = "READY_FOR_DEVELOPMENT"
    # 예외 상태 (Product에서 발생 가능한 전체 — IMPLEMENTATION_PLAN §6.3)
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_EXPERT_CONFIRMATION = "WAITING_EXPERT_CONFIRMATION"
    BLOCKED = "BLOCKED"
    AUTO_BLOCKED_BY_POLICY = "AUTO_BLOCKED_BY_POLICY"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    EXPANSION_REJECTED = "EXPANSION_REJECTED"
    MCP_CONNECTION_FAILED = "MCP_CONNECTION_FAILED"
    AGENT_VALIDATION_FAILED = "AGENT_VALIDATION_FAILED"


class DevelopmentState(StrEnum):
    """Development 상태 (IMPLEMENTATION_PLAN §6.2/6.4)."""

    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    SUPERVISING = "SUPERVISING"
    WAITING_PLAN_APPROVAL = "WAITING_PLAN_APPROVAL"
    WORKSPACE_CREATING = "WORKSPACE_CREATING"
    IMPLEMENTING = "IMPLEMENTING"
    LOCAL_VALIDATING = "LOCAL_VALIDATING"
    COMMITTING = "COMMITTING"
    PR_CREATING = "PR_CREATING"
    CI_RUNNING = "CI_RUNNING"
    REVIEWING = "REVIEWING"
    REPAIRING = "REPAIRING"
    PACKAGING = "PACKAGING"
    WAITING_USER_REVIEW = "WAITING_USER_REVIEW"
    READY_FOR_MERGE = "READY_FOR_MERGE"
    MERGED = "MERGED"
    DELIVERED = "DELIVERED"
    CLEANUP = "CLEANUP"
    COMPLETED = "COMPLETED"
    # 예외 상태 (Development에서 발생 가능한 전체 — §6.4)
    WAITING_INFORMATION = "WAITING_INFORMATION"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    WAITING_EXPERT_CONFIRMATION = "WAITING_EXPERT_CONFIRMATION"
    BLOCKED = "BLOCKED"
    CONFLICTED = "CONFLICTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    MCP_CONNECTION_FAILED = "MCP_CONNECTION_FAILED"
    AGENT_VALIDATION_FAILED = "AGENT_VALIDATION_FAILED"
    AUTO_BLOCKED_BY_POLICY = "AUTO_BLOCKED_BY_POLICY"


class RequirementStatus(StrEnum):
    CONFIRMED = "CONFIRMED"  # 사용자가 직접 확정
    INFERRED = "INFERRED"  # AI가 문맥 기반 추론
    UNKNOWN = "UNKNOWN"  # 추가 확인 필요


class RequirementCategory(StrEnum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    BUSINESS_RULE = "business_rule"
    EXCEPTION_CASE = "exception_case"


class AutomationClass(StrEnum):
    SELF_SERVICE = "SELF_SERVICE"
    AI_ASSISTED = "AI_ASSISTED"
    EXPERT_REVIEW_REQUIRED = "EXPERT_REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


class ClassificationGate(StrEnum):
    """적합도 분류 게이트 판정 (spec 01 §37)."""

    PROCEED = "PROCEED"  # 그대로 진행
    NEEDS_APPROVAL = "NEEDS_APPROVAL"  # 축소 범위 사용자 승인 후 진행
    NEEDS_EXPERT = "NEEDS_EXPERT"  # 전문가 확인 필요
    BLOCKED = "BLOCKED"  # 자동 차단 (결제/민감정보/운영 DB)
    UNSUPPORTED = "UNSUPPORTED"  # 수행 불가 → 사유·대안 설명


class DeliverableType(StrEnum):
    WEB_APP = "WEB_APP"
    DESKTOP_APP = "DESKTOP_APP"
    CLI_TOOL = "CLI_TOOL"
    API_SERVICE = "API_SERVICE"
    AUTOMATION_SCRIPT = "AUTOMATION_SCRIPT"


class DocumentKind(StrEnum):
    UPLOADED = "UPLOADED"
    GENERATED = "GENERATED"


class DocumentType(StrEnum):
    IDEA = "IDEA"  # 기획안 본문
    REFERENCE = "REFERENCE"  # 참고 문서
    PRD = "PRD"
    BACKLOG = "BACKLOG"


class ApprovalType(StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    REDUCED_SCOPE = "REDUCED_SCOPE"
    EXPANSION = "EXPANSION"
    PLAN = "PLAN"
    RESULT = "RESULT"


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class QuestionStatus(StrEnum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"


class DecisionSource(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    INFERRED = "inferred"


class DecisionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class ProviderType(StrEnum):
    AGENT = "AGENT"
    MCP = "MCP"
    LIBRARY = "LIBRARY"


class AuditEventType(StrEnum):
    STATE_TRANSITION = "STATE_TRANSITION"
    TRANSITION_REJECTED = "TRANSITION_REJECTED"
    GUARD_REJECTED = "GUARD_REJECTED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    TIMEOUT_NOTIFIED = "TIMEOUT_NOTIFIED"
    # Phase 6~7 (확장 구조 / 자문)
    POLICY_DECISION = "POLICY_DECISION"
    AGENT_REGISTERED = "AGENT_REGISTERED"
    AGENT_VALIDATION_REJECTED = "AGENT_VALIDATION_REJECTED"
    MCP_CONNECTION_PROPOSED = "MCP_CONNECTION_PROPOSED"
    MCP_ACTIVATED = "MCP_ACTIVATED"
    CONSULTATION_CREATED = "CONSULTATION_CREATED"
    EXPERT_ANSWER_RECORDED = "EXPERT_ANSWER_RECORDED"


# ── Phase 6~7: 확장 구조 (Agent Factory / MCP Registry / Policy Engine / 자문) ──


class PolicyDecision(StrEnum):
    """Policy Engine 4단 판정 (spec 05 §19)."""

    AUTO_APPROVE = "AUTO_APPROVE"  # 코드로 즉시 승인
    USER_APPROVAL = "USER_APPROVAL"  # 사용자가 업무·기능·비용 관점에서 판단
    EXPERT_REQUIRED = "EXPERT_REQUIRED"  # 개발자 자문 필요 → 상담 패키지 생성
    AUTO_BLOCKED = "AUTO_BLOCKED"  # 정책상 금지, 자문으로도 우회 불가(또는 MVP 차단)


class ProposalType(StrEnum):
    """확장 Proposal 종류 (spec 04 §15~17)."""

    AGENT = "AGENT"  # 신규/임시 Agent 생성
    MCP_CONNECTION = "MCP_CONNECTION"  # MCP 활성화·연결


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class AgentLifecycleType(StrEnum):
    """Agent 수명 주기 (spec 04 §15.3)."""

    PROJECT_SCOPED = "project_scoped"  # 프로젝트 종료 시 만료
    TASK_SCOPED = "task_scoped"  # 단일 Task 임시 Agent
    PERSISTENT = "persistent"  # 조직 공통 (등록은 전문가 확인 필요)


class AgentStatus(StrEnum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class McpStatus(StrEnum):
    """MCP Server 등록 상태 (spec 04 §17)."""

    APPROVED = "APPROVED"  # 등록·검증 완료 (활성화 가능)
    PROPOSED = "PROPOSED"  # 연결 제안됨 (판정 전/대기)
    BLOCKED = "BLOCKED"  # 정책상 차단
    DISABLED = "DISABLED"  # 비활성


class McpUsageType(StrEnum):
    """MCP 사용 유형 (spec 04 §17.1)."""

    A_READONLY_ACTIVATE = "A"  # 기존 승인 MCP 읽기 전용 자동 활성화
    B_WRITE_ACTIVATE = "B"  # 기존 MCP 쓰기 기능 활성화 (사용자 승인)
    C_NEW_EXTERNAL = "C"  # 신규 외부 MCP 연결 (allowlist 한정)
    D_NEW_SERVER = "D"  # 신규 MCP Server 개발


class ConsultationTrigger(StrEnum):
    """전문가 상담 패키지 생성 시점 (spec 05 §19.5)."""

    EXPERT_REQUIRED = "EXPERT_REQUIRED"  # 전문가 확인 필요 판정
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"  # 재시도 한도 초과
    SYSTEM_ERROR = "SYSTEM_ERROR"  # Orchestrator 자체 오류
    USER_REQUESTED = "USER_REQUESTED"  # 사용자가 직접 요청


class ConsultationStatus(StrEnum):
    PENDING = "PENDING"  # 답변 대기
    ANSWERED = "ANSWERED"  # 답변 입력됨
    APPLIED = "APPLIED"  # 답변 반영 완료 (게이트 해제/조정/중단)


class ExpansionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_USER = "PENDING_USER"
    PENDING_EXPERT = "PENDING_EXPERT"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
