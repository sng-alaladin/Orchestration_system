# AI Orchestration System

비개발자가 기획안과 자연어만으로 서비스를 개발할 수 있는 확장형 AI Orchestration System.
전체 명세는 [docs/spec/](docs/spec/00-index.md), 구현 계획은 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md),
진행 상황은 [PROGRESS.md](PROGRESS.md)를 참조.

> 현재 상태: **Phase 1 (기반 프로젝트 + 로그인)** 완료. Web UI·Agent Workflow는 이후 세션에서 구현된다.

---

## 사용자용 (비개발자)

지금은 화면(Web UI)이 아직 없는 단계입니다. 시스템 준비가 끝나면 브라우저에서
로그인 → 기획안 입력 → 질문 답변 → 승인 → 결과물 다운로드 순서로 사용하게 됩니다.

관리자가 알려준 이메일과 비밀번호로 로그인하며, 비밀번호는 시스템에 안전하게(복원 불가능한 형태로) 저장됩니다.

---

## 운영자용 (개발자)

### 요구사항

- Docker + Docker Compose (권장 실행 방법)
- 또는 로컬 실행: [uv](https://docs.astral.sh/uv/) (Python 3.12는 uv가 자동 설치)

### 실행 (Docker Compose)

```bash
cp .env.example .env   # 값 수정 (특히 ADMIN_PASSWORD, SECRET 성격 값)
docker compose up --build
```

- API: http://localhost:8000 — 헬스체크 `GET /health`, 준비상태 `GET /health/ready`
- 컨테이너 시작 시 Alembic 마이그레이션이 자동 적용되고, `ADMIN_EMAIL`/`ADMIN_PASSWORD`로 관리자 계정이 시드된다(이미 있으면 건너뜀).

### 로그인 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | /api/auth/login | `{"email", "password"}` → 세션 쿠키 발급 |
| GET | /api/auth/me | 현재 로그인 사용자 |
| POST | /api/auth/logout | 세션 폐기 |

### 로컬 개발

```bash
uv sync                 # .venv 생성 + 의존성 설치
uv run pytest           # 테스트 (DB 불필요 — SQLite in-memory)
uv run ruff check .     # lint
uv run mypy app         # type check
```

### 환경변수

`.env.example` 참조. 모든 설정은 `ORCH_` 접두 환경변수로 주입되며 코드에 인증정보를 하드코딩하지 않는다.
