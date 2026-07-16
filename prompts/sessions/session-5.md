# 세션 5 시작 프롬프트

CLAUDE.md와 PROGRESS.md를 읽고 세션 프로토콜에 따라 시작해라.
이번은 세션 5다: Phase 8(Git Workspace + 부트스트랩) + Phase 9(Model Adapter).
필독 명세: docs/spec/08, 09, 10.

구현 범위: Repository 등록·생성(GitHub App), 언어별 스캐폴딩 템플릿, commands.yaml 생성,
CI(GitHub Actions) 생성, Branch/Worktree 관리, Lock, Scope 검사, Cleanup,
Model Adapter 공통 Interface, JSON 추출·보정 재시도(최대 2회), MockModelAdapter,
결과 Schema 검증, Timeout, 오류 처리, Token 기록.
CodexAdapter와 ClaudeCodeAdapter의 실 구현은 세션 9로 미루되 Interface는 확정해라.

종료 조건: 임시 Repo 부트스트랩 통과(빈 프로젝트에서 install/lint/test 성공),
MockAdapter 왕복 테스트 통과.
종료 시 PROGRESS.md 갱신 및 커밋.
