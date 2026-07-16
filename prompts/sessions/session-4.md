# 세션 4 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 4다: Phase 6(Agent Factory) + Phase 7(MCP Registry + 자문 구조).
필독 명세: docs/spec/04, 05, 10.

구현 범위: Agent Definition Schema, Definition/Permission/Sandbox Validator,
Agent Registry, Lifecycle 관리, MCP Server/Tool Registry, Allowlist,
Permission Policy, Connection Proposal, Health Check,
Policy Engine 4단 판정(자동 승인/사용자 승인/전문가 확인 필요/자동 차단),
전문가 상담 패키지 생성·답변 반영 서비스(Secret 마스킹 포함).

종료 조건: 확장 Proposal → 판정 → 등록/차단/자문 흐름 테스트 통과
(차단 케이스 + 상담 패키지 생성·답변 반영 케이스 포함).
종료 시 PROGRESS.md 갱신 및 커밋.
