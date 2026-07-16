# 10. 실행 계획 — MVP 범위, Phase, 테스트, 완료 기준, 세션 계획

## 38. MVP 구현 범위

첫 번째 MVP에서는 다음 Vertical Slice를 완성한다.

```text
비개발자가 웹 UI에 로그인
→ 기획안 입력 (채팅 + 문서 업로드)
→ Core Agent가 기획안 분석
→ 적합도 분류 게이트 통과
→ Requirement Agent가 누락 사항 탐지
→ UI 질문 카드로 쉬운 질문 제시
→ 사용자가 요구사항 승인 (승인 카드)
→ Specification Agent가 PRD와 개발 Task 생성 (산출물 유형 포함)
→ Capability Registry와 Gap 분석
→ 기존 Agent와 MCP로 처리 가능한지 판단
→ Internal Ticket 생성
→ 신규 GitHub Repository 부트스트랩
→ Codex Supervisor 실행
→ Git Worktree 생성
→ Claude Code Coder 실행
→ Quality Gate 실행
→ Draft PR 생성
→ Codex Reviewer 실행
→ 산출물 패키징
→ Release Agent가 결과 설명 + 기능 확인 체크리스트 생성
→ 사용자가 UI에서 결과물 다운로드 및 확인
→ 사용자 승인 → 시스템 Merge → DELIVERED
→ Project Memory 업데이트
```

MVP에서 Agent 자동 확장은 다음 수준까지만 구현한다.

* Agent Definition 생성 / Schema 검증 / 프로젝트 전용 Agent Registry 등록
* Mock 또는 승인된 Agent 활성화 / 기존 MCP Registry 검색
* MCP 연결 Proposal 생성 / 승인 상태 관리

MVP에서 제외:

* 승인되지 않은 외부 MCP 자동 설치
* 신규 MCP Server의 운영 자동 배포
* 사용자 승인 없는 Merge
* Production 클라우드 자동 배포
* 다중 Repository 동시 수정
* 다중 사용자 / 조직 권한 체계
* Agent 자체 권한 변경
* Core Agent 자체 수정
* Orchestrator 자체 수정
* 완전 자율 Architecture 변경
* 결제 / 법적 민감 개인정보 / 운영 DB 연동이 포함된 프로젝트 (자동 차단)

---

## 39. 구현 순서

```text
Phase 1.  기반 프로젝트
          Python 초기화, FastAPI, PostgreSQL, SQLAlchemy, Alembic,
          Pydantic, Logging, Docker Compose, 기본 테스트 환경,
          users/sessions와 기본 로그인 API

Phase 2.  Product Definition Engine
          문서 업로드, Core Agent, Requirement Agent, 질문 생성,
          요구사항 상태, 사용자 승인, Specification Agent,
          적합도 분류 게이트, PRD 및 Backlog 생성

Phase 3.  Project Memory
          Requirement 저장, Decision Log, Version 관리, Feedback 저장, 충돌 탐지

Phase 4.  상태 머신
          Product/Development 상태 머신, 선언적 전환 테이블,
          전환 Guard, 체크포인트, Idempotency, Retry, Timeout, Audit Log

Phase 5.  Capability Registry
          Capability Schema, Provider 관리, Gap Analyzer, Agent/MCP 매칭

Phase 6.  Agent Factory
          Agent Definition, Validator(정의/권한/Sandbox), Registry, Lifecycle

Phase 7.  MCP Registry + 자문 구조
          Server/Tool Registry, Allowlist, Permission Policy,
          Connection Proposal, Health Check, Approval Workflow,
          전문가 확인 판정 경로, 상담 패키지 생성·답변 반영 서비스

Phase 8.  Git Workspace + 부트스트랩
          Repository 등록·생성, 스캐폴딩 템플릿, commands.yaml 생성,
          CI 생성, Branch/Worktree, Lock, Scope 검사, Cleanup

Phase 9.  Model Adapter
          공통 Interface, JSON 추출·보정 재시도, Mock/Codex/ClaudeCode Adapter,
          결과 Schema 검증, Timeout, 오류 처리, Token 기록

Phase 10. Development Agent Workflow
          Supervisor, Coder, Reviewer, Repair Workflow, Release Agent

Phase 11. Ticket 및 GitHub
          InternalTicketProvider, Jira Adapter(옵션), GitHub Push,
          Draft PR, PR Comment, Webhook (Idempotency 포함)

Phase 12. Quality Gate
          명령 실행기, Scope/Rules/MCP Permission Validation,
          테스트, 빌드, 보안 검사

Phase 13. 산출물 패키징 및 전달
          Packager(유형별), Artifact Store, 스모크 테스트,
          UI 다운로드 API, DELIVERED 흐름

Phase 14. 병렬 실행
          Worker Pool, PostgreSQL Lock, File Intent Lock,
          Agent Expansion Lock, supervisord 설정

Phase 15. Web UI
          로그인, 프로젝트 목록, 대화 화면(질문 카드), 승인 화면,
          진행 상태(WebSocket), 결과 확인·다운로드, 히스토리,
          전문가 자문 화면(패키지 다운로드/복사, 답변 입력)

Phase 16. E2E 및 문서화
          Fake Jira/GitHub/MCP 기반 E2E, README(비개발자용/운영용), ARCHITECTURE.md
```

---

## 40. 테스트 요구사항

Unit Test

* Product/Development 상태 전환 (전환 테이블 기반, 예외 상태 복귀 경로 포함)
* Requirement 상태 관리 / CONFIRMED, INFERRED, UNKNOWN 처리
* 사용자 승인 검증 / Decision 충돌 탐지 / 적합도 분류 게이트
* Capability Gap 분석 / Agent Definition 검증 / MCP Permission 검증
* 자동 차단 정책 (결제, 개인정보, 운영 DB 요청 차단)
* 전문가 확인 필요 판정 및 상담 패키지 생성 (Secret 마스킹 검증 포함)
* 개발자 답변 입력 → 게이트 해제 → 체크포인트 복귀
* 위험도 계산 / Token Budget 계산 및 초과 복귀 / Scope Guard
* Rules 우선순위 / Webhook Idempotency / JSON 추출·보정 재시도

Integration Test

* PostgreSQL 상태 저장 / Project Memory 저장 / 체크포인트 재개
* Worktree 생성 및 삭제 / Lock 동작 / 부트스트랩 (임시 Repo 생성 → 스캐폴딩 → 검증)
* Mock Codex 실행 / Mock Claude Code 실행
* Agent Registry / MCP Registry / Approval Workflow
* InternalTicketProvider / Jira Client / GitHub Client
* 산출물 패키징 및 스모크 테스트 / 로그인 및 세션

End-to-End Test

실제 외부 서비스를 사용하지 않고 Fake Jira, Fake GitHub, Mock MCP를 사용한다.

```text
로그인
→ 기획안 입력
→ 적합도 분류 통과
→ 요구사항 초안 생성
→ 사용자 승인
→ PRD 생성
→ Capability Gap 분석
→ Internal Ticket 생성
→ Fake Repo 부트스트랩
→ Supervisor Mock 승인
→ 임시 Git Repository 수정
→ Coder Mock 실행
→ 테스트 통과
→ Fake PR 생성
→ Reviewer Mock 승인
→ Mock 패키징
→ Release Summary 생성
→ 사용자 승인 → Fake Merge → DELIVERED
→ Project Memory 갱신
→ COMPLETED 상태 확인
```

추가 E2E 1: 결제 기능이 포함된 기획안 입력 → 자동 차단 + 대안 제시 확인.
추가 E2E 2: 허용 목록 밖 MCP가 필요한 요청 → 상담 패키지 생성 → 개발자 답변 입력 → 게이트 해제 → 진행 확인.

실제 Codex, Claude Code, Jira, GitHub, MCP 호출은 opt-in 테스트로 분리한다.

---

## 41. 완료 기준

다음 조건을 모두 만족해야 MVP 완료로 판단한다.

1. 비개발자가 웹 UI에 로그인하고 기획안 문서를 업로드할 수 있다.
2. Core Agent가 프로젝트 목적, 기능, 사용자 흐름, 미확정 사항을 추출한다.
3. 프로젝트가 적합도 게이트로 분류되고, 위험 프로젝트(결제/민감 개인정보/운영 DB)는 자동 차단되며 대안이 제시된다.
4. 부족한 사항이 비개발자용 질문 카드로 UI에 표시된다.
5. 요구사항이 CONFIRMED, INFERRED, UNKNOWN으로 구분된다.
6. 사용자 승인 없이 개발 Ticket이 생성되지 않는다.
7. 승인된 요구사항으로 PRD와 Acceptance Criteria가 생성된다.
8. 산출물 유형이 명세에 포함되고 사용자 승인 카드에 표시된다.
9. Capability Gap 분석이 수행되고, 필요한 Agent와 MCP가 식별되며, 기존 자원을 우선 재사용한다.
10. 신규 Agent Definition이 Schema와 Permission 검증을 통과해야 등록된다.
11. 신규 MCP 연결은 Policy Engine 판정 없이 활성화되지 않는다.
12. 신규 프로젝트에 대해 GitHub Repository가 자동 생성되고, 스캐폴딩·commands.yaml·CI 설정이 함께 생성되며, 빈 프로젝트 상태에서 install/lint/test가 통과한다.
13. 동일 Webhook은 한 번만 처리된다.
14. Ticket마다 독립 Worktree와 Branch가 생성된다.
15. Supervisor와 Reviewer는 Codex Adapter로, Coder는 Claude Code Adapter로 실행된다.
16. 모든 Agent 결과는 Pydantic Schema로 검증되며, JSON 파싱 실패 시 보정 재시도가 동작한다.
17. 승인된 범위 밖 파일 변경은 차단된다.
18. Quality Gate 실패 시 PR이 생성되지 않는다.
19. Reviewer 수정 요청에 따라 제한된 Repair Workflow가 실행된다.
20. Token 사용량이 프로젝트, Task, Agent 단위로 저장되고, 초과 시 사용자 증액 승인 → 체크포인트 재개가 동작한다.
21. 동시 Task는 독립 Worktree에서 실행되고, 충돌 예상 파일은 동시에 수정되지 않는다.
22. 산출물이 패키징되어 UI에서 다운로드할 수 있고, 스모크 테스트를 통과한다.
23. Release Agent가 비개발자용 결과 설명과 기능 확인 체크리스트를 생성한다.
24. 사용자 승인 후에만 Merge가 수행되고 DELIVERED 상태가 된다.
25. 사용자 요구사항, Decision, Ticket, PR, 산출물이 Project Memory에 연결된다.
26. 모든 상태 변경, Agent 호출, MCP 사용, 파일 변경, 정책 판정이 Audit Log에 기록된다.
27. Docker Compose 기반으로 로컬 실행할 수 있다. (backend + frontend + db)
28. 진행 상태가 UI에 실시간 표시된다.
29. 전문가 확인이 필요한 요청과 반복 실패에 대해 2계층(비개발자 요약 + 개발자 상세) 상담 패키지가 생성되고, Secret이 마스킹되며, 답변 입력으로 게이트가 해제되거나 조정된다.

---

## 43. 최종 산출물

완료 후 다음 내용을 제공하라.

1. 전체 디렉터리 구조
2. Non-Developer Web UI 설명 및 화면 구성
3. Product Definition Engine 설명
4. Development Execution Engine 설명
5. Core Agent와 비개발자 간 대화 흐름
6. Core, Supervisor, Coder, Reviewer 데이터 흐름
7. 신규 프로젝트 부트스트랩 흐름
8. 산출물 패키징 및 전달 흐름
9. Project Memory 구조
10. Capability Registry 구조
11. Agent Factory 구조
12. MCP Registry, Allowlist, 승인·차단 정책
13. 전문가 상담 패키지 구조와 자문 흐름
14. 상태 머신 및 전환 테이블 설명
15. Ticket Provider 및 GitHub 연동 방법
16. Codex Adapter / Claude Code Adapter 설정 방법
17. Docker Compose 실행 방법
18. supervisord 실행 방법
19. 테스트 실행 방법
20. 환경변수 목록
21. 비개발자 사용 방법
22. MVP 구현 기능 / 제외 기능 / 알려진 제약사항
23. 보안상 주의사항 및 자동 차단·자문 정책 목록
24. 다음 개발 우선순위

---

## 44. 세션별 실행 계획

전체 구현은 다음 세션으로 나누어 진행한다.
**각 세션은 섹션 0의 프로토콜(PROGRESS.md 읽기/갱신, 테스트, 커밋)을 반드시 따른다.**
한 세션에서 다음 세션 범위를 미리 진행하지 않는다. 세션 범위가 크면 세션 내에서 추가 분할하되 `PROGRESS.md`에 기록한다.

```text
세션 1. 분석 + 계획 + 기반
  - Repository 구조와 실행 환경 분석
  - 기존 파일 및 설정과의 충돌 가능성 파악
  - IMPLEMENTATION_PLAN.md 작성 (상태 전환 테이블 포함)
  - Phase 1 (기반 프로젝트 + 로그인)
  종료 조건: docker compose up으로 API 헬스체크 통과, 로그인 동작, 기본 테스트 통과

세션 2. Product Definition
  - Phase 2 (Core/Requirement/Specification Agent Mock Workflow, 적합도 게이트)
  - Phase 3 (Project Memory, Decision Log)
  종료 조건: Mock 기반으로 기획안 → 요구사항 승인 → PRD 생성 흐름 테스트 통과

세션 3. 상태 머신 + Capability
  - Phase 4 (상태 머신, 전환 테이블, 체크포인트)
  - Phase 5 (Capability Registry, Gap Analyzer)
  종료 조건: 모든 상태 전환 + 예외 복귀 경로 단위 테스트 통과

세션 4. 확장 구조
  - Phase 6 (Agent Factory)
  - Phase 7 (MCP Registry, Allowlist, Policy Engine 4단 판정, 상담 패키지 서비스)
  종료 조건: 확장 Proposal → 판정 → 등록/차단/자문 흐름 테스트 통과
            (차단 케이스 + 상담 패키지 생성·답변 반영 케이스 포함)

세션 5. Git + Adapter
  - Phase 8 (Workspace, 부트스트랩, CI 생성)
  - Phase 9 (Model Adapter, JSON 추출·보정)
  종료 조건: 임시 Repo 부트스트랩 통과, MockAdapter 왕복 테스트 통과

세션 6. Development Workflow
  - Phase 10 (Supervisor/Coder/Reviewer/Repair/Release)
  - Phase 12 (Quality Gate)
  종료 조건: Mock 기반 Task 수신 → Quality Gate → Fake PR 흐름 테스트 통과

세션 7. 연동 + 전달 + 병렬
  - Phase 11 (Internal Ticket, GitHub, Webhook)
  - Phase 13 (패키징, Artifact Store, 다운로드 API)
  - Phase 14 (병렬 실행, Lock, supervisord)
  종료 조건: Ticket → 개발 → 패키징 → DELIVERED 흐름 테스트 통과

세션 8. Web UI
  - Phase 15 (전체 화면, WebSocket 상태, 승인 카드, 다운로드)
  종료 조건: 브라우저에서 로그인 → 기획안 입력 → 승인 → 상태 확인 → 다운로드 수동 확인

세션 9. 통합 마감
  - Phase 16 (E2E, 실 Adapter 연결: CodexAdapter, ClaudeCodeAdapter)
  - 전체 테스트 실행 및 실패 항목 수정
  - README(비개발자용/운영용), ARCHITECTURE.md를 실제 구현 상태에 맞게 작성
  종료 조건: 섹션 41의 완료 기준 전체 점검표 통과
```

설계 문서만 작성하고 종료하지 말고, 각 세션의 종료 조건을 실제로 만족하는 실행 가능한 코드를 구현하라.
