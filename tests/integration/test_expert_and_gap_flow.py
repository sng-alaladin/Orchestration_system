"""세션 3 추가 지시 검증 — 전문가 확인 스텁 + Capability Gap 흐름 (API 레벨).

WAITING_EXPERT_CONFIRMATION과 EXPANSION_PROPOSING은 상담 패키지/확장 Proposal
서비스(세션 4) 전까지 조용히 멈추지 않고 명시적 미구현 안내를 반환해야 한다.
"""

from httpx import AsyncClient

from app.core.enums import ProductState
from tests.conftest import TEST_USER_PASSWORD


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200


async def _create_and_analyze(client: AsyncClient, idea: str) -> tuple[str, dict]:
    created = await client.post("/api/projects", json={"name": "검증", "idea_text": idea})
    project_id = str(created.json()["id"])
    analyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    return project_id, analyzed


async def test_expert_confirmation_returns_explicit_not_implemented(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id, analyzed = await _create_and_analyze(
        client, "사내 인증 연동이 필요한 직원용 업무 포털을 만들어줘"
    )
    # 1) 상태는 전문가 확인 대기
    assert analyzed["status"] == ProductState.WAITING_EXPERT_CONFIRMATION
    # 2) 조용히 멈추지 않는다 — 사유 + 미구현 안내 + 사용자가 할 수 있는 일이 표시된다
    reason = analyzed["status_reason"]
    assert "개발자 확인이 필요" in reason
    assert "아직 준비 중" in reason
    assert "세션 4" in reason

    # 3) 상담 패키지 생성 요청은 명시적 501 (Not Implemented)
    consultation = await client.post(f"/api/projects/{project_id}/consultation")
    assert consultation.status_code == 501
    assert "아직 준비 중" in consultation.json()["detail"]

    # 4) 이 상태에서 요구사항 승인 등 다른 단계 진행은 409로 거부
    approval = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert approval.status_code == 409


async def test_capability_gap_leads_to_expansion_proposing_with_explicit_notice(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id, analyzed = await _create_and_analyze(
        client, "매주 판매 데이터를 정리한 보고서를 만들어 이메일로 공유하는 웹 서비스"
    )
    assert analyzed["status"] == ProductState.WAITING_REQUIREMENT_INPUT

    questions = (await client.get(f"/api/projects/{project_id}/questions")).json()
    for question in questions:
        if question["status"] == "OPEN":
            await client.post(
                f"/api/projects/{project_id}/questions/{question['question_key']}/answer",
                json={"answer": "팀에서 함께 사용하고 1년 보관합니다"},
            )

    approved = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert approved.status_code == 200
    body = approved.json()
    # email-send 역량은 Registry에 없음 → GAP_FOUND → EXPANSION_PROPOSING (명시적 안내)
    assert body["status"] == ProductState.EXPANSION_PROPOSING
    assert "email-send" in body["status_reason"]
    assert "아직 준비 중" in body["status_reason"]

    # PRD는 생성되었지만(SPEC_COMPLETED 통과) Backlog는 만들어지지 않았다
    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    generated = {d["doc_type"] for d in documents if d["kind"] == "GENERATED"}
    assert generated == {"PRD"}
