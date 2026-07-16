# 09. 기술 기반 — Model Adapter, 기술 스택, 디렉터리 구조, Process Supervisor

## 26. Model Adapter 구조

Agent와 AI 모델을 직접 결합하지 않는다.

```python
from typing import Protocol


class ModelAdapter(Protocol):
    async def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        working_directory: str | None = None,
        timeout_seconds: int = 600,
    ) -> "ModelResult":
        ...
```

구현 Adapter:

```text
CodexAdapter
ClaudeCodeAdapter
MockModelAdapter
```

기본 할당:

```yaml
agents:
  core:          {provider: codex, adapter: CodexAdapter}
  requirement:   {provider: codex, adapter: CodexAdapter}
  specification: {provider: codex, adapter: CodexAdapter}
  supervisor:    {provider: codex, adapter: CodexAdapter}
  coder:         {provider: claude-code, adapter: ClaudeCodeAdapter}
  reviewer:      {provider: codex, adapter: CodexAdapter}
  release:       {provider: codex, adapter: CodexAdapter}
```

* 실제 CLI 옵션과 인증 방식은 환경변수와 설정 파일로 분리한다.
* 설치된 Codex와 Claude Code의 공식 도움말(`--help`)을 확인한 뒤 Adapter를 구현한다.
* 특정 CLI 옵션을 추측해 하드코딩하지 않는다.
* **구조화 출력 처리**: CLI가 JSON Schema 출력을 보장하지 않는 경우를 전제로 구현한다.
  * 출력에서 JSON 블록을 추출하는 파서를 구현한다.
  * 파싱 또는 Schema 검증 실패 시, 실패 사유와 함께 최대 2회까지 보정 재요청한다.
  * 최종 실패 시 `AGENT_VALIDATION_FAILED`로 전환하고 원본 출력을 Audit Log에 저장한다.

---

## 33. 기술 스택

선택지는 남기지 않고 다음으로 확정한다.

```text
Backend             Python 3.12
API                 FastAPI
Validation          Pydantic
Database            PostgreSQL
ORM                 SQLAlchemy 2.x
Migration           Alembic
Queue               PostgreSQL 기반 자체 Queue (SKIP LOCKED 패턴)
Worker              자체 Worker (asyncio 기반)
Process Management  supervisord
Frontend            React 18 + TypeScript + Vite
Realtime            FastAPI WebSocket
SCM                 GitHub
Ticket              InternalTicketProvider (기본) / Jira Adapter (옵션)
HTTP Client         httpx
Logging             structlog
Tracing             OpenTelemetry
Test                pytest (+ frontend: vitest)
Lint                Ruff (+ frontend: eslint)
Type Check          mypy (+ frontend: tsc)
Packaging           uv
Container           Docker Compose
```

초기 MVP는 PostgreSQL 상태 머신으로 구현한다.
Workflow가 복잡해지면 Temporal을 도입할 수 있도록 Workflow 인터페이스를 추상화한다.

---

## 34. 권장 디렉터리 구조

```text
ai-orchestrator/
├── frontend/
│   ├── src/
│   │   ├── pages/          # 프로젝트 목록, 대화, 승인, 상태, 결과, 히스토리
│   │   ├── components/     # 채팅, 질문 카드, 승인 카드, 상태 타임라인, 다운로드
│   │   ├── api/            # REST + WebSocket 클라이언트
│   │   └── stores/
│   ├── package.json
│   └── vite.config.ts
│
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   ├── conversations.py
│   │   ├── documents.py
│   │   ├── projects.py
│   │   ├── requirements.py
│   │   ├── approvals.py
│   │   ├── artifacts.py          # 산출물 다운로드
│   │   ├── ws_status.py          # WebSocket 상태 스트림
│   │   ├── jira_webhook.py
│   │   ├── github_webhook.py
│   │   ├── tasks.py
│   │   ├── agents.py
│   │   └── mcp_servers.py
│   │
│   ├── product/
│   │   ├── core_agent.py
│   │   ├── requirement_agent.py
│   │   ├── specification_agent.py
│   │   ├── release_agent.py
│   │   ├── question_generator.py
│   │   ├── requirement_compiler.py
│   │   ├── classifier.py          # 프로젝트 적합도 분류
│   │   └── backlog_generator.py
│   │
│   ├── project_memory/
│   │   ├── service.py
│   │   ├── decision_log.py
│   │   ├── requirement_store.py
│   │   ├── version_store.py
│   │   ├── feedback_store.py
│   │   └── conflict_detector.py
│   │
│   ├── capabilities/
│   │   ├── analyzer.py
│   │   ├── gap_analyzer.py
│   │   ├── matcher.py
│   │   ├── registry.py
│   │   └── schemas.py
│   │
│   ├── agent_factory/
│   │   ├── definition_generator.py
│   │   ├── definition_validator.py
│   │   ├── sandbox_validator.py
│   │   ├── registrar.py
│   │   └── lifecycle_manager.py
│   │
│   ├── mcp/
│   │   ├── registry.py
│   │   ├── allowlist.py           # 승인된 외부 MCP 허용 목록
│   │   ├── discovery.py
│   │   ├── connection_manager.py
│   │   ├── permission_policy.py
│   │   ├── health_checker.py
│   │   ├── sandbox_validator.py
│   │   └── proposal_service.py
│   │
│   ├── expansion/
│   │   ├── proposal_service.py
│   │   ├── policy_engine.py
│   │   ├── approval_service.py
│   │   ├── consultation_service.py   # 전문가 상담 패키지 생성·답변 반영
│   │   └── activation_service.py
│   │
│   ├── orchestrator/
│   │   ├── service.py
│   │   ├── state_machine.py
│   │   ├── product_state_machine.py
│   │   ├── development_state_machine.py
│   │   ├── transitions.py         # 전환 테이블 (선언적 정의)
│   │   ├── transition_guard.py
│   │   ├── checkpoints.py
│   │   ├── task_router.py
│   │   ├── risk_engine.py
│   │   ├── budget_manager.py
│   │   └── approval_policy.py
│   │
│   ├── agents/
│   │   ├── base.py
│   │   ├── runtime.py
│   │   ├── registry.py
│   │   ├── supervisor_agent.py
│   │   ├── coder_agent.py
│   │   ├── reviewer_agent.py
│   │   └── schemas.py
│   │
│   ├── model_adapters/
│   │   ├── base.py
│   │   ├── json_extractor.py      # CLI 출력 → JSON 추출 + 보정 재시도
│   │   ├── codex_adapter.py
│   │   ├── claude_code_adapter.py
│   │   └── mock_adapter.py
│   │
│   ├── project_bootstrap/
│   │   ├── repo_creator.py        # GitHub Repo 생성
│   │   ├── scaffolder.py          # 언어별 스캐폴딩
│   │   ├── templates/             # python/, typescript/ 등
│   │   ├── ci_generator.py        # GitHub Actions 생성
│   │   ├── document_parser.py
│   │   ├── project_compiler.py
│   │   ├── repository_mapper.py
│   │   ├── rules_generator.py
│   │   ├── command_generator.py
│   │   └── change_detector.py
│   │
│   ├── delivery/
│   │   ├── packager.py            # 산출물 유형별 패키징
│   │   ├── artifact_store.py
│   │   └── smoke_tester.py
│   │
│   ├── context/
│   │   ├── builder.py
│   │   ├── repository_search.py
│   │   ├── symbol_index.py
│   │   ├── chunk_store.py
│   │   └── context_cache.py
│   │
│   ├── workspace/
│   │   ├── worktree_manager.py
│   │   ├── branch_manager.py
│   │   ├── lock_manager.py
│   │   ├── scope_guard.py
│   │   └── cleanup.py
│   │
│   ├── quality/
│   │   ├── gate_runner.py
│   │   ├── command_runner.py
│   │   ├── diff_analyzer.py
│   │   ├── rules_validator.py
│   │   └── security_checker.py
│   │
│   ├── tickets/
│   │   ├── base.py                # TicketProvider Protocol
│   │   ├── internal_provider.py
│   │   └── jira_provider.py
│   │
│   ├── integrations/
│   │   ├── jira_client.py
│   │   ├── github_client.py
│   │   └── webhook_security.py
│   │
│   ├── workers/
│   │   ├── product_worker.py
│   │   ├── task_worker.py
│   │   ├── review_worker.py
│   │   ├── expansion_worker.py
│   │   ├── packaging_worker.py
│   │   ├── cleanup_worker.py
│   │   └── recovery_worker.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── models/
│   │   └── repositories/
│   │
│   ├── observability/
│   │   ├── logging.py
│   │   ├── metrics.py
│   │   ├── tracing.py
│   │   └── token_ledger.py
│   │
│   └── core/
│       ├── config.py
│       ├── security.py
│       ├── auth.py
│       ├── exceptions.py
│       └── enums.py
│
├── configs/
│   ├── agents.yaml
│   ├── capabilities.yaml
│   ├── mcp-registry.yaml
│   ├── mcp-allowlist.yaml
│   ├── risk-policy.yaml
│   ├── expansion-policy.yaml
│   ├── auto-block-policy.yaml
│   ├── token-budget.yaml
│   └── concurrency.yaml
│
├── prompts/
│   ├── core-agent.md
│   ├── requirement-agent.md
│   ├── specification-agent.md
│   ├── supervisor.md
│   ├── coder.md
│   ├── reviewer.md
│   ├── release-agent.md
│   └── expansion-proposal.md
│
├── templates/
│   ├── product-brief.md
│   ├── prd.md
│   ├── user-flows.md
│   ├── acceptance-criteria.md
│   └── decision-log.md
│
├── supervisor/
│   └── supervisord.conf
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── PROGRESS.md
├── README.md
└── ARCHITECTURE.md
```

---

## 36. Process Supervisor 설정

다음 Worker를 supervisord로 관리한다.

```text
orchestrator-api
product-worker
task-worker
review-worker
expansion-worker
packaging-worker
cleanup-worker
recovery-worker
```

supervisord는 프로세스 생존만 관리한다.
Workflow 상태는 PostgreSQL이 관리한다.
AI Supervisor Agent와 supervisord를 코드와 문서에서 혼용하지 않는다.

---

