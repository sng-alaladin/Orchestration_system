# 세션 1 시작 프롬프트 (복사해서 Claude Code에 입력)

CLAUDE.md와 docs/spec/00-index.md를 읽어라.
이번은 세션 1이다: 환경 분석 + IMPLEMENTATION_PLAN.md 작성 + Phase 1(기반 프로젝트) 구현.

1. 현재 Repository 구조와 실행 환경을 분석하고, 기존 파일과의 충돌 가능성을 파악해라.
2. docs/spec/의 01, 07, 09, 10을 정독하고 나머지 문서는 목차 수준으로 훑어 전체 그림을 잡아라.
3. IMPLEMENTATION_PLAN.md를 작성해라. 상태 전환 테이블 전체(예외 상태 복귀 경로 포함)를 반드시 포함해라.
4. Phase 1을 구현해라: Python 프로젝트 초기화, FastAPI, PostgreSQL, SQLAlchemy, Alembic,
   Pydantic, structlog, Docker Compose, 기본 테스트 환경, users/sessions 테이블과 기본 로그인 API.

종료 조건: docker compose up으로 API 헬스체크 통과, 로그인 동작, 기본 테스트 통과.
종료 시 세션 프로토콜에 따라 PROGRESS.md를 작성하고 커밋해라.
