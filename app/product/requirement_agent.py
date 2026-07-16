"""Requirement Agent — 구조화 요구사항 변환 (spec 03 §9).

Core Agent 결과와 사용자 답변을 받아 요구사항 집합을 완성한다.
Phase 2는 결정론적 Mock 구현. 기술 구현 방법이 아니라 제품 동작을 정의한다.
"""

from typing import Protocol

from app.core.enums import RequirementCategory, RequirementStatus
from app.product.schemas import CoreAnalysis, QuestionDraft, RequirementDraft, RequirementSet

# 비개발자 프로젝트에 공통 적용되는 표준 보강 요구사항
_STANDARD_SUPPLEMENTS: tuple[tuple[str, str, RequirementCategory], ...] = (
    (
        "NFR-001",
        "비개발자가 별도 설치 지식 없이 실행하거나 접속할 수 있어야 한다",
        RequirementCategory.NON_FUNCTIONAL,
    ),
    (
        "NFR-002",
        "오류가 발생하면 기술 용어 대신 사용자 언어로 안내한다",
        RequirementCategory.NON_FUNCTIONAL,
    ),
    (
        "BR-001",
        "기존 결과물을 덮어쓰지 않고 새 이름으로 저장한다",
        RequirementCategory.BUSINESS_RULE,
    ),
    (
        "EX-001",
        "입력 자료가 형식에 맞지 않으면 어떤 부분이 문제인지 알려준다",
        RequirementCategory.EXCEPTION_CASE,
    ),
)


class RequirementAgent(Protocol):
    async def refine(
        self, analysis: CoreAnalysis, answers: dict[str, str]
    ) -> RequirementSet: ...


class MockRequirementAgent:
    """answers: 질문 key(Q-xxx) → 사용자 답변. 답변된 UNKNOWN은 CONFIRMED로 승격된다."""

    async def refine(self, analysis: CoreAnalysis, answers: dict[str, str]) -> RequirementSet:
        answered_req_keys = {
            q.related_requirement_key: answers[q.key]
            for q in analysis.open_questions
            if q.key in answers and q.related_requirement_key
        }

        requirements: list[RequirementDraft] = []
        for req in analysis.functional_requirements:
            if req.key in answered_req_keys:
                requirements.append(
                    req.model_copy(
                        update={
                            "status": RequirementStatus.CONFIRMED,
                            "description": (
                                f"{req.description} — 사용자 답변: {answered_req_keys[req.key]}"
                            ),
                        }
                    )
                )
            else:
                requirements.append(req)

        existing_keys = {r.key for r in requirements}
        for key, description, category in _STANDARD_SUPPLEMENTS:
            if key not in existing_keys:
                requirements.append(
                    RequirementDraft(
                        key=key,
                        description=description,
                        status=RequirementStatus.INFERRED,
                        category=category,
                        priority="MEDIUM",
                    )
                )

        open_questions: list[QuestionDraft] = [
            q for q in analysis.open_questions if q.key not in answers
        ]
        return RequirementSet(requirements=requirements, open_questions=open_questions)
