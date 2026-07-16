"""Core Agent — 기획안 분석 (spec 03 §8).

Phase 2에서는 결정론적 MockCoreAgent만 구현한다.
실제 LLM(CodexAdapter) 연동은 Phase 9(세션 5)에서 같은 Protocol 뒤에 추가된다.
설정 agent_mode="live"는 아직 명시적 오류를 낸다 (미구현 위장 금지 원칙).
"""

import re
from typing import Protocol

from app.core.enums import DeliverableType, RequirementCategory, RequirementStatus
from app.product.schemas import CoreAnalysis, ProjectInput, QuestionDraft, RequirementDraft

_ACTION_KEYWORDS = (
    "입력",
    "업로드",
    "생성",
    "만들",
    "저장",
    "다운로드",
    "분석",
    "보고서",
    "알림",
    "검색",
    "조회",
    "정리",
    "변환",
    "수집",
)

_CAPABILITY_MAP: dict[str, tuple[str, ...]] = {
    "excel-read": ("엑셀", "xlsx", "xls", "스프레드시트"),
    "document-generate": ("보고서", "word", "문서 생성", "pdf"),
    "web-ui": ("웹", "사이트", "화면", "웹서비스"),
    "email-send": ("이메일", "메일 발송"),
    "data-analyze": ("분석", "통계", "집계"),
    "file-storage": ("저장", "보관", "업로드"),
}

# 항상 확인이 필요한 표준 미확정 항목 (비개발자 언어 질문)
_STANDARD_UNKNOWNS: tuple[tuple[str, str, str], ...] = (
    (
        "동시에 사용하는 인원 규모",
        "이 결과물을 혼자 사용하나요, 아니면 여러 사람이 함께 사용하나요?",
        "여러 사람이 함께 사용하면 저장 방식과 화면 구성이 달라집니다.",
    ),
    (
        "결과물 보관 기간",
        "만들어진 결과물을 언제까지 보관해야 하나요? (예: 1개월, 1년, 계속)",
        "보관 기간에 따라 저장 공간과 정리 방식이 달라집니다.",
    ),
)


class CoreAgent(Protocol):
    async def analyze(self, project_input: ProjectInput) -> CoreAnalysis: ...


class MockCoreAgent:
    """키워드 기반 결정론적 분석. 동일 입력 → 동일 출력."""

    async def analyze(self, project_input: ProjectInput) -> CoreAnalysis:
        text = project_input.combined_text
        sentences = _split_sentences(text)
        goal = sentences[0][:200] if sentences else project_input.project_name

        requirements: list[RequirementDraft] = []
        seen: set[str] = set()
        for sentence in sentences:
            if len(requirements) >= 20:
                break
            if any(kw in sentence for kw in _ACTION_KEYWORDS) and sentence not in seen:
                seen.add(sentence)
                requirements.append(
                    RequirementDraft(
                        key=f"FR-{len(requirements) + 1:03d}",
                        description=sentence,
                        status=RequirementStatus.CONFIRMED,
                        category=RequirementCategory.FUNCTIONAL,
                        priority="HIGH",
                    )
                )
        if not requirements:
            requirements.append(
                RequirementDraft(
                    key="FR-001",
                    description=goal,
                    status=RequirementStatus.CONFIRMED,
                    category=RequirementCategory.FUNCTIONAL,
                    priority="HIGH",
                )
            )

        questions: list[QuestionDraft] = []
        next_fr = len(requirements) + 1
        for index, (topic, question, reason) in enumerate(_STANDARD_UNKNOWNS, start=1):
            req_key = f"FR-{next_fr:03d}"
            next_fr += 1
            requirements.append(
                RequirementDraft(
                    key=req_key,
                    description=topic,
                    status=RequirementStatus.UNKNOWN,
                    category=RequirementCategory.FUNCTIONAL,
                )
            )
            questions.append(
                QuestionDraft(
                    key=f"Q-{index:03d}",
                    question=question,
                    reason=reason,
                    related_requirement_key=req_key,
                )
            )

        capabilities = sorted(
            cap
            for cap, keywords in _CAPABILITY_MAP.items()
            if any(kw in text.lower() for kw in keywords)
        )

        return CoreAnalysis(
            project_goal=goal,
            target_users=["비개발자 실무 사용자"],
            deliverable_type=_deliverable_type(text),
            functional_requirements=requirements,
            open_questions=questions,
            required_capabilities=capabilities or ["general-automation"],
            expansion_required=False,
        )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=다)\.|[.!?\n]", text)
    return [p.strip().rstrip(".") for p in parts if p and len(p.strip()) >= 5]


def _deliverable_type(text: str) -> DeliverableType:
    lowered = text.lower()
    if any(kw in lowered for kw in ("웹", "사이트", "웹서비스", "브라우저")):
        return DeliverableType.WEB_APP
    if any(kw in lowered for kw in ("스크립트", "자동화 작업", "배치")):
        return DeliverableType.AUTOMATION_SCRIPT
    if any(kw in lowered for kw in ("프로그램", "엑셀", "데스크톱", "설치")):
        return DeliverableType.DESKTOP_APP
    return DeliverableType.WEB_APP
