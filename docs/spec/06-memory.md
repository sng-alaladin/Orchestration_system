# 06. Project Memory와 데이터 모델

## 20. Project Memory

비개발자가 프로젝트를 지속적으로 발전시키려면 단순 대화 기록이 아니라 구조화된 Project Memory가 필요하다.

저장 대상:

* 프로젝트 목표 / 핵심 사용자 / 현재 기능 / 미구현 기능 / 요구사항
* 사용자 승인 내역 / 추론된 요구사항 / 미확정 사항 / 과거 의사결정 / 폐기된 아이디어
* 사용자 흐름 / 화면 동작 / 데이터 구조 / 알려진 문제 / 기술 부채
* 버전 기록 / Ticket / GitHub PR / 배포·전달 기록 / 사용자 피드백
* 다음 개선 후보 / 활성 Agent / 활성 MCP / Capability Gap / 산출물 버전

### 20.1 Decision Log

모든 중요한 결정은 Decision Log에 저장한다.

```yaml
decision_id: DEC-014
title: 동일 파일명 처리 방식
decision: 기존 파일을 덮어쓰지 않고 번호를 붙인다
reason: 사용자가 기존 결과물을 실수로 잃지 않도록 하기 위함
source: user_confirmed
related_tasks: [DEV-142]
status: active
```

새로운 요청이 기존 결정과 충돌하면 Core Agent가 사용자에게 알려야 한다.

```text
기존에는 결과 파일을 덮어쓰지 않도록 결정했습니다.
이번 요청은 항상 같은 이름으로 저장하는 방식입니다.
기존 정책을 변경할까요?
```

---

## 35. 핵심 데이터 모델

최소한 다음 테이블을 설계한다.

```text
users
sessions

projects
project_versions
project_documents
project_commands
project_rules
project_classification      (적합도 분류 결과)

project_requirements
requirement_versions
requirement_questions
user_approvals
project_decisions
project_feedback
release_versions
artifacts                   (산출물 저장 메타데이터)

capabilities
capability_providers
agent_definitions
agent_versions
agent_permissions
agent_lifecycle_events

mcp_servers
mcp_tools
mcp_permissions
mcp_connections
mcp_health_checks
expansion_proposals
policy_decisions            (자동 승인/차단 판정 기록)
expert_consultations        (상담 패키지: 대상, 질문, 상태)
consultation_answers        (질문별 개발자 답변과 반영 조치)

tickets                     (InternalTicketProvider용)
tasks
task_plans
task_runs
task_steps
task_events
task_attempts
task_checkpoints

workspaces
branches
resource_locks
file_intent_locks

agent_calls
token_usage
quality_results
review_findings

integration_events
webhook_events
audit_logs
```

상태 변경과 중요한 의사결정은 Append-only Event로 저장한다.
모든 주요 테이블에 `user_id`를 포함한다.

---

