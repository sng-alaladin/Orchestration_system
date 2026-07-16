"""Product Definition End-to-End (Mock) — 세션 2 종료 조건 검증.

기획안 입력 → 분석 → 분류 게이트 → 질문 답변 → 요구사항 승인 → PRD/Backlog 생성.
"""

import io

from httpx import AsyncClient

from app.core.enums import ProductState
from tests.conftest import TEST_USER_PASSWORD

IDEA = (
    "엑셀 파일을 업로드하면 월간 보고서를 자동으로 생성하는 프로그램이 필요하다. "
    "생성된 보고서는 폴더에 저장한다."
)


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200


async def _create_project(client: AsyncClient, idea: str = IDEA) -> str:
    response = await client.post(
        "/api/projects", json={"name": "보고서 자동화", "idea_text": idea}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == ProductState.IDEA_RECEIVED
    return str(body["id"])


async def _answer_all_open_questions(client: AsyncClient, project_id: str) -> None:
    questions = (await client.get(f"/api/projects/{project_id}/questions")).json()
    for question in questions:
        if question["status"] == "OPEN":
            response = await client.post(
                f"/api/projects/{project_id}/questions/{question['question_key']}/answer",
                json={"answer": "혼자 사용하고, 1년간 보관하면 됩니다"},
            )
            assert response.status_code == 200


async def test_full_flow_idea_to_prd(client: AsyncClient, seeded_user: str) -> None:
    await _login(client, seeded_user)
    project_id = await _create_project(client)

    # 1) 분석 실행 → 질문 대기
    analyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    assert analyzed["status"] == ProductState.WAITING_REQUIREMENT_INPUT

    detail = (await client.get(f"/api/projects/{project_id}")).json()
    assert detail["classification"]["automation_class"] == "SELF_SERVICE"

    questions = (await client.get(f"/api/projects/{project_id}/questions")).json()
    open_questions = [q for q in questions if q["status"] == "OPEN"]
    assert len(open_questions) == 2

    # 2) 승인 단계 전에는 PRD가 존재하지 않는다 (승인 없이 진행 금지)
    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    assert all(d["kind"] != "GENERATED" for d in documents)

    # 승인 시도 → 아직 승인 단계가 아니므로 409
    premature = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert premature.status_code == 409

    # 3) 질문에 모두 답하면 승인 대기
    await _answer_all_open_questions(client, project_id)
    detail = (await client.get(f"/api/projects/{project_id}")).json()
    assert detail["status"] == ProductState.WAITING_REQUIREMENT_APPROVAL

    requirements = (await client.get(f"/api/projects/{project_id}/requirements")).json()
    keys = {r["req_key"] for r in requirements}
    assert {"NFR-001", "BR-001", "EX-001"} <= keys
    assert all(r["status"] != "UNKNOWN" for r in requirements), "답변 후 UNKNOWN이 남지 않는다"

    # 4) 요구사항 승인 → PRD + Backlog 생성, 개발 준비 완료
    approved = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REQUIREMENTS", "decision": "APPROVED"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == ProductState.READY_FOR_DEVELOPMENT

    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    generated = {d["doc_type"]: d for d in documents if d["kind"] == "GENERATED"}
    assert set(generated) == {"PRD", "BACKLOG"}

    prd = await client.get(
        f"/api/projects/{project_id}/documents/{generated['PRD']['id']}"
    )
    assert prd.status_code == 200
    assert "# PRD — 보고서 자동화" in prd.text
    assert "완료 조건" in prd.text
    assert "반영된 의사결정" in prd.text  # 질문 답변이 Decision Log를 거쳐 PRD에 반영

    approvals = (await client.get(f"/api/projects/{project_id}/approvals")).json()
    assert [a["decision"] for a in approvals] == ["APPROVED"]


async def test_rejection_returns_to_approval_after_redraft(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id = await _create_project(client)
    await client.post(f"/api/projects/{project_id}/analyze")
    await _answer_all_open_questions(client, project_id)

    rejected = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={
            "approval_type": "REQUIREMENTS",
            "decision": "CHANGES_REQUESTED",
            "comment": "보고서에 회사 로고도 넣어 주세요",
        },
    )
    assert rejected.status_code == 200
    # 재초안 후 다시 승인 대기 (답변은 유지되므로 질문 단계로 돌아가지 않는다)
    assert rejected.json()["status"] == ProductState.WAITING_REQUIREMENT_APPROVAL

    documents = (await client.get(f"/api/projects/{project_id}/documents")).json()
    assert all(d["kind"] != "GENERATED" for d in documents), "거절 시 PRD가 생성되지 않는다"


async def test_payment_idea_is_auto_blocked_with_alternative(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id = await _create_project(
        client, idea="고객이 카드결제로 주문할 수 있는 쇼핑몰을 만들어줘"
    )
    analyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    assert analyzed["status"] == ProductState.AUTO_BLOCKED_BY_POLICY
    assert "대안" in analyzed["status_reason"]

    # 요구사항·PRD가 만들어지지 않는다
    requirements = (await client.get(f"/api/projects/{project_id}/requirements")).json()
    assert requirements == []

    # 기획 수정(결제 제거) 후 재분석하면 진행된다 (ALTERNATIVE_ACCEPTED 경로)
    await client.patch(
        f"/api/projects/{project_id}", json={"idea_text": "주문 내역을 정리하는 프로그램"}
    )
    reanalyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    assert reanalyzed["status"] == ProductState.WAITING_REQUIREMENT_INPUT


async def test_risky_idea_requires_reduced_scope_approval(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id = await _create_project(
        client, idea="경쟁사 사이트를 크롤링해서 가격 보고서를 만들어주는 서비스"
    )
    analyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    assert analyzed["status"] == ProductState.WAITING_APPROVAL

    approved = await client.post(
        f"/api/projects/{project_id}/approvals",
        json={"approval_type": "REDUCED_SCOPE", "decision": "APPROVED"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == ProductState.WAITING_REQUIREMENT_INPUT


async def test_uploaded_document_is_used_in_analysis(
    client: AsyncClient, seeded_user: str
) -> None:
    await _login(client, seeded_user)
    project_id = await _create_project(client, idea="업무 자동화 도구가 필요하다")

    upload = await client.post(
        f"/api/projects/{project_id}/documents",
        files={
            "file": (
                "기획서.txt",
                io.BytesIO("고객이 카드결제로 구매하는 기능도 필요하다".encode()),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201

    # 업로드 문서의 결제 언급이 분석에 반영되어 차단된다 → 문서가 입력에 포함됨을 증명
    analyzed = (await client.post(f"/api/projects/{project_id}/analyze")).json()
    assert analyzed["status"] == ProductState.AUTO_BLOCKED_BY_POLICY


async def test_project_access_requires_login_and_ownership(
    client: AsyncClient, seeded_user: str, session_factory: object
) -> None:
    # 미로그인 → 401
    response = await client.get("/api/projects")
    assert response.status_code == 401

    await _login(client, seeded_user)
    project_id = await _create_project(client)

    # 다른 사용자 생성 후 그 계정으로 접근 → 404 (존재 여부 비노출)
    from app.core.security import hash_password
    from app.db.models.user import User

    factory = session_factory
    async with factory() as session:  # type: ignore[operator]
        other = User(
            email="other@example.com",
            password_hash=hash_password(TEST_USER_PASSWORD),
            display_name="다른 사용자",
        )
        session.add(other)
        await session.commit()

    await client.post("/api/auth/logout")
    await _login(client, "other@example.com")
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404
