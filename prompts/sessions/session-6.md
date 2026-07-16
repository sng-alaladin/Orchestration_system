# 세션 6 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 6이다: Phase 10(Development Agent Workflow) + Phase 12(Quality Gate).
필독 명세: docs/spec/03, 07, 08, 10.

구현 범위: Supervisor/Coder/Reviewer Agent(MockAdapter 기반), Repair Workflow(횟수 제한),
Release Agent(기능 확인 체크리스트 포함), 명령 실행기(인자 분리 검증),
Scope/Rules/MCP Permission Validation, 테스트·빌드·보안 검사 Gate.

종료 조건: Mock 기반 Task 수신 → Quality Gate → Fake PR 흐름 테스트 통과.
종료 시 PROGRESS.md 갱신 및 커밋.
