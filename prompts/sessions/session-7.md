# 세션 7 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 7이다: Phase 11(Ticket·GitHub) + Phase 13(패키징·전달) + Phase 14(병렬 실행).
필독 명세: docs/spec/08, 09, 10.

구현 범위: InternalTicketProvider(기본), Jira Adapter(옵션, 동일 Interface),
GitHub Push, Draft PR, PR Comment, Webhook(Idempotency),
산출물 유형별 Packager, Artifact Store, 스모크 테스트, 다운로드 API,
사용자 승인 → 시스템 Merge → DELIVERED 흐름,
Worker Pool, PostgreSQL Lock, File Intent Lock, Agent Expansion Lock, supervisord 설정.

종료 조건: Ticket → 개발 → 패키징 → DELIVERED 흐름 테스트 통과.
종료 시 PROGRESS.md 갱신 및 커밋.
