"""전문가 확인 게이트 + Capability Gap → 상담 패키지 흐름 (API 레벨, Phase 7).

세션 3의 501/미구현 스텁이 세션 4에서 실제 상담 서비스로 대체되었다:
- 적합도 게이트 전문가 확인 → 상담 패키지 생성 → 답변(UNBLOCK) → 진행 재개
- Capability Gap(email-send=gmail-mcp, allowlist 밖) → 전문가 확인 필요 → 상담 패키지
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


async def _answer_all_open_questions(client: AsyncClient, project_id: str) -> None:
    questions = (await client.get(f"/api/projects/{project_id}/questions")).json()
    for question in questions:
        if question["status"] == "OPEN":
            await client.post(
                f"/api/projects/{project_id}/questions/{question['question_key']}/answer",
                json={"answer": "팀에서 함께 사용하고 1년 보관합니다"},
            )


async def test_expert_gate_creates_consultation_and_unblocks(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id, analyzed = await _create_and_analyze(
        client, "사내 인증 연동이 필요한 직원용 업무 포털을 만들어줘"
    )
    # 1) 전문가 확인 대기 + 조용히 멈추지 않는 명시적 안내
    assert analyzed["status"] == ProductState.WAITING_EXPERT_CONFIRMATION
    assert "개발자 확인이 필요" in analyzed["status_reason"]
    assert "상담 자료" in analyzed["status_reason"]

    # 2) 상담 패키지가 실제로 생성되어 조회된다 (2계층 구조)
    consultation = await client.get(f"/api/projects/{project_id}/consultation")
    assert consultation.status_code == 200
    body = consultation.json()
    assert "비개발자용 요약" in body["markdown"]
    assert "개발자용 기술 상세" in body["markdown"]
    assert body["status"] == "PENDING"
    assert any(q["key"] == "GATE-EXPERT" for q in body["questions"])

    # 3) 개발자 답변(UNBLOCK) 입력 → 게이트 해제 후 진행 재개
    answered = await client.post(
        f"/api/projects/{project_id}/consultation/answers",
        json={
            "question_key": "GATE-EXPERT",
            "answer": "확인했고 사내 인증은 표준 방식으로 진행 가능합니다.",
            "resolution": "UNBLOCK",
        },
    )
    assert answered.status_code == 200
    # 게이트가 풀려 요구사항 단계로 진행 (표준 미확정 질문 존재 → 입력 대기)
    assert answered.json()["status"] == ProductState.WAITING_REQUIREMENT_INPUT

    # 4) 상담은 반영 완료로 기록된다
    after = (await client.get(f"/api/projects/{project_id}/consultation")).json()
    assert after["status"] == "APPLIED"
    assert after["answers"][0]["question_key"] == "GATE-EXPERT"


async def test_capability_gap_routes_to_expert_consultation(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id, analyzed = await _create_and_analyze(
        client, "매주 판매 데이터를 정리한 보고서를 만들어 이메일로 공유하는 웹 서비스"
    )
    assert analyzed["status"] == ProductState.WAITING_REQUIREMENT_INPUT

    await _answer_all_open_questions(client, project_id)
    approved = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert approved.status_code == 200
    body = approved.json()

    # email-send=gmail-mcp(허용 목록 밖) → 전문가 확인 필요 → 상담 패키지 + 대기
    assert body["status"] == ProductState.WAITING_EXPERT_CONFIRMATION
    assert "email-send" in body["status_reason"]
    assert "개발자 확인이 필요" in body["status_reason"]

    # 상담 패키지가 생성되었고, 확장 질문에 gmail-mcp가 포함된다
    consultation = (await client.get(f"/api/projects/{project_id}/consultation")).json()
    assert consultation["status"] == "PENDING"
    assert any("gmail-mcp" in q["question"] for q in consultation["questions"])

    # PRD는 생성되었지만(SPEC_COMPLETED 통과) Backlog는 아직 만들어지지 않았다
    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    generated = {d["doc_type"] for d in documents if d["kind"] == "GENERATED"}
    assert generated == {"PRD"}
