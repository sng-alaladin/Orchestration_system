# 구현 진행 상황

마지막 갱신: 2026-07-16 (세션 2 종료)

## 완료된 Phase

### Phase 1 — 기반 프로젝트 (세션 1, 완료)

- uv 기반 Python 3.12 프로젝트, FastAPI 앱 팩토리(`app/main.py`), structlog, 접근 로그 미들웨어.
- 설정: `app/core/config.py` (pydantic-settings, `ORCH_` 접두). 인증정보 하드코딩 없음.
- users/sessions + argon2id 로그인 API (`POST /api/auth/login`, `GET /me`, `POST /logout`).
- 관리자 시드(`ORCH_ADMIN_EMAIL/PASSWORD`, 멱등), 헬스체크(`/health`, `/health/ready`).
- Docker Compose(db+api healthcheck), Alembic 0001. **시각 규약: DB는 naive UTC**(`app/core/clock.py`).
- 세션 1 종료 검증: compose 헬스체크 + 로그인 E2E + 테스트 23개 통과.

### Phase 2 — Product Definition Engine (세션 2, 완료 / Mock 수준)

- **Agent Schema** (`app/product/schemas.py`): CoreAnalysis / RequirementSet / SpecificationResult /
  ClassificationResult 등 Pydantic Schema. Agent 간에는 구조화 결과만 전달.
- **Mock Agent 3종** (결정론적, 동일 입력=동일 출력):
  - `MockCoreAgent`(`core_agent.py`): 문장·키워드 기반 FR 추출(CONFIRMED), 표준 미확정 2건(UNKNOWN)
    + 질문 카드, capability 매핑, 산출물 유형 추정.
  - `MockRequirementAgent`(`requirement_agent.py`): 답변된 UNKNOWN → CONFIRMED 승격,
    표준 보강(NFR/BR/EX) 추가.
  - `MockSpecificationAgent`(`specification_agent.py`): PRD 마크다운 + AC + Epic/Story/Task.
  - 실 LLM 연동은 Protocol 뒤에서 Phase 9(세션 5)에 교체. `agent_mode != "mock"`은 명시적 오류
    (미구현 위장 금지).
- **적합도 분류 게이트** (`classifier.py` + `configs/auto-block-policy.yaml`):
  결제/민감 개인정보/운영 DB → AUTO_BLOCKED_BY_POLICY(대안 제시),
  위험 기능 → WAITING_APPROVAL(축소 범위 승인), 전문가 키워드 → WAITING_EXPERT_CONFIRMATION,
  범위 밖 → CANCELLED. 키워드 정책은 설정 파일로 분리.
- **Workflow** (`app/product/workflow.py`): IDEA_RECEIVED → … → READY_FOR_DEVELOPMENT.
  허용 전이 집합(`_LEGAL_TRANSITIONS`)으로 불법 전이 차단. 상태 변경은 코드로만.
  승인 없으면 PRD/Backlog 생성 안 됨(409). 거절 시 피드백 저장 후 재초안.
  차단 후 기획 수정 → 재분석(ALTERNATIVE_ACCEPTED 경로) 동작.
- **문서 업로드/다운로드** (`app/api/documents.py`): UTF-8 텍스트 1MB 제한, 업로드 문서가
  분석 입력에 포함됨. 생성 산출물(PRD.md/BACKLOG.md)은 project_documents(kind=GENERATED)로 저장.
- **API**: `app/api/projects.py`(생성/목록/상세/PATCH 기획/analyze), `requirements.py`(요구사항·질문·답변),
  `approvals.py`(REQUIREMENTS/REDUCED_SCOPE 승인). 전부 로그인 + 소유권 검증(타인 프로젝트 404).

### Phase 3 — Project Memory (세션 2, 완료)

- `app/project_memory/`: requirement_store(버전 관리 sync — 변경 시 version++/이력 기록,
  제외 시 is_active=False 보존), version_store, decision_log(DEC-nnn, active/superseded),
  feedback_store, conflict_detector(토큰 겹침 기반 잠재 충돌 → 사용자 확인 질문 카드 생성),
  service(Facade).
- 질문 답변은 자동으로 Decision Log에 기록(user_confirmed)되고 PRD "반영된 의사결정"에 표시.
- DB: 마이그레이션 0002 — projects, project_documents, project_classification,
  project_requirements, requirement_versions, requirement_questions, user_approvals,
  project_decisions, project_feedback (전부 user_id 연결, CASCADE).

### 세션 2 종료 조건 검증 (2026-07-16)

- Mock 기반 기획안 → 질문 답변 → 요구사항 승인 → PRD 생성 흐름: **API 통합 테스트 통과**
  (`tests/integration/test_product_flow.py`).
- Docker(PostgreSQL) 컨테이너 상대 동일 플로우 수동 검증: IDEA_RECEIVED → WAITING_REQUIREMENT_INPUT(질문 2)
  → WAITING_REQUIREMENT_APPROVAL → READY_FOR_DEVELOPMENT + PRD.md/BACKLOG.md 생성 확인.
- `uv run pytest` 49개 통과, ruff 0건, mypy strict 0건.

## 진행 중인 Phase

없음. (Phase 4 이후는 미착수 — 세션 범위 준수)

## 다음 세션 시작 지점 (세션 3)

- 범위: Phase 4 (상태 머신 — 선언적 전환 테이블, Guard, 체크포인트, Idempotency, Retry,
  Timeout, Audit Log) + Phase 5 (Capability Registry, Gap Analyzer).
- 필독 spec: `docs/spec/04, 07, 10`.
- 종료 조건: 모든 상태 전환 + 예외 복귀 경로 단위 테스트 통과.
- 참고:
  - 전환 테이블 원본 정의는 IMPLEMENTATION_PLAN.md §6 (Product/Development/예외 복귀 분리본).
  - Phase 2의 임시 전이 가드(`app/product/workflow.py`의 `_LEGAL_TRANSITIONS`,`_set_status`)를
    Phase 4의 정식 상태 머신(`app/orchestrator/`)으로 대체하고 workflow가 그것을 쓰도록 리팩터링할 것.
  - `expert_confirmed` 플래그는 project_classification에 이미 존재(재분류 무한 루프 방지용).
  - Capability 스텁: `workflow._generate_specification`의 CAPABILITY_ANALYZING 통과 스텁
    (NO_GAP_FOUND 고정, 로그 남김)을 Phase 5 Gap Analyzer로 대체할 것.
  - Audit Log 도입 시 Phase 2의 상태 변경 지점(`_set_status`)이 단일 진입점이므로 거기 연결하면 됨.

## 알려진 이슈 / 임시 처리

- compose db는 호스트 15432로 노출(`POSTGRES_HOST_PORT`). 호스트 5432 점유 때문.
- Mock Agent는 키워드 휴리스틱이므로 한국어 위주 기획안에 최적화됨. 실 LLM 교체 전까지의
  의도된 제약(세션 5/9에서 CodexAdapter/ClaudeCodeAdapter로 교체).
- WAITING_EXPERT_CONFIRMATION 진입은 되지만 상담 패키지 생성·답변 반영은 Phase 7(세션 4) 범위.
  현재는 상태+사유 기록만 된다.
- 충돌 탐지는 토큰 겹침(≥2) 휴리스틱 — 과탐지 허용 설계. 합의(포함 관계)는 제외됨.
- Workflow의 재분석은 MockCoreAgent를 매번 재실행(결정론적이라 안전). LLM 전환 시
  분석 결과 캐시/저장 필요 — Phase 9에서 처리.
- 테스트는 SQLite 기반. PostgreSQL 특화 동작(SKIP LOCKED 등)은 Phase 4 Queue 구현 시
  `@pytest.mark.integration`으로 추가 필요.
- TODO 주석: 코드 내 없음.

## 테스트 상태

- 최근 실행: 2026-07-16 (세션 2 종료 직전)
- `uv run pytest`: **49 passed, 0 failed** (unit 26 + integration 23, SQLite in-memory)
- `uv run ruff check .` / `uv run mypy app`(strict): 통과
- Docker 재빌드 + 컨테이너 플로우 검증: 통과 (마이그레이션 0002 자동 적용 확인)
