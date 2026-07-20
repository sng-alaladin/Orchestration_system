# 구현 진행 상황

마지막 갱신: 2026-07-20 (세션 3 종료)

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

## 진행 중인 Phase

없음. (Phase 6 이후 미착수 — 세션 범위 준수)

## 다음 세션 시작 지점 (세션 4)

- 범위: Phase 6 (Agent Factory) + Phase 7 (MCP Registry, Allowlist, Policy Engine 4단 판정,
  전문가 상담 패키지 서비스).
- 필독 spec: `docs/spec/04, 05, 10`.
- 종료 조건: 확장 Proposal → 판정 → 등록/차단/자문 흐름 테스트 통과
  (차단 케이스 + 상담 패키지 생성·답변 반영 케이스 포함).
- 참고:
  - EXPANSION_PROPOSING 진입/이탈 전환은 이미 상태 머신에 존재(Guard는 `deferred:policy-engine@phase7`
    — 세션 4에서 실제 Policy Engine Guard로 교체할 것).
  - 상담 패키지 서비스 구현 시: `POST /api/projects/{id}/consultation`의 501 스텁을 대체하고,
    답변 반영 → `EXPERT_ANSWER_UNBLOCKS`(Guard: expert_confirmed_with_checkpoint —
    project_classification.expert_confirmed=true 설정 + 체크포인트 복귀)로 게이트 해제.
    workflow의 `EXPERT_CONSULTATION_NOT_READY` 상수/안내문 제거.
  - Capability Gap → 확장 Proposal 생성 연결 지점: `workflow._generate_specification`의
    GAP_FOUND 분기 (현재 명시적 미구현 안내만 남김).
  - 상담 패키지의 Secret 마스킹 검증 테스트 필수 (spec 10 §40).

## 알려진 이슈 / 임시 처리

- compose db는 호스트 15432로 노출(`POSTGRES_HOST_PORT`).
- `deferred:*` Guard 15종은 통과+로그만 한다 — 각 표기된 Phase에서 실제 검증으로 교체 필요
  (`transitions.py`에서 grep "deferred:" 로 전체 확인 가능).
- Development 머신은 엔진·전환 수준으로만 검증됨(전수 매트릭스). 실제 개발 실행 워크플로는
  Phase 10(세션 6). tasks 테이블은 최소 골격.
- Timeout 검사기는 수동 호출 서비스 — 주기 실행 Worker(Phase 14)에서 연결.
- 재분석 시 project_classification의 expert_confirmed는 최신 행에서 새 행으로 승계됨
  (재분류 루프 방지). 상담 서비스가 플래그를 설정하는 것은 세션 4 몫.
- Mock Agent 키워드 휴리스틱, SQLite 테스트 기반 등 기존 제약은 세션 2 기록 참조.
- TODO 주석: 코드 내 없음.

## 테스트 상태

- 최근 실행: 2026-07-20 (세션 3 종료 직전)
- `uv run pytest`: **198 passed, 0 failed**
  (unit 55 + integration 143 — 전환 매트릭스 118케이스 포함, SQLite in-memory)
- `uv run ruff check .` / `uv run mypy app`(strict): 통과
- Docker 재빌드 + PostgreSQL 3경로 검증(전문가 501 / Gap / 정상): 통과
