# 07. 상태 머신, Token Budget, Repair Workflow

## 23. Workflow 상태 머신

### 23.1 Product Definition 상태

```text
IDEA_RECEIVED
DOCUMENT_ANALYZING
CLASSIFYING            (프로젝트 적합도 분류, 섹션 37)
REQUIREMENT_DRAFTING
WAITING_REQUIREMENT_INPUT
WAITING_REQUIREMENT_APPROVAL
SPECIFICATION_GENERATING
CAPABILITY_ANALYZING
EXPANSION_PROPOSING
WAITING_EXPANSION_APPROVAL
BACKLOG_GENERATING
BOOTSTRAPPING          (신규 프로젝트: Repo 생성 및 스캐폴딩, 섹션 5)
READY_FOR_DEVELOPMENT
```

### 23.2 Development 상태

```text
RECEIVED
VALIDATING
CONTEXT_BUILDING
SUPERVISING
WAITING_PLAN_APPROVAL
WORKSPACE_CREATING
IMPLEMENTING
LOCAL_VALIDATING
COMMITTING
PR_CREATING
CI_RUNNING
REVIEWING
REPAIRING
PACKAGING
WAITING_USER_REVIEW
READY_FOR_MERGE
MERGED
DELIVERED
CLEANUP
COMPLETED
```

### 23.3 예외 상태

```text
WAITING_INFORMATION
WAITING_DEPENDENCY
WAITING_APPROVAL
WAITING_EXPERT_CONFIRMATION
BLOCKED
CONFLICTED
FAILED
CANCELLED
TOKEN_BUDGET_EXCEEDED
EXPANSION_REJECTED
MCP_CONNECTION_FAILED
AGENT_VALIDATION_FAILED
AUTO_BLOCKED_BY_POLICY
```

### 23.4 상태 전환 테이블 의무화

상태 목록만으로는 구현할 수 없다. 다음을 의무화한다.

1. `IMPLEMENTATION_PLAN.md`에 **모든 상태의 전환 테이블**(현재 상태 → 이벤트 → 다음 상태 → Guard 조건)을 포함한다.
2. **모든 예외 상태의 복귀 경로**를 정의한다. 최소 다음을 포함한다.

```text
TOKEN_BUDGET_EXCEEDED
  → 사용자에게 예상 추가 비용과 함께 증액 승인 요청
  → 승인 시: 직전 진행 상태로 복귀 (체크포인트 기반 재개)
  → 거절 시: 작업 범위 축소 제안 또는 CANCELLED

BLOCKED / WAITING_DEPENDENCY
  → 차단 원인 해소 이벤트 발생 시 직전 상태로 복귀
  → 일정 시간 초과 시 사용자에게 알림

FAILED
  → recovery_worker가 재시도 정책에 따라 재시도
  → 재시도 한도 초과 시: 사용자에게 사용자 언어로 상황 설명
    + 선택지 제공 (범위 축소 / 중단 / "개발자에게 물어볼 자료 만들기")
  → 상담 패키지 선택 시 WAITING_EXPERT_CONFIRMATION으로 전환

WAITING_EXPERT_CONFIRMATION
  → 전문가 상담 패키지 생성 및 자문 화면 게시
  → 사용자가 개발자 답변을 입력하면 답변 내용에 따라:
    게이트 해제 후 직전 진행 상태로 복귀 (체크포인트 기반)
    / 범위 조정 후 SUPERVISING 재진입 / CANCELLED
  → 장기간 미응답 시 사용자에게 리마인드 알림

CONFLICTED
  → Base Branch Drift 해소(rebase) 시도 → 실패 시 Supervisor 재계획

AUTO_BLOCKED_BY_POLICY
  → 차단 사유와 대안을 사용자에게 설명 → 범위 축소된 신규 요구사항으로 재시작 가능
```

3. 상태 전환은 명시적인 코드로 관리한다. LLM이 직접 상태를 변경하지 않는다.
4. 각 상태에는 체크포인트를 두어, 중단된 작업이 처음부터가 아니라 중단 지점부터 재개될 수 있게 한다.

---

## 27. Token 최적화

다음 Context 흐름을 사용한다.

```text
기획안 → 구조화된 프로젝트 요약 → 관련 Requirement → 관련 Decision
→ 관련 Domain → Repository Map → Symbol 검색 → 관련 파일 → 필요한 코드 범위
```

Agent 간 전달:

```text
Core Agent          → 구조화된 요구사항만 전달
Requirement Agent   → Requirement Schema만 전달
Specification Agent → 개발 명세만 전달
Supervisor Agent    → 실행 계획만 전달
Coder Agent         → 변경 결과와 Diff만 전달
Reviewer Agent      → 리뷰 결과만 전달
```

전체 대화 기록과 내부 추론을 다음 Agent에게 전달하지 않는다.

Token Budget 기본값 (초기값은 보수적으로 크게 잡고, 실측 후 조정한다):

```yaml
token_budget:
  project_definition_limit: 200000
  default_development_task_limit: 400000
  warning_ratio: 0.7
  hard_stop_ratio: 1.0

  agent_limits:
    core: 50000
    requirement: 40000
    specification: 40000
    supervisor: 50000
    coder: 250000
    reviewer: 50000
    release: 20000
```

Budget 초과 시 자동으로 저성능 모델로 전환하지 않는다.
`TOKEN_BUDGET_EXCEEDED`로 전환하고, 섹션 23.4의 복귀 흐름(사용자 증액 승인 → 체크포인트 재개)을 따른다.
증액 승인 카드에는 "지금까지 사용량, 예상 추가량, 대략적인 비용"을 사용자 언어로 표시한다.

---

## 30. Repair Workflow

```text
Reviewer Agent → Review Finding 생성
→ Supervisor Agent가 수정 범위 판단
→ Coder Agent 수정
→ Quality Gate 재실행
→ Reviewer Agent 재검토
```

제한:

```yaml
repair_policy:
  max_test_repairs: 3
  max_review_repairs: 2
  max_user_feedback_repairs: 2
  max_total_attempts: 5
```

초과 시 `WAITING_USER_REVIEW`로 전환하고, 현재 상태·시도 내역·선택지(범위 축소, 요구사항 조정, 중단)를 사용자 언어로 제시한다.

---

