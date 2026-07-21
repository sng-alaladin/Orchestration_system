"""확장 Proposal → 판정 → 등록/차단/자문 흐름 (세션 4 종료 조건).

자동 승인 / 사용자 승인 / 전문가 확인 필요 / 자동 차단 네 경로를 모두 검증하고,
전문가 경로는 상담 패키지 생성 → 답변 반영 → 게이트 해제 → 등록·진행까지 확인한다.
"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.capabilities.gap_analyzer import GapAnalyzer
from app.capabilities.registry import CapabilityRegistry
from app.core.config import Settings
from app.core.enums import McpStatus, PolicyDecision, ProductState
from app.core.security import hash_password
from app.db.models.mcp_server import McpServer
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import SessionFactory
from app.expansion.service import build_expansion_service
from app.mcp.registry import McpRegistry
from app.orchestrator.product_state_machine import build_product_state_machine
from app.policy.engine import PRODUCT_EXPANSION_EVENT
from tests.conftest import TEST_USER_PASSWORD

CFG = Settings(env="test", database_url="sqlite+aiosqlite://")

# 카탈로그의 대표 역량 → 기대 판정 (자동/사용자/전문가/차단)
CAP_EXPECTED = [
    ("internal-doc-read", PolicyDecision.AUTO_APPROVE),
    ("ticket-management", PolicyDecision.USER_APPROVAL),
    ("email-send", PolicyDecision.EXPERT_REQUIRED),
    ("settlement-read", PolicyDecision.AUTO_BLOCKED),
]


async def _seed(session) -> None:
    await McpRegistry(session).sync_from_config(Path(CFG.mcp_servers_config))
    await CapabilityRegistry(session).sync_from_config(Path(CFG.capabilities_config))


async def _make_project(session, status: str = ProductState.EXPANSION_PROPOSING) -> Project:
    user = User(
        email=f"exp-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("pw-123456"),
        display_name="EXP",
    )
    session.add(user)
    await session.flush()
    project = Project(user_id=user.id, name="확장", idea_text="테스트", status=status)
    session.add(project)
    await session.flush()
    return project


@pytest.mark.parametrize("capability,expected", CAP_EXPECTED)
async def test_policy_routes_each_capability(
    capability: str, expected: PolicyDecision, session_factory: SessionFactory
) -> None:
    """카탈로그 역량별로 4단 판정이 결정론적으로 나온다."""
    async with session_factory() as session:
        await _seed(session)
        project = await _make_project(session)
        service = build_expansion_service(session, CFG)
        resolution = await service.plan_and_judge(project.id, [capability])
        assert resolution.decision == expected


@pytest.mark.parametrize("capability,expected", CAP_EXPECTED)
async def test_state_machine_routes_each_decision(
    capability: str, expected: PolicyDecision, session_factory: SessionFactory
) -> None:
    """판정 → 상태 머신 이벤트 → 목적지 상태가 4경로 모두 올바르다."""
    async with session_factory() as session:
        await _seed(session)
        project = await _make_project(session)
        service = build_expansion_service(session, CFG)
        resolution = await service.plan_and_judge(project.id, [capability])
        machine = build_product_state_machine(session)
        event = PRODUCT_EXPANSION_EVENT[resolution.decision]
        await machine.fire(
            project, event, context={"policy_decision": resolution.decision.value}
        )
        expected_state = {
            PolicyDecision.AUTO_APPROVE: ProductState.BACKLOG_GENERATING,
            PolicyDecision.USER_APPROVAL: ProductState.WAITING_EXPANSION_APPROVAL,
            PolicyDecision.EXPERT_REQUIRED: ProductState.WAITING_EXPERT_CONFIRMATION,
            PolicyDecision.AUTO_BLOCKED: ProductState.AUTO_BLOCKED_BY_POLICY,
        }[expected]
        assert project.status == expected_state


async def test_auto_approve_activation_closes_gap(session_factory: SessionFactory) -> None:
    """자동 승인 확장을 활성화하면 Capability Gap이 닫힌다 (등록)."""
    async with session_factory() as session:
        await _seed(session)
        project = await _make_project(session)
        service = build_expansion_service(session, CFG)

        before = await GapAnalyzer(session).analyze(["internal-doc-read"])
        assert before.has_gap

        resolution = await service.plan_and_judge(project.id, ["internal-doc-read"])
        assert resolution.decision == PolicyDecision.AUTO_APPROVE
        activated = await service.activate(resolution)
        assert "internal-doc-read" in activated

        after = await GapAnalyzer(session).analyze(["internal-doc-read"])
        assert not after.has_gap, "활성화 후 Gap이 닫혀야 한다"


async def test_auto_blocked_gives_alternatives(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        await _seed(session)
        project = await _make_project(session)
        service = build_expansion_service(session, CFG)
        resolution = await service.plan_and_judge(project.id, ["settlement-read"])
        assert resolution.decision == PolicyDecision.AUTO_BLOCKED
        assert resolution.alternatives, "차단은 대안을 제시해야 한다"


async def test_approve_pending_activates_user_expansion(
    session_factory: SessionFactory,
) -> None:
    """사용자 승인 대기(PENDING_USER) 확장을 승인하면 등록·활성화된다."""
    async with session_factory() as session:
        await _seed(session)
        project = await _make_project(session)
        service = build_expansion_service(session, CFG)
        resolution = await service.plan_and_judge(project.id, ["ticket-management"])
        assert resolution.decision == PolicyDecision.USER_APPROVAL

        activated = await service.approve_pending(project.id)
        assert "ticket-management" in activated
        jira = (
            await session.execute(select(McpServer).where(McpServer.server_id == "jira-mcp"))
        ).scalar_one()
        assert jira.status == McpStatus.APPROVED


# ── 전문가 경로 전 구간 (자문 → 답변 반영 → 등록·진행) — API 레벨 ────


async def _login(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": TEST_USER_PASSWORD}
    )
    assert r.status_code == 200


async def test_expert_consultation_answer_unblocks_and_completes(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    created = await client.post(
        "/api/projects",
        json={
            "name": "이메일 공유",
            "idea_text": "매주 판매 데이터를 정리한 보고서를 만들어 이메일로 공유하는 웹 서비스",
        },
    )
    project_id = str(created.json()["id"])
    await client.post(f"/api/projects/{project_id}/analyze")
    questions = (await client.get(f"/api/projects/{project_id}/questions")).json()
    for q in questions:
        if q["status"] == "OPEN":
            await client.post(
                f"/api/projects/{project_id}/questions/{q['question_key']}/answer",
                json={"answer": "팀이 함께 사용, 1년 보관"},
            )
    approved = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert approved.json()["status"] == ProductState.WAITING_EXPERT_CONFIRMATION

    # 상담 질문 키를 조회해 UNBLOCK 답변 반영
    consultation = (await client.get(f"/api/projects/{project_id}/consultation")).json()
    qkey = consultation["questions"][0]["key"]
    answered = await client.post(
        f"/api/projects/{project_id}/consultation/answers",
        json={
            "question_key": qkey,
            "answer": "Gmail 연동은 승인된 방식으로 진행 가능합니다.",
            "resolution": "UNBLOCK",
        },
    )
    assert answered.status_code == 200
    # 게이트 해제 → 확장 등록 → 개발 준비 완료
    assert answered.json()["status"] == ProductState.READY_FOR_DEVELOPMENT

    # Backlog도 생성되었다
    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    generated = {d["doc_type"] for d in documents if d["kind"] == "GENERATED"}
    assert {"PRD", "BACKLOG"} <= generated
