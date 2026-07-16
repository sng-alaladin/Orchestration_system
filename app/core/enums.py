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
    # 예외 상태 (Phase 2에서 사용하는 것만 우선)
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_EXPERT_CONFIRMATION = "WAITING_EXPERT_CONFIRMATION"
    AUTO_BLOCKED_BY_POLICY = "AUTO_BLOCKED_BY_POLICY"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


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
