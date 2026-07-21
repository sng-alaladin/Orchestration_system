# 구현 진행 상황

마지막 갱신: 2026-07-21 (세션 4 종료)

## 완료된 Phase

### Phase 1 — 기반 프로젝트 (세션 1, 완료)

- uv/Python 3.12, FastAPI 앱 팩토리, structlog, pydantic-settings(`ORCH_` 접두).
- users/sessions + argon2id 로그인 API, 관리자 env 시드(멱등), 헬스체크.
- Docker Compose(db+api healthcheck), Alembic 0001. **시각 규약: DB는 naive UTC**(`app/core/clock.py`).

### Phase 2 — Product Definition Engine (세션 2, 완료 / Mock)

- Mock Core/Requirement/Specification Agent(결정론적) + Pydantic Schema(`app/product/`).
- 적합도 분류 게이트(`classifier.py` + `configs/auto-block-policy.yaml`).
- 문서 업로드/다운로드, PRD.md/BACKLOG.md 생성(project_documents, kind=GENERATED).
- API: projects/documents/requirements/approvals (로그인 + 소유권 검증).

### Phase 3 — Project Memory (세션 2, 완료)

- 요구사항 버전 관리, Decision Log(답변 자동 기록), Feedback, 충돌 탐지(질문 카드 생성).
- 마이그레이션 0002 (projects 등 9개 테이블).

### Phase 4 — 상태 머신 (세션 3, 완료)

- **단일 진실 원천**: `app/orchestrator/transitions.py` — IMPLEMENTATION_PLAN §6.1~6.4를
  1:1 인코딩(PRODUCT 51 + DEVELOPMENT 67개 전환, CHECKPOINT 센티널 포함).
  **테이블↔코드 완전 대조 테스트**(`tests/unit/test_transitions_match_plan.py`)가
  양방향 차이 0을 강제한다. 플랜 테이블 수정 시 이 테스트가 즉시 실패한다.
- 엔진(`state_machine.py`): fire() 단일 진입점. 테이블에 없는 전환은 IllegalTransition으로
  거부+감사 기록. Guard 거부는 GuardRejected. LLM은 상태를 변경하지 않는다.
- Guard(`transition_guard.py`): 구현 Guard 20종(승인 레코드/질문 상태/분류·expert_confirmed/
  산출물 존재/Capability Gap/체크포인트/재시도 한도). 근거 데이터가 없는 조건은
  `deferred:<설명>@<phase>`로 통과+로그 (해당 Phase에서 실제 Guard로 교체 — 위장 금지).
- 체크포인트(`checkpoints.py` + workflow_checkpoints): 예외 상태 진입 시 직전 상태 자동 저장,
  CHECKPOINT 목적지는 최신 체크포인트로 해석(없으면 명시적 거부).
- Idempotency: workflow_events.idempotency_key(unique) — 동일 key 재적용은 IDEMPOTENT_REPLAY.
- Retry: FAILED→RETRY_SCHEDULED에 can_retry Guard(기본 3회, `ORCH_MAX_RETRY_ATTEMPTS`),
  한도 초과 시 사용자 선택지(축소/중단/상담) 경로만 허용.
- Timeout(`timeout_checker.py` + `configs/state-timeouts.yaml`): WAITING_* 초과 시
  TIMEOUT_NOTIFIED 감사 기록 1회(상태 유지). 주기 실행 Worker는 Phase 14에서 연결.
- Audit Log(audit_logs, append-only): 모든 전환/거부/재생/타임아웃 기록.
- **workflow.py 통합 완료**: 세션 2의 `_LEGAL_TRANSITIONS`/`_set_status` 제거,
  모든 상태 변경이 ProductStateMachine.fire() 이벤트로 수행됨.
- 마이그레이션 0003 (audit_logs, workflow_events, workflow_checkpoints, tasks,
  capabilities, capability_providers). tasks는 Development 머신 검증용 최소 골격
  (pr_id·ticket 연동은 Phase 7/10에서 확장).

### Phase 5 — Capability Registry (세션 3, 완료)

- `app/capabilities/`: registry(설정 파일 → DB 멱등 동기화, `configs/capabilities.yaml`),
  matcher(priority → AGENT>MCP>LIBRARY → 이름순, available만), gap_analyzer, schemas.
- workflow 통합: 요구사항 승인 → PRD 생성 → **Gap 분석** → NO_GAP이면 Backlog →
  READY_FOR_DEVELOPMENT, GAP이면 EXPANSION_PROPOSING + 명시적 미구현 안내
  (확장 Proposal/Policy Engine은 세션 4). `email-send`는 의도적으로 미등록(갭 시연·테스트용).
- 기동 시 lifespan에서 Registry 동기화, 테스트/워크플로에서는 ensure_seeded로 자체 시드.

### 세션 3 추가 지시 이행

1. workflow 전이 로직 → transitions.py 상태 머신으로 이관·통합 완료 (위).
2. 테이블↔코드 대조 테스트 추가 완료 — 대조 과정에서 §6.3 AUTO_BLOCKED_BY_POLICY의
   ALTERNATIVE_ACCEPTED 목적지를 REQUIREMENT_DRAFTING → **DOCUMENT_ANALYZING으로 플랜 보정**
   (수정된 기획도 재분류 게이트를 다시 통과해야 차단 항목 잔존을 재차단할 수 있음 — 보안상 필수,
   세션 2 구현·테스트와도 일치).
3. WAITING_EXPERT_CONFIRMATION: 조용히 멈추지 않음 검증 —
   status_reason에 사유+미구현 안내+사용자 행동 지침 표시,
   `POST /api/projects/{id}/consultation`은 명시적 501,
   해당 상태에서 다른 단계 진행은 409 (`tests/integration/test_expert_and_gap_flow.py`).

### 세션 3 종료 조건 검증 (2026-07-20)

- 모든 상태 전환 + 예외 복귀 경로 단위 테스트: **전수 매트릭스 통과**
  (PRODUCT 51 + DEVELOPMENT 67 전환 각각 Guard 전제 준비 후 fire → 목적지 확인,
  체크포인트 복귀 포함. `tests/integration/test_all_transitions.py`).
- 테이블↔코드 대조 테스트 통과 (양방향 차이 0).
- 엔진 동작 테스트: 불법 전이 거부+감사, Guard 거부+감사, 멱등 재생, 체크포인트 자동 저장/복귀,
  재시도 한도(3회 후 거부 → 상담 경로), 전문가 확인 재분류 루프 방지.
- Docker(PostgreSQL) 검증: 마이그레이션 0003 자동 적용, 전문가 스텁(501)/Capability Gap
  (EXPANSION_PROPOSING)/정상 흐름(READY_FOR_DEVELOPMENT) 3경로 확인.
- `uv run pytest`: **198 passed** / ruff 0건 / mypy strict 0건.

### Phase 6 — Agent Factory (세션 4, 완료)

- `app/agents/`: schemas(AgentDefinition, spec 04 §15.3), validators(정의/권한/모델/MCP의존성/
  Token Budget/Sandbox 검증 체인 §16), registry(AgentDefinitionRecord — Core Agent 직접 쓰기 금지,
  Factory만 등록, project_scoped 만료), factory(assess: 검증→Policy 판정, register).
- 하드 불변 차단: 관리자 권한(perm.admin)·Secret 접근(perm.secret) 정의는 검증 단계에서 거부
  (Policy 이전). 미검증 권한 값/미등록 MCP 의존성/Token Budget 초과/미지원 모델도 거부.
- 프로젝트 범위·Secret 없음 Agent → 자동 승인, 네트워크/shell 확장·조직 공통 → 전문가 확인.

### Phase 7 — MCP Registry + Policy Engine + 자문 (세션 4, 완료)

- `app/mcp/`: schemas, registry(configs/mcp-servers.yaml → DB 멱등 동기화, tools eager-load),
  allowlist(configs/mcp-allowlist.yaml), health(Mock — 외부 네트워크/차단 상태 거부),
  connection(사용 유형 A/B/C/D 분류 §17.1 + Policy 입력 Proposal 생성).
- `app/policy/`: **결정론적 Policy Engine 4단 판정**(engine.py) — 차단>전문가>사용자>자동 순
  규칙 사다리, 첫 매칭 승, 미인식은 안전하게 사용자 승인으로 강등(조용한 자동 승인 금지).
  판정→상태 이벤트 매핑(PRODUCT_EXPANSION_EVENT / DEV_PLAN_EVENT). 최종 판정자는 LLM이 아닌 코드.
- `app/consultation/`: masking(Secret·개인정보 마스킹 — 키/값/PII 패턴, 과다 마스킹 허용),
  package(2계층 패키지 빌더 §19.5 — 전 필드 마스킹), service(영속화·답변 기록,
  원문 미저장·마스킹본만 저장).
- `app/expansion/`: planner(expansion-catalog.yaml로 부족 역량→Proposal),
  service(plan_and_judge: 계획→판정→expansion_proposals 감사기록, activate/approve_pending:
  자동·승인 확장을 MCP 승격+Capability Provider 등록으로 실제 활성화, build_expert_questions).
- workflow 통합: GAP_FOUND → `_resolve_expansion` → 4단 라우팅(자동=활성화+Backlog /
  사용자=WAITING_EXPANSION_APPROVAL / 전문가=상담 패키지+대기 / 차단=사유·대안).
  적합도 게이트 전문가 확인도 상담 패키지 생성. `decide_expansion`(EXPANSION 승인),
  `apply_consultation_answer`(UNBLOCK/ADJUST_SCOPE/STOP) 추가. **세션 3 스텁 제거**
  (EXPERT_CONSULTATION_NOT_READY 상수/501 삭제).
- API: `GET/POST /consultation`, `POST /consultation/answers`, 승인에 EXPANSION 추가.
- 마이그레이션 0004 (agent_definitions, mcp_servers, mcp_tools, expansion_proposals,
  expert_consultations). 기동 lifespan에서 MCP Registry도 동기화.

### 세션 4 추가 지시 이행

1. **새로 해소한 deferred Guard**: `deferred:policy-engine@phase7` **5건 전부 해소**
   (Product EXPANSION_PROPOSING 4 + Development SUPERVISING PLAN_AUTO_APPROVED 1)
   → 실제 `policy_decision_{auto_approve,user_approval,expert_required,auto_blocked}` Guard로 교체.
   이 Guard는 ctx["policy_decision"](결정론적 Policy Engine이 계산)이 전환을 인가하는지 검증한다.
   **남은 deferred Guard(해소 phase)**: phase8(bootstrap·worktree·scope-guard·rebase·cleanup=7),
   phase9(json-correction·budget-manager·core-output-schema·retry-policy=11),
   phase10(repair-limit·task-schema·dependency-check·context-package·replan-limit·review-schema·
   memory-update=12), phase11(git-push·pr-idempotency·webhook-idempotency=3), phase12(quality-gate=1),
   phase13(artifact-store·packaging=2), phase14(ticket-lock=1). (`grep "deferred:" transitions.py`)
2. **Secret 마스킹은 테스트로 증명**: `tests/unit/test_secret_masking.py` — password/API key/AWS key/
   JWT/Bearer/이메일/전화/주민번호/카드/DB URL 비밀번호를 실제로 심어 상담 패키지를 생성하고,
   패키지 본문·질문·요약 어디에도 원본 값이 남지 않음을 검증(마스킹 감지 요약도 비어있지 않음).

### 세션 4 종료 조건 검증 (2026-07-21)

- 확장 Proposal → 판정 → 등록/차단/자문 **네 경로 모두 통과** (`test_expansion_flow.py`):
  자동 승인(internal-doc-read→활성화로 Gap 해소) / 사용자 승인(ticket-management→approve_pending 등록) /
  전문가 확인(email-send→상담 패키지→UNBLOCK 답변→활성화·READY_FOR_DEVELOPMENT) /
  자동 차단(settlement-read→대안 제시). 판정→상태 머신 목적지도 4경로 모두 검증.
- Policy Engine 4단 단위 테스트(`test_policy_engine.py`, 규칙 우선순위 포함),
  Agent Factory 검증·판정·등록(`test_agent_factory.py`), MCP Registry/Allowlist/유형/Health
  (`test_mcp_registry.py`), Secret 마스킹(`test_secret_masking.py`).
- `uv run pytest`: **241 passed** / ruff 0건 / mypy strict 0건.
- Docker(PostgreSQL): 마이그레이션 0004 적용(5개 테이블) + 4경로 판정 + 상담 마스킹 스모크 통과.

## 진행 중인 Phase

없음. (Phase 8 이후 미착수 — 세션 범위 준수)

## 다음 세션 시작 지점 (세션 5)

- 범위: Phase 8 (Git Workspace + 부트스트랩 + CI 생성) + Phase 9 (Model Adapter, JSON 추출·보정).
- 필독 spec: `docs/spec/08, 09, 10`.
- 종료 조건: 임시 Repo 부트스트랩 통과, MockAdapter 왕복 테스트 통과.
- 참고:
  - Phase 8/9에서 `deferred:*@phase8`(bootstrap·worktree·scope-guard·rebase·cleanup),
    `deferred:*@phase9`(json-correction·budget-manager·core-output-schema·retry-policy) Guard를
    실제 검증으로 교체한다.
  - `agent_mode="live"`는 아직 명시적 오류 — Phase 9에서 Model Adapter 뒤로 연결.
  - Development 워크플로(Supervisor/Coder/Reviewer)는 Phase 10(세션 6). 현재 Development 머신의
    SUPERVISING PLAN_AUTO_APPROVED Guard는 Policy Engine 기반으로 이미 실제화됨(ctx로 판정 전달) —
    세션 6에서 실행 계획 판정을 ctx["policy_decision"]로 넣어 발화할 것.
  - 확장 UNBLOCK 시 대기(PENDING) Proposal 활성화는 `ExpansionService.approve_pending`가 담당.

## 알려진 이슈 / 임시 처리

- compose db는 호스트 15432로 노출(`POSTGRES_HOST_PORT`).
- alembic.ini에 한국어 주석이 있어 Windows 호스트에서 `alembic` CLI 직접 실행 시
  cp949 디코드 오류가 난다. 컨테이너 내부(UTF-8) 또는 ini를 읽지 않는 Python API
  (`Config(); set_main_option("script_location","migrations"); command.upgrade`)로 실행하면 정상.
- 감사 로그 정렬: `audit_logs`는 `(occurred_at, id)` 순. Windows에서 `datetime.now()` 해상도가
  거칠어 같은 tick의 두 레코드는 상대순서가 비결정적일 수 있다(모든 레코드는 정상 기록됨).
  순서 의존 테스트는 다중집합으로 검증한다.
- `deferred:*` Guard(현재 phase8~14) 는 통과+로그만 한다 — 각 표기된 Phase에서 실제 검증으로 교체 필요
  (`transitions.py`에서 grep "deferred:" 로 전체 확인 가능). policy-engine@phase7은 세션 4에서 해소됨.
- 확장 카탈로그(expansion-catalog.yaml)에 없는 역량은 "해결 방법 미정의" → 전문가 확인으로 안전 강등.
  AGENT 전략 해결은 카탈로그에 자리만 있고 현재 전문가 강등(프로젝트 전용 Agent 자동 생성은 후속).
- Development 머신은 엔진·전환 수준으로만 검증됨(전수 매트릭스). 실제 개발 실행 워크플로는
  Phase 10(세션 6). tasks 테이블은 최소 골격.
- Timeout 검사기는 수동 호출 서비스 — 주기 실행 Worker(Phase 14)에서 연결.
- 재분석 시 project_classification의 expert_confirmed는 최신 행에서 새 행으로 승계됨
  (재분류 루프 방지). 상담 서비스가 플래그를 설정하는 것은 세션 4 몫.
- Mock Agent 키워드 휴리스틱, SQLite 테스트 기반 등 기존 제약은 세션 2 기록 참조.
- TODO 주석: 코드 내 없음.

## 테스트 상태

- 최근 실행: 2026-07-21 (세션 4 종료 직전)
- `uv run pytest`: **241 passed, 0 failed**
  (세션 3 대비 +43: policy 4단·규칙 우선순위, Agent Factory 검증/판정, Secret 마스킹(심은 값 미노출),
  MCP Registry/Allowlist/유형/Health, 확장 4경로·상담 답변 반영. 전환 매트릭스 118케이스 포함, SQLite in-memory)
- `uv run ruff check .` / `uv run mypy app`(strict): 통과
- Docker + PostgreSQL 검증: 마이그레이션 0004 적용(agent_definitions/mcp_servers/mcp_tools/
  expansion_proposals/expert_consultations) + Policy 4경로 판정 + 상담 마스킹 스모크 통과.
