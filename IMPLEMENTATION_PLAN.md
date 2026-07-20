# IMPLEMENTATION_PLAN — AI Orchestration System

작성일: 2026-07-16 (세션 1) / 근거 명세: `docs/spec/` (마스터 v2.1 분할본)

---

## 1. 현재 Repository 상태

| 항목 | 상태 |
|---|---|
| 기존 파일 | `CLAUDE.md`, `docs/spec/*.md`(명세 11개), `prompts/sessions/*.md`(세션 프롬프트 9개) |
| 코드 | 없음 (이번 세션이 최초 구현) |
| Git | 미초기화 → 세션 1에서 `git init` 후 커밋 시작 |
| 충돌 가능성 | 없음. 단, 명세의 `prompts/` 디렉터리(Agent 프롬프트용)와 기존 `prompts/sessions/`(세션 지시문)가 같은 최상위 디렉터리를 공유함 → Agent 프롬프트는 `prompts/agents/`에 두어 충돌 회피 |

### 실행 환경 (2026-07-16 측정)

| 도구 | 버전 | 비고 |
|---|---|---|
| OS | Windows 11 Pro | 개발 호스트. 컨테이너는 Linux |
| Python | 3.14.6 (전역) | 명세는 3.12 고정 → **uv로 3.12 설치·고정** (`.python-version`) |
| uv | 0.11.26 | 패키징 표준 (명세 33) |
| Docker / Compose | 29.6.1 / v5.3.0 | 로컬 실행 기반 |
| git | 2.55.0.windows.1 | |
| Node | 24.18.0 | Phase 15(Web UI)에서 사용 |
| Codex / Claude Code CLI | 미확인 | Phase 9까지는 MockModelAdapter로 동작. 실 CLI는 세션 9에서 `--help` 확인 후 연동 |

---

## 2. 목표 Architecture

```text
[Non-Developer Web UI]  React 18 + TS + Vite  (Phase 15)
        │ REST + WebSocket
[FastAPI Orchestrator API]  Python 3.12
        │
        ├─ Product Definition Engine   (Core/Requirement/Specification/Release Agent)
        ├─ Development Execution Engine (Supervisor/Coder/Reviewer + Quality Gate)
        ├─ 결정론적 Orchestrator        (상태 머신·전환 테이블·체크포인트·Budget·승인)
        ├─ Policy Engine               (자동 승인/사용자 승인/전문가 확인/자동 차단)
        ├─ Expansion                   (Agent Factory, MCP Registry, Capability Registry)
        ├─ Workspace                   (Git Worktree, Lock, Scope Guard, 부트스트랩)
        ├─ Model Adapter               (Codex/ClaudeCode/Mock — Protocol 기반)
        └─ Workers (asyncio + PostgreSQL SKIP LOCKED Queue, supervisord 관리)
        │
[PostgreSQL]  상태 머신·Queue·Project Memory·Audit Log의 단일 진실 원천
```

원칙(불변):
- 상태 전환은 선언적 전환 테이블 + Guard 코드로만 수행한다. **LLM은 상태를 변경하지 않는다.**
- Agent 간에는 Pydantic Schema로 검증된 구조화 결과만 전달한다.
- 모든 상태 변경·Agent 호출·정책 판정은 Audit Log(Append-only)에 기록한다.
- Secret은 Agent Context에 전달하지 않는다. 사용자 승인 없는 Merge 금지.

## 3. MVP 범위

`docs/spec/10-plan.md` 섹션 38의 Vertical Slice 전체(로그인 → 기획안 → 분류 게이트 → 요구사항 승인
→ PRD/Backlog → 부트스트랩 → Supervisor/Coder/Reviewer → 패키징 → 사용자 승인 → Merge → DELIVERED).
자동 확장은 Proposal 생성·판정·등록까지, 외부 MCP 자동 설치·운영 배포·다중 사용자 등은 제외(섹션 38 제외 목록).
결제·법적 민감정보·운영 DB 프로젝트는 자동 차단.

## 4. 생성·수정 파일 (세션 1 / Phase 1)

```text
IMPLEMENTATION_PLAN.md          # 이 문서
PROGRESS.md                     # 세션 종료 시
pyproject.toml, uv.lock, .python-version
.env.example, .gitignore, .gitattributes
alembic.ini
migrations/env.py, script.py.mako, versions/0001_users_sessions.py
app/main.py                     # FastAPI 앱 팩토리 + lifespan(관리자 시드)
app/api/health.py               # GET /health, /health/ready
app/api/auth.py                 # POST /api/auth/login, /logout, GET /api/auth/me
app/core/config.py              # pydantic-settings, 전 설정 환경변수화
app/core/security.py            # argon2 해시, 세션 토큰 생성·해시
app/core/auth.py                # 세션 쿠키 → 현재 사용자 의존성
app/core/exceptions.py
app/db/base.py, session.py      # SQLAlchemy 2.x async
app/db/models/user.py, user_session.py
app/db/repositories/users.py, sessions.py
app/observability/logging.py    # structlog 구성
tests/conftest.py, tests/unit/*, tests/integration/*
Dockerfile, docker-compose.yml
README.md                       # 최소 실행 안내 (전체 문서화는 Phase 16)
```

이후 세션의 디렉터리 배치는 `docs/spec/09-tech.md` 섹션 34를 따른다.
(빈 디렉터리를 미리 만들지 않고, 각 Phase에서 실제 코드와 함께 추가한다.)

## 5. 구현 단계

Phase 1~16과 세션 1~9 매핑은 `docs/spec/10-plan.md` 섹션 39·44를 그대로 따른다(재기술 생략).
세션 1 내부 분할:

1. uv 프로젝트 초기화 (Python 3.12 고정, 의존성 설치)
2. 설정(`app/core/config.py`) + structlog + FastAPI 앱 골격 + `/health`
3. users/sessions 모델 + Alembic 초기 마이그레이션
4. 인증: argon2 비밀번호 해시, 불투명 세션 토큰(SHA-256 해시 저장), HttpOnly 쿠키
5. 관리자 계정 시드(환경변수 기반, 코드에 인증정보 없음)
6. 테스트: unit(보안 유틸·설정) + integration(SQLite 기반 로그인/로그아웃/me/헬스)
7. Dockerfile + docker-compose(db+api, 헬스체크) 검증
8. PROGRESS.md 작성, git init, 커밋

---

## 6. 상태 전환 테이블 (전체)

명세 `07-state-machine.md` 섹션 23 기준. 구현은 Phase 4(세션 3)에서 선언적 테이블
(`app/orchestrator/transitions.py`) + Guard 함수로 수행하며, 본 테이블이 그 원본 정의다.

표기: Guard는 전환 전 코드로 검증하는 조건. 모든 전환은 `task_events`/`audit_logs`에 기록,
전환 직전 상태는 체크포인트(`task_checkpoints`)로 저장되어 예외 상태에서 "직전 상태 복귀"에 사용된다.
`직전 상태`는 예외 상태 진입 시점에 체크포인트에 기록된 상태를 뜻한다.

### 6.1 Product Definition 상태 전환

| 현재 상태 | 이벤트 | 다음 상태 | Guard 조건 |
|---|---|---|---|
| IDEA_RECEIVED | ANALYSIS_STARTED | DOCUMENT_ANALYZING | 기획 텍스트 또는 문서 ≥ 1 존재, 프로젝트 활성 |
| DOCUMENT_ANALYZING | ANALYSIS_COMPLETED | CLASSIFYING | Core Agent 출력 Schema 검증 통과 |
| DOCUMENT_ANALYZING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | JSON 보정 재요청 2회 실패 |
| DOCUMENT_ANALYZING | ANALYSIS_FAILED | FAILED | 재시도 정책 소진 |
| CLASSIFYING | CLASSIFIED_SELF_SERVICE | REQUIREMENT_DRAFTING | 분류 결과 저장(project_classification) |
| CLASSIFYING | CLASSIFIED_AI_ASSISTED | WAITING_APPROVAL | 위험 기능 제외한 축소 범위안 생성 완료 |
| CLASSIFYING | CLASSIFIED_EXPERT_REVIEW | WAITING_EXPERT_CONFIRMATION | **전문가 확인 미완료(expert_confirmed=false)** + 상담 패키지 생성 완료(MVP 자동 차단 항목 미포함) |
| CLASSIFYING | EXPERT_CONFIRMED_PROCEED | REQUIREMENT_DRAFTING | **전문가 확인 완료(expert_confirmed=true)** — 확인 완료된 프로젝트는 CLASSIFIED_EXPERT_REVIEW로 재진입 불가(재분류 무한 루프 방지) |
| CLASSIFYING | CLASSIFIED_UNSUPPORTED | CANCELLED | 사유·대안 설명 생성 완료 |
| CLASSIFYING | PROHIBITED_SCOPE_DETECTED | AUTO_BLOCKED_BY_POLICY | 결제/법적 민감정보/운영 DB 감지 |
| REQUIREMENT_DRAFTING | DRAFT_HAS_UNKNOWNS | WAITING_REQUIREMENT_INPUT | UNKNOWN 요구사항 ≥ 1, 질문 카드 생성됨 |
| REQUIREMENT_DRAFTING | DRAFT_COMPLETED | WAITING_REQUIREMENT_APPROVAL | UNKNOWN 없음, CONFIRMED/INFERRED 구분 저장 |
| REQUIREMENT_DRAFTING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | 보정 2회 실패 |
| WAITING_REQUIREMENT_INPUT | USER_ANSWERED | REQUIREMENT_DRAFTING | 답변이 requirement_questions에 저장됨 |
| WAITING_REQUIREMENT_APPROVAL | REQUIREMENTS_APPROVED | SPECIFICATION_GENERATING | user_approvals에 승인 레코드 존재 |
| WAITING_REQUIREMENT_APPROVAL | CHANGES_REQUESTED | REQUIREMENT_DRAFTING | 사용자 피드백 저장됨 |
| SPECIFICATION_GENERATING | SPEC_COMPLETED | CAPABILITY_ANALYZING | PRD·AC·산출물 유형 생성, Schema 검증 통과 |
| SPECIFICATION_GENERATING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | 보정 2회 실패 |
| CAPABILITY_ANALYZING | NO_GAP_FOUND | BACKLOG_GENERATING | 기존 Agent/MCP로 충족 판정 |
| CAPABILITY_ANALYZING | GAP_FOUND | EXPANSION_PROPOSING | Capability Gap 목록 생성 |
| EXPANSION_PROPOSING | PROPOSAL_AUTO_APPROVED | BACKLOG_GENERATING | Policy Engine 자동 승인 + Sandbox 검증 통과 |
| EXPANSION_PROPOSING | PROPOSAL_NEEDS_USER | WAITING_EXPANSION_APPROVAL | 사용자 판단 가능 항목(기능·비용) |
| EXPANSION_PROPOSING | PROPOSAL_NEEDS_EXPERT | WAITING_EXPERT_CONFIRMATION | 전문가 확인 필요 판정, 상담 패키지 생성 |
| EXPANSION_PROPOSING | PROPOSAL_BLOCKED | AUTO_BLOCKED_BY_POLICY | 자동 차단 정책 해당 |
| WAITING_EXPANSION_APPROVAL | EXPANSION_APPROVED | BACKLOG_GENERATING | 승인 레코드 + Registry 등록 완료 |
| WAITING_EXPANSION_APPROVAL | EXPANSION_DENIED | EXPANSION_REJECTED | — |
| BACKLOG_GENERATING | BACKLOG_READY_NEW_REPO | BOOTSTRAPPING | Ticket 생성 완료, 신규 프로젝트 |
| BACKLOG_GENERATING | BACKLOG_READY_EXISTING | READY_FOR_DEVELOPMENT | Ticket 생성 완료, 기존 Repo 프로젝트 |
| BOOTSTRAPPING | BOOTSTRAP_COMPLETED | READY_FOR_DEVELOPMENT | Repo 생성 + 스캐폴딩 + install/lint/test 통과 |
| BOOTSTRAPPING | BOOTSTRAP_FAILED | FAILED | 재시도 소진 |
| DOCUMENT_ANALYZING · CLASSIFYING · REQUIREMENT_DRAFTING · SPECIFICATION_GENERATING · CAPABILITY_ANALYZING · EXPANSION_PROPOSING · BACKLOG_GENERATING | BUDGET_EXHAUSTED | TOKEN_BUDGET_EXCEEDED | LLM 호출 상태 공통: project_definition_limit의 hard_stop_ratio 도달 (복귀는 6.3) |

### 6.2 Development 상태 전환

| 현재 상태 | 이벤트 | 다음 상태 | Guard 조건 |
|---|---|---|---|
| RECEIVED | TASK_ACCEPTED | VALIDATING | Ticket Lock 획득, Repo 동시 실행 한도 내 |
| VALIDATING | VALIDATION_PASSED | CONTEXT_BUILDING | Task Schema·범위·의존성 유효 |
| VALIDATING | VALIDATION_FAILED | FAILED | 결함 사유 기록 |
| VALIDATING | DEPENDENCY_UNMET | WAITING_DEPENDENCY | 선행 Ticket 미완료 |
| CONTEXT_BUILDING | CONTEXT_READY | SUPERVISING | Context Package 생성(Hash 캐시 확인) |
| CONTEXT_BUILDING | INFO_MISSING | WAITING_INFORMATION | 필수 정보 부재, 사용자 질문 생성 |
| SUPERVISING | PLAN_AUTO_APPROVED | WORKSPACE_CREATING | 실행 계획 Schema 통과 + Policy 자동 승인 |
| SUPERVISING | PLAN_NEEDS_USER | WAITING_PLAN_APPROVAL | 사용자 판단 대상(기능 동작·비용) |
| SUPERVISING | PLAN_NEEDS_EXPERT | WAITING_EXPERT_CONFIRMATION | 전문가 확인 필요 판정 |
| SUPERVISING | PLAN_BLOCKED | AUTO_BLOCKED_BY_POLICY | 금지 항목 포함 |
| SUPERVISING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | 보정 2회 실패 |
| WAITING_PLAN_APPROVAL | PLAN_APPROVED | WORKSPACE_CREATING | 승인 레코드 존재 |
| WAITING_PLAN_APPROVAL | PLAN_REJECTED | SUPERVISING | 피드백 반영 재계획(횟수 제한 내) |
| WORKSPACE_CREATING | WORKSPACE_READY | IMPLEMENTING | Worktree+Branch 생성, File Intent Lock 획득 |
| WORKSPACE_CREATING | LOCK_CONFLICT | CONFLICTED | 충돌 파일 Lock 보유자 존재 |
| IMPLEMENTING | CODE_COMPLETED | LOCAL_VALIDATING | Scope Guard 통과(승인 범위 밖 변경 없음) |
| IMPLEMENTING | BUDGET_EXHAUSTED | TOKEN_BUDGET_EXCEEDED | hard_stop_ratio 도달 |
| IMPLEMENTING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | 보정 2회 실패 |
| IMPLEMENTING | IMPLEMENT_FAILED | FAILED | Coder 재시도 소진 |
| LOCAL_VALIDATING | QUALITY_GATE_PASSED | COMMITTING | 테스트·정적분석·보안검사 전체 통과 |
| LOCAL_VALIDATING | QUALITY_GATE_FAILED | REPAIRING | repair 시도 < max_test_repairs |
| LOCAL_VALIDATING | REPAIR_LIMIT_EXCEEDED | WAITING_USER_REVIEW | 한도 초과 → 선택지 제시 |
| COMMITTING | PUSHED | PR_CREATING | Commit·Push 성공 (main 직접 Push 아님) |
| COMMITTING | BASE_DRIFT_DETECTED | CONFLICTED | Base Branch Drift 검사 실패 |
| PR_CREATING | PR_CREATED | CI_RUNNING | **멱등**: Task에 연결된 기존 PR(tasks.pr_id)이 있으면 신규 생성 없이 기존 PR 재사용(Branch Push 반영만) — Repair 사이클 재진입 시 PR 중복 생성 금지. pr_id가 없을 때만 Draft PR 생성 후 기록 |
| PR_CREATING | PR_CREATE_FAILED | FAILED | 재시도 소진 |
| CI_RUNNING | CI_PASSED | REVIEWING | CI 결과 수신(Webhook Idempotent 처리) |
| CI_RUNNING | CI_FAILED | REPAIRING | repair 시도 한도 내 |
| REVIEWING | REVIEW_APPROVED | PACKAGING | Reviewer 결과 Schema 통과, 차단 Finding 없음 |
| REVIEWING | REVIEW_CHANGES_REQUESTED | REPAIRING | review repair < max_review_repairs |
| REVIEWING | AGENT_OUTPUT_INVALID | AGENT_VALIDATION_FAILED | 보정 2회 실패 |
| REPAIRING | REPAIR_COMPLETED | LOCAL_VALIDATING | 총 시도 ≤ max_total_attempts(5) |
| REPAIRING | REPAIR_LIMIT_EXCEEDED | WAITING_USER_REVIEW | 한도 초과, 상황·선택지 사용자 언어 제시 |
| REPAIRING | BUDGET_EXHAUSTED | TOKEN_BUDGET_EXCEEDED | hard_stop_ratio 도달 |
| PACKAGING | PACKAGE_READY | WAITING_USER_REVIEW | 산출물 패키징 + 스모크 테스트 통과 |
| PACKAGING | PACKAGING_FAILED | REPAIRING | 시도 한도 내, 아니면 FAILED |
| WAITING_USER_REVIEW | USER_APPROVED | READY_FOR_MERGE | 결과 승인 레코드 존재 |
| WAITING_USER_REVIEW | USER_FEEDBACK | REPAIRING | feedback repair < max_user_feedback_repairs |
| WAITING_USER_REVIEW | USER_CANCELLED | CANCELLED | — |
| READY_FOR_MERGE | MERGE_COMPLETED | MERGED | **사용자 승인 레코드 필수**, PR Lock 획득 |
| READY_FOR_MERGE | MERGE_CONFLICT | CONFLICTED | — |
| MERGED | DELIVERED_TO_USER | DELIVERED | 산출물 다운로드 가능, Release 설명 생성 |
| DELIVERED | MEMORY_UPDATED | CLEANUP | Project Memory·Decision Log 갱신 완료 |
| CLEANUP | CLEANUP_COMPLETED | COMPLETED | Worktree 제거, 모든 Lock 해제 |

### 6.3 Product 예외 상태 복귀 경로

Product에서 발생 가능한 예외: WAITING_APPROVAL, WAITING_EXPERT_CONFIRMATION, BLOCKED, FAILED,
CANCELLED, TOKEN_BUDGET_EXCEEDED, EXPANSION_REJECTED, MCP_CONNECTION_FAILED,
AGENT_VALIDATION_FAILED, AUTO_BLOCKED_BY_POLICY.
(WAITING_INFORMATION·WAITING_DEPENDENCY·CONFLICTED는 Development 전용이다. Product의 사용자
입력·승인 대기는 전용 상태 WAITING_REQUIREMENT_INPUT / WAITING_REQUIREMENT_APPROVAL /
WAITING_EXPANSION_APPROVAL로 모델링된다.)
**복귀 목적지는 전부 Product 상태다. SUPERVISING 등 Development 전용 상태로 복귀하지 않는다.**

| 예외 상태 | 복귀 이벤트 | 다음 상태 | Guard / 비고 |
|---|---|---|---|
| WAITING_APPROVAL | APPROVAL_GRANTED | REQUIREMENT_DRAFTING | 축소 범위(AI_ASSISTED) 승인 레코드 존재 |
| WAITING_APPROVAL | APPROVAL_DENIED | CANCELLED | 거절 사유 기록. 다른 축소안 제안 시 CLASSIFYING부터 신규 재시작 |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_UNBLOCKS | 직전 상태 (체크포인트) | 답변 기록(consultation_answers) + **게이트를 유발한 판정 항목에 확인 완료 플래그(expert_confirmed=true) 기록 후 복귀** → 동일 사유로 WAITING_EXPERT_CONFIRMATION 재진입 금지. 직전 상태가 CLASSIFYING이면 6.1의 "전문가 확인 미완료" Guard에 걸려 CLASSIFIED_EXPERT_REVIEW로 재진입 불가, EXPERT_CONFIRMED_PROCEED 경로로만 진행(재분류 무한 루프 방지) |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_ADJUSTS_SCOPE | REQUIREMENT_DRAFTING | 답변에 따른 범위 조정을 반영해 요구사항 재작성 |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_STOPS | CANCELLED | 장기 미응답 시 리마인드 알림(상태 유지) |
| BLOCKED | BLOCK_RESOLVED | 직전 상태 (체크포인트) | 차단 원인 해소 이벤트. 시간 초과 시 사용자 알림 |
| FAILED | RETRY_SCHEDULED | 직전 상태 (체크포인트) | recovery_worker, 재시도 정책 한도 내 |
| FAILED | RETRY_EXHAUSTED_SCOPE_DOWN | REQUIREMENT_DRAFTING | 사용자 선택: 범위 축소 후 요구사항 재작성 |
| FAILED | RETRY_EXHAUSTED_CONSULT | WAITING_EXPERT_CONFIRMATION | 사용자 선택: "개발자에게 물어볼 자료 만들기" → 상담 패키지 생성 |
| FAILED | RETRY_EXHAUSTED_STOP | CANCELLED | 사용자 선택: 중단 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_INCREASE_APPROVED | 직전 상태 (체크포인트) | 사용량·예상 추가량·비용 표시 후 증액 승인. 저성능 모델 자동 전환 금지 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_INCREASE_DENIED | REQUIREMENT_DRAFTING | 범위 축소 제안 수락 시 요구사항 재작성 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_DENIED_STOP | CANCELLED | 축소 제안도 거절 |
| EXPANSION_REJECTED | SCOPE_REDUCED_RETRY | BACKLOG_GENERATING | 기존 Capability만으로 축소 Backlog 재생성 |
| EXPANSION_REJECTED | REJECT_ACCEPTED_STOP | CANCELLED | — |
| MCP_CONNECTION_FAILED | MCP_RETRY_SUCCEEDED | 직전 상태 (체크포인트) | Sandbox/health check 통과 |
| MCP_CONNECTION_FAILED | MCP_ALTERNATIVE_SELECTED | EXPANSION_PROPOSING | 기존 MCP 대안으로 Proposal 재작성 |
| MCP_CONNECTION_FAILED | MCP_RETRY_EXHAUSTED | WAITING_EXPERT_CONFIRMATION | 상담 패키지 생성 |
| AGENT_VALIDATION_FAILED | CORRECTION_SUCCEEDED | 직전 상태 (체크포인트) | 보정 재요청(최대 2회) 내 성공. 원본 출력은 Audit Log 저장 |
| AGENT_VALIDATION_FAILED | CORRECTION_EXHAUSTED | FAILED | FAILED 복귀 경로를 따름 |
| AUTO_BLOCKED_BY_POLICY | ALTERNATIVE_ACCEPTED | DOCUMENT_ANALYZING | 차단 요소를 제외하도록 수정된 기획으로 재분석 — **재분류 게이트 재통과 필수**(차단 요소가 남아 있으면 다시 차단됨) |
| AUTO_BLOCKED_BY_POLICY | BLOCK_ACKNOWLEDGED_STOP | CANCELLED | 사유·대안은 사용자 언어로 설명(우회 불가) |
| CANCELLED | (터미널) | — | 재시작은 신규 요청으로만 |

### 6.4 Development 예외 상태 복귀 경로

Development에서 발생 가능한 예외: WAITING_INFORMATION, WAITING_DEPENDENCY,
WAITING_EXPERT_CONFIRMATION, BLOCKED, CONFLICTED, FAILED, CANCELLED, TOKEN_BUDGET_EXCEEDED,
MCP_CONNECTION_FAILED, AGENT_VALIDATION_FAILED, AUTO_BLOCKED_BY_POLICY.
(EXPANSION_REJECTED·WAITING_APPROVAL은 Product 전용이다. Development의 사용자 승인 대기는
전용 상태 WAITING_PLAN_APPROVAL / WAITING_USER_REVIEW로 모델링된다.)

| 예외 상태 | 복귀 이벤트 | 다음 상태 | Guard / 비고 |
|---|---|---|---|
| WAITING_INFORMATION | INFO_PROVIDED | 직전 상태 (체크포인트) | 답변 저장 완료. 장기 미응답 시 리마인드 알림 |
| WAITING_DEPENDENCY | DEPENDENCY_RESOLVED | 직전 상태 (체크포인트) | 선행 Ticket 완료 이벤트. 시간 초과 시 사용자 알림 |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_UNBLOCKS | 직전 상태 (체크포인트) | 답변 기록(consultation_answers) + 게이트를 유발한 판정 항목에 확인 완료 플래그 기록 → 동일 사유로 재진입 금지 |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_ADJUSTS_SCOPE | SUPERVISING | 범위 조정 후 재계획 재진입 |
| WAITING_EXPERT_CONFIRMATION | EXPERT_ANSWER_STOPS | CANCELLED | 장기 미응답 시 리마인드 알림(상태 유지) |
| BLOCKED | BLOCK_RESOLVED | 직전 상태 (체크포인트) | 차단 원인 해소 이벤트. 시간 초과 시 사용자 알림 |
| CONFLICTED | REBASE_SUCCEEDED | LOCAL_VALIDATING | Base Drift rebase 성공 → 재검증부터 재개 |
| CONFLICTED | REBASE_FAILED | SUPERVISING | Supervisor 재계획 |
| FAILED | RETRY_SCHEDULED | 직전 상태 (체크포인트) | recovery_worker, 재시도 정책 한도 내 |
| FAILED | RETRY_EXHAUSTED_SCOPE_DOWN | SUPERVISING | 사용자 선택: 범위 축소 후 재계획 |
| FAILED | RETRY_EXHAUSTED_CONSULT | WAITING_EXPERT_CONFIRMATION | 사용자 선택: "개발자에게 물어볼 자료 만들기" → 상담 패키지 생성 |
| FAILED | RETRY_EXHAUSTED_STOP | CANCELLED | 사용자 선택: 중단 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_INCREASE_APPROVED | 직전 상태 (체크포인트) | 증액 승인(사용량·예상 추가량·비용 표시). 저성능 모델 자동 전환 금지 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_INCREASE_DENIED | SUPERVISING | 범위 축소 제안 수락 시 재계획 |
| TOKEN_BUDGET_EXCEEDED | BUDGET_DENIED_STOP | CANCELLED | 축소 제안도 거절 |
| MCP_CONNECTION_FAILED | MCP_RETRY_SUCCEEDED | 직전 상태 (체크포인트) | health check 통과 |
| MCP_CONNECTION_FAILED | MCP_ALTERNATIVE_SELECTED | SUPERVISING | 기존 MCP 대안을 반영해 재계획 |
| MCP_CONNECTION_FAILED | MCP_RETRY_EXHAUSTED | WAITING_EXPERT_CONFIRMATION | 상담 패키지 생성 |
| AGENT_VALIDATION_FAILED | CORRECTION_SUCCEEDED | 직전 상태 (체크포인트) | 보정 재요청(최대 2회) 내 성공. 원본 출력은 Audit Log 저장 |
| AGENT_VALIDATION_FAILED | CORRECTION_EXHAUSTED | FAILED | FAILED 복귀 경로를 따름 |
| AUTO_BLOCKED_BY_POLICY | ALTERNATIVE_ACCEPTED | SUPERVISING | 차단 요소를 제외한 대안 범위로 재계획 |
| AUTO_BLOCKED_BY_POLICY | REQUIREMENT_CHANGE_NEEDED | CANCELLED | 요구사항 자체 변경 필요 → Task 종결 후 축소 요구사항으로 Product 흐름(REQUIREMENT_DRAFTING) 신규 재시작 |
| AUTO_BLOCKED_BY_POLICY | BLOCK_ACKNOWLEDGED_STOP | CANCELLED | 사유·대안은 사용자 언어로 설명(우회 불가) |
| CANCELLED | (터미널) | — | 재시작은 신규 Ticket으로만 |

공통 규칙:
- 예외 상태 진입 시 직전 진행 상태·진행 산출물을 체크포인트로 저장하고, 복귀는 항상 체크포인트 기반 재개다(처음부터 재실행 금지).
- 위 테이블에 없는 전환은 전부 불법 전환으로 코드에서 거부하고 Audit Log에 기록한다.
- 모든 대기(WAITING_*) 상태는 타임아웃 시 사용자 알림 이벤트를 발생시킨다(상태는 유지).

---

## 7. 기술적 위험

| 위험 | 완화 |
|---|---|
| Codex/Claude Code CLI 부재·옵션 상이 | Adapter Protocol + MockModelAdapter로 전 흐름 개발, 실 CLI는 `--help` 확인 후 연동(추측 하드코딩 금지) |
| CLI가 JSON Schema 출력 미보장 | JSON 추출 파서 + 보정 재요청 2회 + AGENT_VALIDATION_FAILED 전환 |
| Windows 호스트 ↔ Linux 컨테이너 차이 (경로·줄바꿈·Worktree) | 실행은 Docker 기준, `.gitattributes`로 LF 강제, Worktree 경로는 설정으로 분리 |
| PostgreSQL Queue 경합·중복 처리 | SKIP LOCKED + Idempotency Key + task_attempts 기록 |
| 테스트가 Docker/Postgres에 의존 | unit·API 테스트는 SQLite(aiosqlite)로 실행, Postgres 통합 테스트는 opt-in 마커 분리 |
| SQLite/PostgreSQL 방언 차이 | 포터블 타입만 사용(Uuid, String, DateTime naive-UTC 규약), DB 시각 함수 의존 금지 |
| 상태 머신 복잡도 증가 | 선언적 전환 테이블 단일 원본 + 전환 테이블 기반 단위 테스트 의무화 |

## 8. 보안 위험

| 위험 | 대응 |
|---|---|
| 인증정보 하드코딩 | 전 설정 환경변수(pydantic-settings). 관리자 계정은 env로 시드, .env는 gitignore |
| 세션 토큰 탈취 | 토큰은 SHA-256 해시로만 저장, HttpOnly+SameSite=Lax 쿠키, 만료·폐기 지원 |
| 비밀번호 저장 | argon2id 해시(argon2-cffi). 평문·복호화 가능 저장 금지 |
| Prompt Injection (Repo 문서 내 지시문) | Agent 프롬프트에 불신 원칙 명시 + 도구 권한 최소화(Phase 10) + 사용자 승인 게이트 |
| Agent 권한 과다 | Agent별 허용 명령어·경로 제한, Secret 미전달, Worktree 밖 접근 차단(Phase 8~12) |
| 사용자 승인 없는 Merge | READY_FOR_MERGE Guard가 승인 레코드를 코드로 검증. main 직접 Push 금지 |
| 감사 추적 부재 | audit_logs Append-only, 모든 전환·Agent 호출·정책 판정 기록(Phase 4) |

## 9. 테스트 방법

- **Unit**: pytest. DB 불요 또는 SQLite in-memory. 보안 유틸, 설정, (Phase 4~) 상태 전환 테이블·예외 복귀 경로 전수 검증.
- **Integration**: httpx `ASGITransport`로 API 왕복(로그인/세션), SQLite 기본. Postgres·Worktree·부트스트랩은 `@pytest.mark.integration`(로컬 Docker 필요) 분리.
- **E2E**(Phase 16): Fake GitHub/Jira/MCP + Mock Adapter로 섹션 40의 3개 시나리오.
- 실 Codex/Claude Code/GitHub 호출은 opt-in 마커로 격리. CI 없는 환경에서도 `uv run pytest`가 통과해야 한다.
- Lint/Type: Ruff + mypy. 실행 명령: `uv run pytest`, `uv run ruff check .`, `uv run mypy app`.

## 10. 미확정 사항

| 항목 | 현재 가정 | 확정 시점 |
|---|---|---|
| Codex/Claude Code CLI 실제 옵션 | Mock으로 대체 | 세션 9 (`--help` 실측) |
| GitHub 대상 조직·인증 방식 | PAT 환경변수 가정 | 세션 7 |
| Jira 사용 여부 | InternalTicketProvider 기본, Jira는 옵션 | 세션 7 |
| 산출물 저장 위치 | 로컬 볼륨(artifacts/) | 세션 7 |
| 관리자 초기 계정 | env(ADMIN_EMAIL/ADMIN_PASSWORD) 시드 | 운영 전 변경 필수 |
| Temporal 도입 | 도입 안 함(PostgreSQL 상태 머신), 인터페이스만 추상화 | MVP 이후 |

## 11. 제외 범위 (MVP)

`docs/spec/10-plan.md` 섹션 38 제외 목록 전체를 따른다: 승인되지 않은 외부 MCP 자동 설치,
신규 MCP 운영 자동 배포, 사용자 승인 없는 Merge, Production 자동 배포, 다중 Repo 동시 수정,
다중 사용자/조직 권한, Agent 자체 권한 변경, Core Agent/Orchestrator 자체 수정,
완전 자율 Architecture 변경, 결제·법적 민감정보·운영 DB 연동 프로젝트(자동 차단).
