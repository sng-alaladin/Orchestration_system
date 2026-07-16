# 00. 명세 문서 인덱스

이 디렉터리는 AI Orchestration System의 전체 명세(마스터 프롬프트 v2.1)를 주제별로 분할한 것이다.
**이번 세션 범위에 해당하는 문서만 읽어라.** 전체 원본은 `docs/spec/_master-v2.1.md`에 보존되어 있다
(참조용, 평소에는 읽지 않는다).

## 문서 목록

| 문서 | 내용 |
|---|---|
| 01-overview.md | 역할·전제, 최종 사용자, 핵심 목표, 자동 개발 Workflow, 적합도 진입 게이트 |
| 02-ui.md | Non-Developer Web UI 화면 명세, 승인 구조, 사용자용 상태 표시 |
| 03-agents.md | 7개 Agent의 역할·모델 할당·입출력 Schema (Core~Release) |
| 04-expansion.md | Agent 자동 확장, Agent Factory, MCP Registry, Capability Registry |
| 05-policy.md | Policy Engine 4단 판정, 전문가 상담 패키지, 보안 요구사항 |
| 06-memory.md | Project Memory, Decision Log, 핵심 데이터 모델(테이블) |
| 07-state-machine.md | Product/Development/예외 상태, 전환 테이블 의무, Token Budget, Repair |
| 08-workspace.md | Repo 부트스트랩, 산출물 패키징·전달, Ticket, Worktree·Lock, Rules, Quality Gate, commands.yaml |
| 09-tech.md | Model Adapter(JSON 보정 포함), 기술 스택, 디렉터리 구조, supervisord |
| 10-plan.md | MVP 범위, Phase 1~16, 테스트 요구사항, 완료 기준, 세션별 실행 계획 |

## 세션별 필독 문서 매핑

| 세션 | 범위 | 필독 문서 |
|---|---|---|
| 세션 1 | 분석 + IMPLEMENTATION_PLAN + Phase 1 기반 | 01, 07, 09, 10 (계획 수립을 위해 나머지는 훑어보기) |
| 세션 2 | Product Definition + Project Memory | 01, 03, 06, 10 |
| 세션 3 | 상태 머신 + Capability Registry | 04, 07, 10 |
| 세션 4 | Agent Factory + MCP Registry + 자문 구조 | 04, 05, 10 |
| 세션 5 | Git Workspace·부트스트랩 + Model Adapter | 08, 09, 10 |
| 세션 6 | Development Workflow + Quality Gate | 03, 07, 08, 10 |
| 세션 7 | Ticket·GitHub 연동 + 패키징 + 병렬 실행 | 08, 09, 10 |
| 세션 8 | Web UI | 02, 05(자문 화면), 10 |
| 세션 9 | E2E + 실 Adapter + 문서화 | 09, 10 + PROGRESS.md 전체 점검 |
