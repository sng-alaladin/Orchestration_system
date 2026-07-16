# 구현 진행 상황

마지막 갱신: 2026-07-16 (세션 1 종료)

## 완료된 Phase

### Phase 1 — 기반 프로젝트 (세션 1, 완료)

- 환경 분석: Windows 11 호스트, uv 0.11.26, Docker 29 + Compose v5. Python 3.12는 uv로 설치·고정(`.python-version`).
- `IMPLEMENTATION_PLAN.md` 작성 — **상태 전환 테이블 전체(Product/Development/예외 복귀 13종) 포함**. Phase 4 상태 머신 구현의 원본 정의로 사용할 것.
- uv 기반 Python 3.12 프로젝트 (`pyproject.toml`, hatchling, dependency-groups).
- FastAPI 앱 팩토리(`app/main.py` `create_app`) + structlog(`app/observability/logging.py`) + 접근 로그 미들웨어.
- 설정: `app/core/config.py` (pydantic-settings, `ORCH_` 접두, `.env` 지원). 인증정보 하드코딩 없음.
- DB: SQLAlchemy 2.x async (`app/db/`), users/sessions 모델, Alembic 초기 마이그레이션(`migrations/versions/0001_users_sessions.py`).
  - **시각 규약: DB에는 naive UTC로 저장** (`app/core/clock.py:utc_now`) — SQLite(테스트)/PostgreSQL 양쪽 호환 목적.
- 인증: argon2id 비밀번호 해시, 불투명 세션 토큰(SHA-256 해시만 저장), HttpOnly+SameSite=Lax 쿠키.
  - API: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` (204).
  - 계정 존재 여부 노출 방지(동일 401 메시지 + 더미 해시 검증).
- 관리자 시드: `ORCH_ADMIN_EMAIL`/`ORCH_ADMIN_PASSWORD` 설정 시 기동 때 1회 생성(멱등). `app/core/bootstrap.py`.
- 헬스체크: `GET /health`(생존), `GET /health/ready`(DB 포함).
- Docker: `Dockerfile`(python:3.12-slim + uv, 기동 시 `alembic upgrade head`), `docker-compose.yml`(db+api, 양쪽 healthcheck).

### 세션 1 종료 조건 검증 (2026-07-16)

- `docker compose up --build` → db·api 모두 healthy 확인.
- `GET /health` = ok, `GET /health/ready` = `{status: ok, database: up}`.
- 실 컨테이너 상대 로그인 E2E: login(200, 쿠키 발급) → me(200) → logout(204) → me(401), 오답 비밀번호(401) 확인.
- `uv run pytest` 23개 전체 통과, `ruff check` 0건, `mypy app` (strict) 0건.

## 진행 중인 Phase

없음. (Phase 1 완료, Phase 2 미착수 — 세션 범위 준수를 위해 선행 구현하지 않음)

## 다음 세션 시작 지점 (세션 2)

- 범위: Phase 2 (Product Definition Engine — Mock Workflow) + Phase 3 (Project Memory, Decision Log).
- 필독 spec: `docs/spec/01, 03, 06, 10` (`docs/spec/00-index.md` 매핑 참조).
- 종료 조건: Mock 기반 기획안 → 요구사항 승인 → PRD 생성 흐름 테스트 통과.
- 참고:
  - Agent 프롬프트 파일은 기존 `prompts/sessions/`(세션 지시문)와 충돌하지 않도록 `prompts/agents/`에 둘 것 (IMPLEMENTATION_PLAN §1).
  - Model Adapter는 Phase 9 범위지만, Phase 2에서 Mock Agent 호출이 필요하면 최소 Protocol + MockModelAdapter만 선작업하고 그 사실을 여기 기록할 것.
  - 상태 머신 구현(Phase 4)은 세션 3. Phase 2에서는 단순 상태 필드로 시작해도 되지만 상태 이름은 IMPLEMENTATION_PLAN §6의 정의를 따를 것.

## 알려진 이슈 / 임시 처리

- 호스트 5432 포트가 이미 점유되어 있어 compose의 db는 **호스트 15432**로 노출(`POSTGRES_HOST_PORT`, 기본 15432). 컨테이너 내부는 5432 그대로.
- 테스트는 SQLite(aiosqlite) 기반이라 PostgreSQL 방언 특화 동작(SKIP LOCKED 등)은 아직 검증 안 됨 → Phase 4(Queue) 구현 시 `@pytest.mark.integration`으로 PostgreSQL 테스트 추가 필요.
- 테스트는 FastAPI lifespan을 실행하지 않고 `dependency_overrides[get_db]` + `app.state.session_factory` 직접 주입으로 동작(`tests/conftest.py`). lifespan 경로 자체의 테스트는 없음.
- Windows PowerShell에서 한글 포함 파일을 `Set-Content`로 다루면 인코딩이 깨진다(세션 중 1회 발생, 복구 완료). 파일 수정은 반드시 Write/Edit 도구 사용.
- 감사 로그(audit_logs)는 Phase 4 범위 — 현재 로그인 성공/실패는 structlog로만 기록됨.
- TODO 주석: 현재 코드 내 TODO 없음.

## 테스트 상태

- 최근 실행: 2026-07-16 (세션 1 종료 직전)
- `uv run pytest`: **23 passed, 0 failed** (unit 10 + integration 13, SQLite in-memory, 외부 의존성 불필요)
- `uv run ruff check .`: 통과 / `uv run mypy app`(strict): 통과
- Docker 헬스체크 + 로그인 E2E: 통과 (위 종료 조건 검증 참조)
