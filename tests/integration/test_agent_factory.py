"""Agent Factory 테스트 — 정의 검증 + Policy 판정 + 등록 (Phase 6, spec 04 §16)."""

import uuid

from app.agents.factory import AgentFactory
from app.agents.schemas import (
    AgentDefinition,
    AgentModelRef,
    AgentPermissions,
    AgentScope,
    AgentTokenBudget,
)
from app.core.enums import AgentStatus, PolicyDecision
from app.core.security import hash_password
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import SessionFactory


def _defn(**overrides: object) -> AgentDefinition:
    base = dict(
        id="excel-report-agent",
        name="Excel Report Agent",
        version="1.0.0",
        purpose="엑셀 데이터를 분석해 보고서 구조화 데이터를 만든다.",
        model=AgentModelRef(provider="mock", adapter="MockAdapter"),
        scope=AgentScope(project_id="report-automation", allowed_paths=["src/reporting/**"]),
        capabilities=["inspect_excel_schema"],
        permissions=AgentPermissions(filesystem="read_only", network="denied", shell="denied"),
        quality_gates=["unit_test"],
        token_budget=AgentTokenBudget(max_input_tokens=30000, max_output_tokens=10000),
    )
    base.update(overrides)
    return AgentDefinition(**base)  # type: ignore[arg-type]


async def _make_project(session) -> Project:
    user = User(
        email=f"af-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("pw-123456"),
        display_name="AF",
    )
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="AF", idea_text="엑셀", status="READY_FOR_DEVELOPMENT")
    session.add(project)
    await session.flush()
    return project


async def test_valid_project_scoped_agent_auto_approved_and_registered(
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        project = await _make_project(session)
        factory = AgentFactory(session)
        assessment = factory.assess(_defn())
        assert assessment.valid
        assert assessment.judgment is not None
        assert assessment.judgment.decision == PolicyDecision.AUTO_APPROVE

        record = await factory.register(_defn(), project_id=project.id)
        assert record.status == AgentStatus.ACTIVE
        assert record.agent_id == "excel-report-agent"
        await session.commit()


async def test_admin_privilege_is_rejected(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        defn = _defn(permissions=AgentPermissions(admin=True))
        assessment = factory.assess(defn)
        assert not assessment.valid
        assert any(i.code == "perm.admin" for i in assessment.validation.issues)
        assert assessment.judgment is None  # 검증 실패 → 판정 이전에 중단


async def test_secret_access_definition_is_rejected(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        defn = _defn(permissions=AgentPermissions(accesses_secret=True))
        assessment = factory.assess(defn)
        assert not assessment.valid
        assert any(i.code == "perm.secret" for i in assessment.validation.issues)


async def test_unknown_mcp_dependency_is_rejected(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        defn = _defn(mcp_dependencies=["ghost-mcp"])
        assessment = factory.assess(defn, known_mcp_ids=["jira-mcp"])
        assert not assessment.valid
        assert any(i.code == "mcp.unknown" for i in assessment.validation.issues)


async def test_over_budget_is_rejected(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        defn = _defn(token_budget=AgentTokenBudget(max_input_tokens=999_999, max_output_tokens=10))
        assessment = factory.assess(defn)
        assert not assessment.valid
        assert any(i.code == "budget.input" for i in assessment.validation.issues)


async def test_network_agent_needs_expert(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        # 네트워크 접근 = 권한 확장 → 전문가 확인 필요
        defn = _defn(
            permissions=AgentPermissions(filesystem="read_only", network="allowlisted"),
        )
        assessment = factory.assess(defn)
        assert assessment.valid
        assert assessment.judgment is not None
        assert assessment.judgment.decision == PolicyDecision.EXPERT_REQUIRED


async def test_unknown_model_provider_is_rejected(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        factory = AgentFactory(session)
        defn = _defn(model=AgentModelRef(provider="gpt-magic", adapter="X"))
        assessment = factory.assess(defn)
        assert not assessment.valid
        assert any(i.code == "model.provider" for i in assessment.validation.issues)
