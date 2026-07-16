# 08. 작업 공간 — 부트스트랩, 산출물 전달, Ticket, Worktree, Rules, Quality Gate

## 5. 신규 프로젝트 Repository 부트스트랩

대상 프로젝트는 **기존 Repository가 없는 신규 생성인 경우가 대부분**이다.
다음 부트스트랩 흐름을 필수로 구현한다.

```text
산출물 형태 결정 (섹션 6)
→ 프로젝트 언어/프레임워크 결정 (Supervisor Agent)
→ GitHub Repository 생성 (GitHub App, private 기본)
→ 초기 스캐폴딩 생성
   (디렉터리 구조, 패키지 설정, 린트/타입체크/테스트 설정, .gitignore)
→ commands.yaml 자동 생성
→ CI 설정 파일 자동 생성 (GitHub Actions: lint + test + build)
→ 프로젝트 Rules 초기 생성
→ 초기 커밋 및 main 브랜치 설정
→ 브랜치 보호 규칙 설정 (main 직접 Push 차단)
→ 부트스트랩 검증 (clone → install → test 가 빈 프로젝트에서 통과)
→ READY_FOR_DEVELOPMENT
```

원칙:

* 부트스트랩 산출물 자체도 Quality Gate를 통과해야 한다. (빈 프로젝트에서 install, lint, test 성공)
* 스캐폴딩은 언어별 템플릿(`project_bootstrap/templates/`)으로 관리하고, Supervisor가 선택한다.
* 기존 Repository를 연결하는 경우에는 부트스트랩 대신 Repository 분석(구조, 명령어 추론, Rules 추출)을 수행한다. 두 흐름 모두 지원하되 MVP의 기본 시나리오는 신규 생성이다.
* CI 설정(GitHub Actions workflow 파일)은 부트스트랩 시점에 생성하며, `CI_RUNNING` 상태는 이 CI 결과를 확인하는 상태다.

---

## 6. 산출물 패키징 및 전달

개발 완료가 "PR Merge"로 끝나서는 안 된다.
비개발자가 실제로 받아서 사용할 수 있는 형태로 전달되어야 한다.

### 6.1 산출물 유형

Specification 단계에서 다음 중 하나로 산출물 유형을 확정하고, 요구사항 승인 카드에 포함한다.

```text
DESKTOP_APP      Windows 실행 파일 (예: PyInstaller 단일 exe)
                 → UI에서 zip 다운로드 + 실행 가이드 제공

SCRIPT_BUNDLE    실행 스크립트 묶음 (실행 환경이 있는 사용자용)
                 → zip 다운로드 + 단계별 실행 가이드 제공

WEB_SERVICE      웹 서비스 (Docker Compose 패키지)
                 → MVP에서는 로컬/사내 서버 실행 패키지로 전달
                 → 클라우드 자동 배포는 MVP 제외

AUTOMATION_JOB   주기 실행 자동화 (스케줄러 포함 Docker 패키지)
```

### 6.2 패키징 흐름

```text
Merge 완료
→ Release Build 실행 (commands.yaml의 package 명령)
→ 산출물 검증 (실행 스모크 테스트)
→ 산출물 저장 (버전 태그와 함께 artifacts 저장소에 보관)
→ UI 결과 확인 화면에 다운로드 링크 + 사용 가이드 게시
→ DELIVERED
```

* `commands.yaml`에 `package` 명령 그룹을 추가한다.
* 산출물은 `release_versions` 테이블과 연결해 버전별로 재다운로드할 수 있어야 한다.
* WEB_SERVICE 유형의 클라우드 배포 자동화는 MVP에서 제외하되, 전달 패키지에 실행 방법 문서를 반드시 포함한다.

---

## 24. Ticket Workflow

Ticket 시스템은 Provider 추상화로 구현한다.

```text
TicketProvider (Protocol)
├── InternalTicketProvider   MVP 기본값. 자체 DB 기반 Ticket 관리
└── JiraTicketProvider       Jira 연동 (설정으로 활성화)
```

* MVP의 기본 Provider는 **InternalTicketProvider**다. 비개발자 단독 사용 환경에서는 Jira 계정과 프로젝트 설정 자체가 진입 장벽이 되기 때문이다.
* Jira 연동은 동일 인터페이스의 Adapter로 구현하며, 활성화 시 다음을 지원한다.

Jira Ticket 생성 방식:

```text
1. 기존 Jira Ticket에 ai-ready Label 추가
2. Specification Agent가 승인된 요구사항으로 Jira Ticket 자동 생성
```

자동 실행 Label: `ai-ready` / 작업 중단 Label: `ai-stop`

권장 Ticket 필드:

* Summary / Description / Acceptance Criteria / Target Repository / Priority
* Related Documents / Out of Scope / Risk Level / AI Execution Status
* Source Requirement / User Approval ID / Required Capabilities
* Required Agents / Required MCP Servers / Deliverable Type

정보가 부족하면 `WAITING_INFORMATION`으로 전환한다.
Ticket Key는 Development Task ID로 사용한다.

---

## 25. Git Worktree 병렬 처리

각 Task에 독립된 Branch와 Worktree를 할당한다.

```text
Task: DEV-142
Branch: agent/DEV-142-session-timeout
Worktree: {WORKTREE_ROOT}/DEV-142
```

* `WORKTREE_ROOT`는 환경변수로 설정한다. (기본값: Linux `/var/lib/ai-orchestrator/worktrees`, 로컬 개발 시 프로젝트 하위 `./.worktrees`)

생성 명령:

```bash
git fetch origin
git worktree add \
  {WORKTREE_ROOT}/DEV-142 \
  -b agent/DEV-142-session-timeout \
  origin/main
```

구현할 Lock:

* Ticket Lock / Repository Lock / File Intent Lock / Workspace Lock
* PR Lock / Agent Expansion Lock / MCP Registration Lock

초기 MVP에서는 PostgreSQL Advisory Lock을 우선 사용한다.

---

## 28. Rules 체계

Rules 우선순위:

```text
Organization Rules → Project Rules → Domain Rules
→ Directory Rules → Agent Rules → Task Constraints
```

가능한 Rule은 Prompt뿐 아니라 코드로 검증한다.

검증 예:

* 금지 경로 변경 여부 / 테스트 파일 존재 여부 / Migration 변경 여부
* Diff 크기 제한 / Dependency 추가 여부 / Secret 파일 접근 여부
* MCP 권한 초과 여부 / Agent Scope 초과 여부 / 신규 외부 연결 여부 / 사용자 승인 여부

---

## 29. Quality Gate

다음 순서로 실행한다.

```text
Changed Scope Validation
→ Agent Permission Validation
→ MCP Permission Validation
→ Forbidden Path Validation
→ Format → Lint → Type Check
→ Related Unit Test → Full Unit Test
→ Build
→ Security Scan
→ AI Self Review
→ Codex Reviewer
```

필수 Gate 중 하나라도 실패하면 PR을 생성하지 않는다.

---

## 32. 프로젝트별 언어 및 명령어

Orchestrator는 Python으로 구현한다.
대상 프로젝트의 명령어는 `commands.yaml`로 관리한다.
신규 프로젝트의 `commands.yaml`은 부트스트랩 단계에서 자동 생성한다.

Python 예:

```yaml
runtime:
  language: python
  package_manager: uv

commands:
  install: [uv sync]
  format: [ruff format --check .]
  lint: [ruff check .]
  typecheck: [mypy src]
  unit_test: [pytest]
  build: [python -m build]
  package: [pyinstaller --onefile src/main.py]
```

TypeScript 예:

```yaml
runtime:
  language: typescript
  package_manager: npm

commands:
  install: [npm ci]
  format: [npm run format:check]
  lint: [npm run lint]
  typecheck: [npm run typecheck]
  unit_test: [npm test]
  build: [npm run build]
  package: [npm run package]
```

Shell 문자열을 그대로 실행하지 말고 명령어와 인자를 분리해 검증한다.

---

