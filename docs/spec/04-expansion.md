# 04. 확장 구조 — Agent Factory, MCP Registry, Capability Registry

## 15. Agent 자동 확장 구조

### 15.1 확장 원칙

Core Agent는 기획안을 분석한 뒤 필요한 Capability를 추출한다.

```json
{
  "required_capabilities": ["excel-read", "data-validation", "docx-generate", "email-send"]
}
```

Capability Registry와 비교한다.

```json
{
  "available": ["excel-read", "data-validation"],
  "reusable_with_extension": ["docx-generate"],
  "missing": ["email-send"]
}
```

다음 우선순위로 해결한다.

```text
1. 기존 Agent 재사용
2. 기존 Agent에 Rule 추가
3. 기존 Agent에 Skill 추가
4. 기존 MCP 활성화
5. 임시 Task Agent 생성
6. 프로젝트 전용 Agent 생성
7. 신규 MCP 연결
8. 신규 MCP Server 구현
9. 조직 공통 Agent 또는 MCP 등록
```

불필요하게 Agent를 새로 생성하지 않는다.

### 15.2 Agent 생성 기준

다음 조건 중 여러 개를 만족할 때 별도 Agent를 생성한다.

* 독립된 도메인 지식이 필요함 / 다른 권한 범위를 사용함 / 별도의 모델이 적합함
* 독립적으로 병렬 실행할 수 있음 / 별도의 품질 기준이 필요함
* Context 격리가 필요함 / 여러 Task에서 반복 사용됨

다음과 같은 단순 작업은 별도 Agent를 만들지 않는다.

* 버튼 문구 변경 / 파일명 변경 / 테스트 한 개 추가 / 단순 API 필드 추가 / 작은 UI 수정

### 15.3 Agent Definition 예시

```yaml
id: excel-report-agent
name: Excel Report Agent
version: 1.0.0

purpose:
  엑셀 데이터를 분석하고 보고서 생성용 구조화 데이터를 생성한다.

model:
  provider: claude-code
  adapter: ClaudeCodeAdapter

scope:
  project_id: report-automation
  allowed_paths:
    - src/reporting/**
    - tests/reporting/**

capabilities:
  - inspect_excel_schema
  - transform_tabular_data
  - generate_report_payload

mcp_dependencies:
  - filesystem-readonly
  - document-generator

permissions:
  filesystem: read_write_scoped
  network: denied
  shell: allowlisted

rules:
  - 원본 엑셀 파일을 수정하지 않는다
  - 계산 결과에는 검증 근거를 포함한다
  - 보고서 생성 전 데이터 누락 여부를 확인한다

quality_gates:
  - schema_validation
  - unit_test
  - output_validation

token_budget:
  max_input_tokens: 30000
  max_output_tokens: 10000

lifecycle:
  type: project_scoped
  expires_after_project: true
```

---

## 16. Agent Factory

Agent Factory는 Core Agent가 생성한 Agent Definition을 검증하고 등록한다.

처리 순서:

```text
Agent Definition 생성
→ JSON/YAML Schema 검증
→ 권한 검증
→ 모델 사용 가능 여부 검증
→ MCP 의존성 검증
→ Token Budget 검증
→ Sandbox Test
→ Policy Engine 판정 (자동 승인 / 사용자 승인 / 전문가 확인 필요 / 자동 차단)
→ Agent Registry 등록
```

Core Agent가 Agent Registry에 직접 쓰지 못하도록 한다.
Agent 등록 승인의 최종 판정자는 LLM(Supervisor Agent)이 아니라 **결정론적 Policy Engine**이다.

---

## 17. MCP Registry 및 자동 연결

MCP는 모델이 아니라 AI Agent가 외부 도구와 데이터를 사용할 수 있게 하는 연결 계층으로 취급한다.

MCP Server는 다음 정보를 Registry에 등록한다.

```yaml
id: jira-mcp
name: Jira MCP
status: approved

capabilities:
  - read_issue
  - create_issue
  - add_comment
  - transition_issue

permissions:
  read:
    - jira:issue
  write:
    - jira:comment
    - jira:transition

risk_level: medium
requires_user_approval:
  - create_issue
  - transition_issue
```

### 17.1 MCP 사용 유형

```text
유형 A. 기존 승인 MCP 자동 활성화
        읽기 전용이며 낮은 위험도의 MCP는 정책에 따라 자동 활성화할 수 있다.

유형 B. 기존 MCP의 쓰기 기능 활성화
        사용자 승인을 요구한다. 단, 사용자 승인 가능 범위(섹션 19)를 벗어나면 자동 차단한다.

유형 C. 신규 외부 MCP 연결
        사전 등록된 허용 목록(curated allowlist)에 있는 MCP만 사용자 승인으로 연결할 수 있다.
        목록에 없는 MCP는 자동 차단하고 사유를 설명한다.

유형 D. 신규 MCP Server 개발
        Coder Agent가 구현하고 Reviewer와 Sandbox 검증을 거친 뒤 등록한다.
        외부 네트워크 접근이 필요한 MCP는 MVP에서 자동 차단한다.
```

### 17.2 신규 MCP Proposal 예시

```json
{
  "type": "MCP_SERVER_PROPOSAL",
  "name": "internal-settlement-mcp",
  "reason": "현재 Registry에 사내 정산 시스템 접근 기능이 없음",
  "required_capabilities": ["search_settlement", "read_settlement_detail"],
  "data_classification": "CONFIDENTIAL",
  "requested_permissions": ["settlement:read"],
  "write_access_required": false,
  "authentication_type": "service_account",
  "risk_level": "HIGH",
  "policy_decision": "AUTO_BLOCKED",
  "blocked_reason": "기밀 데이터 접근은 현재 시스템 정책상 자동 연결할 수 없습니다"
}
```

### 17.3 Core Agent가 할 수 없는 MCP 작업

* 임의의 인터넷 MCP Server 설치 / 인증정보 직접 생성 / Secret 조회
* 관리자 권한 부여 / 운영 DB 쓰기 권한 활성화 / 데이터 삭제 도구 활성화
* 외부 데이터 전송 승인 / 정책 엔진 우회 / MCP Server 검증 생략

---

## 18. Capability Registry

현재 시스템이 제공할 수 있는 모든 역량을 관리한다.

```yaml
capabilities:
  - id: source-code-edit
    providers:
      agents: [coder-agent]

  - id: code-review
    providers:
      agents: [reviewer-agent]

  - id: requirement-analysis
    providers:
      agents: [requirement-agent]

  - id: ticket-management
    providers:
      mcp_servers: [jira-mcp]

  - id: excel-processing
    providers:
      libraries: [openpyxl, pandas]
      agents: [data-processing-agent]

  - id: email-send
    providers:
      mcp_servers: [gmail-mcp]
```

Capability Registry는 다음 정보를 관리한다.

* Capability 이름 / 제공 Agent / 제공 MCP / 필요 권한 / 위험도 / 비용
* 지원 프로젝트 / 상태 / 버전 / 테스트 결과 / 성공률 / 최근 사용 일시

---

