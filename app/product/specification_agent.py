"""Specification Agent — 승인된 요구사항을 개발 명세(PRD)로 변환 (spec 03 §10)."""

from typing import Protocol

from app.core.enums import DeliverableType, RequirementCategory, RequirementStatus
from app.product.schemas import (
    BacklogTask,
    Epic,
    RequirementDraft,
    SpecificationResult,
    UserStory,
)

_EPIC_TITLES: dict[RequirementCategory, str] = {
    RequirementCategory.FUNCTIONAL: "핵심 기능",
    RequirementCategory.NON_FUNCTIONAL: "품질과 사용성",
    RequirementCategory.BUSINESS_RULE: "업무 규칙",
    RequirementCategory.EXCEPTION_CASE: "예외 상황 처리",
}


class SpecificationAgent(Protocol):
    async def generate(
        self,
        *,
        project_name: str,
        project_goal: str,
        deliverable_type: DeliverableType,
        requirements: list[RequirementDraft],
        decisions: list[tuple[str, str]],
    ) -> SpecificationResult: ...


class MockSpecificationAgent:
    async def generate(
        self,
        *,
        project_name: str,
        project_goal: str,
        deliverable_type: DeliverableType,
        requirements: list[RequirementDraft],
        decisions: list[tuple[str, str]],
    ) -> SpecificationResult:
        confirmed = [r for r in requirements if r.status == RequirementStatus.CONFIRMED]
        acceptance_criteria = [r.description for r in confirmed]

        epics = _build_epics(requirements)
        out_of_scope = [
            "결제 기능",
            "법적 민감 개인정보 저장",
            "운영 데이터베이스 직접 연동",
        ]
        risks = ["초기 버전은 소규모 사용을 전제로 한다"]
        test_scenarios = [f"{r.key}: {r.description} — 동작을 확인한다" for r in confirmed]

        prd = _render_prd(
            project_name=project_name,
            project_goal=project_goal,
            deliverable_type=deliverable_type,
            requirements=requirements,
            acceptance_criteria=acceptance_criteria,
            decisions=decisions,
            out_of_scope=out_of_scope,
            risks=risks,
        )
        return SpecificationResult(
            prd_markdown=prd,
            deliverable_type=deliverable_type,
            acceptance_criteria=acceptance_criteria,
            epics=epics,
            out_of_scope=out_of_scope,
            risks=risks,
            test_scenarios=test_scenarios,
        )


def _build_epics(requirements: list[RequirementDraft]) -> list[Epic]:
    epics: list[Epic] = []
    epic_no = 0
    for category, title in _EPIC_TITLES.items():
        members = [r for r in requirements if r.category == category]
        if not members:
            continue
        epic_no += 1
        stories = [
            UserStory(
                key=f"US-{epic_no}{index:02d}",
                title=req.description[:100],
                tasks=[
                    BacklogTask(
                        key=f"DEV-{epic_no}{index:02d}",
                        title=f"{req.key} 구현",
                        description=f"{req.description} (요구사항 {req.key}, 상태 {req.status})",
                    )
                ],
            )
            for index, req in enumerate(members, start=1)
        ]
        epics.append(Epic(key=f"EP-{epic_no:03d}", title=title, stories=stories))
    return epics


def _render_prd(
    *,
    project_name: str,
    project_goal: str,
    deliverable_type: DeliverableType,
    requirements: list[RequirementDraft],
    acceptance_criteria: list[str],
    decisions: list[tuple[str, str]],
    out_of_scope: list[str],
    risks: list[str],
) -> str:
    lines: list[str] = [
        f"# PRD — {project_name}",
        "",
        "## 목표",
        project_goal,
        "",
        f"## 산출물 유형\n{deliverable_type}",
        "",
        "## 요구사항",
    ]
    for req in requirements:
        lines.append(f"- **{req.key}** [{req.status}] ({req.category}) {req.description}")
    lines += ["", "## 완료 조건 (Acceptance Criteria)"]
    lines += [f"- {ac}" for ac in acceptance_criteria]
    if decisions:
        lines += ["", "## 반영된 의사결정"]
        lines += [f"- {title}: {decision}" for title, decision in decisions]
    lines += ["", "## 제외 범위"]
    lines += [f"- {item}" for item in out_of_scope]
    lines += ["", "## 위험과 가정"]
    lines += [f"- {item}" for item in risks]
    return "\n".join(lines) + "\n"
