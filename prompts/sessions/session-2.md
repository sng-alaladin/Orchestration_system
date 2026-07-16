# 세션 2 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 2다: Phase 2(Product Definition Engine) + Phase 3(Project Memory).
필독 명세: docs/spec/01, 03, 06, 10.

구현 범위: 문서 업로드, Core/Requirement/Specification Agent의 Pydantic Schema와
Mock Workflow, 적합도 분류 게이트, 질문 생성, 요구사항 상태(CONFIRMED/INFERRED/UNKNOWN),
사용자 승인, PRD·Backlog 생성, Requirement 저장, Decision Log, Version 관리,
Feedback 저장, 충돌 탐지.

종료 조건: Mock 기반으로 기획안 → 요구사항 승인 → PRD 생성 흐름 테스트 통과.
종료 시 PROGRESS.md 갱신 및 커밋.
