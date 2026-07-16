# 03. Agent 정의 — 역할, 모델, 입출력 Schema

## 7. Agent 역할과 모델 할당

기본 Agent와 담당 모델은 다음과 같이 설정한다.

```text
Core Agent            Codex
Requirement Agent     Codex
Specification Agent   Codex
Supervisor Agent      Codex
Coder Agent           Claude Code
Reviewer Agent        Codex
Release Agent         Codex
```

기본 모델 할당은 설정 파일로 관리하고 Model Adapter 구조를 통해 교체 가능하게 한다.

---

## 8. Core Agent

### 8.1 역할

Core Agent는 비개발자와 시스템 사이의 단일 대표 소통 창구다.

```text
AI Product Manager + Business Analyst + Technical Translator
+ Project Navigator + Capability Planner
```

주요 책임:

* 자연어 요청 이해 / 기획안 분석 / 부족한 요구사항 탐지
* 비개발자용 질문 생성 / 요구사항 상태 관리 / 프로젝트 범위 정의
* 사용자 흐름 정리 / 프로젝트 진행 상황 설명
* 기술적 문제를 사용자 언어로 변환 / 사용자 답변을 개발 명세로 변환
* 기존 프로젝트 결정과 신규 요청 간 충돌 탐지
* 프로젝트에 필요한 Agent 및 MCP 역량 분석 / 시스템 확장안 생성
* 사용자 승인 요청 / 결과와 제한사항 설명
* 프로젝트 적합도 분류 및 차단 사유 설명 (섹션 37)

Core Agent는 제품 코드를 직접 수정하지 않는다.
Core Agent는 Orchestrator의 상태 머신이나 보안 정책을 직접 변경하지 않는다.

### 8.2 Core Agent 출력 예시

```json
{
  "project_goal": "엑셀 데이터를 기반으로 Word 보고서를 자동 생성한다",
  "target_users": ["비개발자 사무직 사용자"],
  "automation_class": "SELF_SERVICE",
  "deliverable_type": "DESKTOP_APP",
  "functional_requirements": [
    {
      "id": "FR-001",
      "description": "사용자는 xlsx 또는 xls 파일을 입력할 수 있다",
      "status": "CONFIRMED"
    },
    {
      "id": "FR-002",
      "description": "동일 이름의 결과 파일이 있을 경우 새 이름을 생성한다",
      "status": "INFERRED"
    }
  ],
  "open_questions": [
    {
      "id": "Q-001",
      "question": "기존 Word 양식을 그대로 사용해야 하나요?",
      "reason": "보고서 생성 방식을 결정하기 위해 필요함"
    }
  ],
  "required_capabilities": ["excel-read", "word-document-generate", "file-output"],
  "expansion_required": false
}
```

---

## 9. Requirement Agent

Requirement Agent는 Core Agent가 정리한 내용을 구조화된 요구사항으로 변환한다.

담당 기능:

* 누락된 기능 요구사항 탐지 / 비기능 요구사항 탐지 / 예외 상황 생성
* 업무 규칙 정리 / 사용자 유형 정의 / 입력과 출력 정의
* 완료 조건 생성 / 우선순위 제안 / 요구사항 간 충돌 탐지

Requirement Agent는 기술 구현 방법보다 제품 동작을 정의해야 한다.

---

## 10. Specification Agent

Specification Agent는 승인된 요구사항을 개발 가능한 명세로 변환한다.

생성 대상:

```text
PRD / Epic / User Story / Development Task / Acceptance Criteria
Test Scenario / Out of Scope / Risk Assumption / Ticket Payload
산출물 유형(deliverable_type) 및 패키징 요구사항
```

예시:

```json
{
  "task_type": "feature",
  "goal": "엑셀 데이터를 읽어 기존 Word 템플릿에 표와 차트를 삽입한다",
  "deliverable_type": "DESKTOP_APP",
  "acceptance_criteria": [
    "xlsx와 xls 파일을 읽을 수 있다",
    "사용자가 입력한 이슈사항을 보고서에 포함한다",
    "결과 파일은 output 폴더에 저장된다",
    "Python이 없는 Windows 환경에서 실행할 수 있다"
  ],
  "constraints": [
    "Microsoft Office 2007 문서 형식과 호환되어야 한다",
    "원본 엑셀 파일을 변경하지 않는다"
  ],
  "out_of_scope": ["클라우드 업로드", "다중 사용자 동시 실행"]
}
```

---

## 11. Supervisor Agent

담당 모델: Codex

Supervisor Agent는 개발 실행 단계의 책임자다.

역할:

* 개발 Task 분석 / 작업 적합성 판단 / 위험도 평가 / 작업 계획 생성
* Coder 실행 범위 정의 / 수정 예상 파일 지정 / 병렬 작업 충돌 판단
* Quality Gate 지정 / 사용자 승인 필요 여부 판단(Policy Engine 규칙 안에서)
* Token Budget 지정 / 재시도 판단 / PR 생성 가능 여부 판단
* 신규 프로젝트의 언어/프레임워크/스캐폴딩 템플릿 선택

Supervisor Agent는 제품 코드를 직접 수정하지 않는다.
Supervisor Agent의 결과는 반드시 Pydantic Schema로 검증 가능한 JSON이어야 한다.

```json
{
  "task_id": "DEV-142",
  "decision": "APPROVED",
  "risk_score": 42,
  "requires_user_approval": false,
  "goal": "로그인 세션 만료 경계값 오류 수정",
  "affected_domains": ["authentication", "session"],
  "expected_files": [
    "src/auth/session_service.py",
    "tests/auth/test_session_service.py"
  ],
  "steps": [
    "현재 세션 만료 조건 확인",
    "재현 테스트 추가",
    "만료 조건 수정",
    "회귀 테스트 실행"
  ],
  "quality_gates": ["format", "lint", "typecheck", "unit_test", "build"],
  "constraints": [
    "인증 API 응답 형식을 변경하지 않는다",
    "DB Schema를 변경하지 않는다"
  ],
  "token_budget": 150000
}
```

---

## 12. Coder Agent

담당 모델: Claude Code

역할:

* Supervisor가 승인한 계획 실행 / Git Worktree 내부 코드 탐색
* 관련 코드 수정 / 테스트 추가 및 수정 / 프로젝트 Rules 준수
* Quality Gate 실행 / 실패 원인 분석 / 변경 내용 요약

Coder Agent는 다음 행동을 할 수 없다.

* 승인되지 않은 대규모 리팩터링 / 승인 범위를 벗어난 파일 변경
* Secret 파일 조회 / 테스트 삭제 또는 우회 / 품질 검사 비활성화
* 위험 경로 무단 변경 / main 또는 develop 브랜치 직접 수정
* PR 직접 승인 / 자동 Merge / Agent Registry 직접 변경
* MCP Server 직접 활성화 / Orchestrator 정책 수정

계획에 없는 파일을 수정해야 하는 경우 작업을 중단하고 Supervisor Agent에게 범위 변경을 요청한다.

출력 예시:

```json
{
  "status": "IMPLEMENTATION_COMPLETED",
  "changed_files": [
    "src/auth/session_service.py",
    "tests/auth/test_session_service.py"
  ],
  "commands_executed": ["ruff check .", "mypy src", "pytest tests/auth"],
  "test_results": {"passed": 28, "failed": 0, "skipped": 1},
  "scope_changed": false,
  "known_risks": [],
  "summary": "세션 만료 경계값 비교 로직을 수정하고 회귀 테스트를 추가함"
}
```

---

## 13. Reviewer Agent

담당 모델: Codex

역할:

* 요구사항과 구현 결과 비교 / Git Diff 검토 / Rules 준수 여부 검토
* 코드 품질 검토 / 잠재적 버그 탐지 / 테스트 충분성 평가
* 보안 문제 검토 / 불필요한 변경 탐지 / 과도한 추상화 탐지
* 회귀 가능성 검토 / PR 승인 가능 여부 판단

Reviewer Agent는 Coder Agent와 독립된 Context로 실행한다.

Reviewer Agent에게 제공하는 정보:

* Ticket / 승인된 작업 계획 / 프로젝트 Rules / Git Diff
* 변경 코드 주변 Context / 테스트 결과 / 정적 분석 결과 / 빌드 결과

Coder Agent의 전체 대화는 전달하지 않는다.

출력 예시:

```json
{
  "decision": "CHANGES_REQUESTED",
  "summary": "핵심 로직은 적절하지만 만료 직전 경계값 테스트가 부족함",
  "findings": [
    {
      "severity": "MEDIUM",
      "category": "TEST",
      "file": "tests/auth/test_session_service.py",
      "line": 42,
      "message": "만료 1초 전 케이스에 대한 테스트가 필요함",
      "suggested_action": "만료 시각 직전 세션이 유효한지 검증하는 테스트 추가"
    }
  ],
  "require_repair": true,
  "requires_user_review": false
}
```

---

## 14. Release Agent

Release Agent는 개발 완료 결과를 비개발자용 설명으로 변환한다.

생성 내용:

* 무엇이 추가되었는지 / 무엇이 변경되었는지 / 어떻게 사용하는지
* 요청 내용이 어떻게 반영되었는지 / 검증 결과 / 알려진 제약사항
* 사용자가 직접 확인해야 할 부분 (기능 확인 체크리스트)
* 다음 개선 후보
* 산출물 다운로드 안내 및 실행 방법

Release Agent는 코드 Diff를 사용자에게 기본적으로 노출하지 않는다.

**기능 확인 체크리스트**는 사용자가 실제 산출물을 실행하며 하나씩 확인할 수 있는
구체적인 행동 지시 형태로 작성한다.

```text
[ ] 프로그램을 실행하고 샘플 엑셀 파일(sample.xlsx)을 선택해 보세요.
[ ] output 폴더에 Word 보고서가 생성되었는지 확인해 보세요.
[ ] 같은 파일로 한 번 더 실행했을 때 기존 보고서가 지워지지 않는지 확인해 보세요.
```

---

