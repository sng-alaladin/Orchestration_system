"""Mock Agent 단위 테스트 — 결정론적 출력과 Schema 준수."""

from app.core.enums import DeliverableType, RequirementStatus
from app.product.core_agent import MockCoreAgent
from app.product.question_generator import build_question_cards
from app.product.requirement_agent import MockRequirementAgent
from app.product.schemas import ProjectInput
from app.product.specification_agent import MockSpecificationAgent

IDEA = (
    "엑셀 파일을 업로드하면 월간 보고서를 자동으로 생성하는 프로그램이 필요하다. "
    "생성된 보고서는 폴더에 저장한다."
)


def _input() -> ProjectInput:
    return ProjectInput(project_name="보고서 자동화", idea_text=IDEA)


async def test_core_agent_extracts_requirements_and_questions() -> None:
    analysis = await MockCoreAgent().analyze(_input())
    confirmed = [
        r for r in analysis.functional_requirements if r.status == RequirementStatus.CONFIRMED
    ]
    unknown = [
        r for r in analysis.functional_requirements if r.status == RequirementStatus.UNKNOWN
    ]
    assert confirmed, "기획안에서 CONFIRMED 요구사항을 추출해야 한다"
    assert len(unknown) == 2, "표준 미확정 항목 2건이 UNKNOWN으로 생성된다"
    assert len(analysis.open_questions) == 2
    assert all(q.related_requirement_key for q in analysis.open_questions)
    assert analysis.deliverable_type == DeliverableType.DESKTOP_APP
    assert "excel-read" in analysis.required_capabilities


async def test_core_agent_is_deterministic() -> None:
    first = await MockCoreAgent().analyze(_input())
    second = await MockCoreAgent().analyze(_input())
    assert first == second


async def test_requirement_agent_promotes_answered_unknowns() -> None:
    analysis = await MockCoreAgent().analyze(_input())
    question = analysis.open_questions[0]
    refined = await MockRequirementAgent().refine(analysis, {question.key: "혼자 사용합니다"})

    promoted = next(
        r for r in refined.requirements if r.key == question.related_requirement_key
    )
    assert promoted.status == RequirementStatus.CONFIRMED
    assert "혼자 사용합니다" in promoted.description
    assert all(q.key != question.key for q in refined.open_questions)
    # 표준 보강 요구사항 추가 확인
    keys = {r.key for r in refined.requirements}
    assert {"NFR-001", "NFR-002", "BR-001", "EX-001"} <= keys


async def test_question_cards_deduplicated() -> None:
    analysis = await MockCoreAgent().analyze(_input())
    refined = await MockRequirementAgent().refine(analysis, {})
    cards = build_question_cards(refined)
    assert len(cards) == len({c.key for c in cards})


async def test_specification_agent_builds_prd_from_confirmed() -> None:
    analysis = await MockCoreAgent().analyze(_input())
    refined = await MockRequirementAgent().refine(
        analysis, {q.key: "답변" for q in analysis.open_questions}
    )
    spec = await MockSpecificationAgent().generate(
        project_name="보고서 자동화",
        project_goal=analysis.project_goal,
        deliverable_type=analysis.deliverable_type,
        requirements=refined.requirements,
        decisions=[("보관 기간", "1년")],
    )
    assert "# PRD — 보고서 자동화" in spec.prd_markdown
    assert spec.acceptance_criteria, "CONFIRMED 요구사항이 완료 조건이 된다"
    assert "보관 기간: 1년" in spec.prd_markdown  # 의사결정 반영
    assert spec.epics and spec.epics[0].stories
    assert "결제 기능" in spec.out_of_scope
