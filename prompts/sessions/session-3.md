# 세션 3 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 3이다: Phase 4(상태 머신) + Phase 5(Capability Registry).
필독 명세: docs/spec/04, 07, 10. IMPLEMENTATION_PLAN.md의 상태 전환 테이블을 기준으로 구현해라.

구현 범위: Product/Development 상태 머신, 선언적 전환 테이블, 전환 Guard, 체크포인트,
Idempotency, Retry, Timeout, Audit Log, Capability Schema, Provider 관리,
Gap Analyzer, Agent/MCP 매칭.

종료 조건: 모든 상태 전환 + 예외 상태 복귀 경로 단위 테스트 통과.
종료 시 PROGRESS.md 갱신 및 커밋.
