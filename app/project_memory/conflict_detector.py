"""요구사항 ↔ 기존 결정 충돌 탐지 (spec 06 §20.1).

Mock 수준의 결정론적 탐지: 새 요구사항과 활성 결정이 유의미한 토큰을
2개 이상 공유하면 "잠재 충돌"로 표시해 사용자 확인을 요청한다.
(정밀한 의미 비교는 LLM Agent 연동 이후 고도화한다. 과탐지는 허용,
미탐지로 기존 결정이 조용히 뒤집히는 것을 막는 것이 목적이다.)
"""

import re
from dataclasses import dataclass

from app.db.models.project_decision import ProjectDecision
from app.product.schemas import RequirementDraft

_STOPWORDS = {
    "있다",
    "한다",
    "않는다",
    "된다",
    "수",
    "것",
    "및",
    "또는",
    "등",
    "위해",
    "대한",
    "사용자",
    "사용",
    "기능",
    "요구사항",
    "시스템",
}

_MIN_SHARED_TOKENS = 2


@dataclass(frozen=True)
class DecisionConflict:
    requirement_key: str
    decision_key: str
    decision_title: str
    message: str  # 사용자 언어 설명


def find_conflicts(
    drafts: list[RequirementDraft], active_decisions: list[ProjectDecision]
) -> list[DecisionConflict]:
    conflicts: list[DecisionConflict] = []
    for decision in active_decisions:
        decision_tokens = _significant_tokens(f"{decision.title} {decision.decision}")
        for draft in drafts:
            shared = decision_tokens & _significant_tokens(draft.description)
            # 결정 내용이 요구사항에 그대로 반영된 경우(합의 상태)는 충돌이 아니다.
            agrees = (
                decision.decision in draft.description
                or draft.description in decision.decision
            )
            if len(shared) >= _MIN_SHARED_TOKENS and not agrees:
                conflicts.append(
                    DecisionConflict(
                        requirement_key=draft.key,
                        decision_key=decision.decision_key,
                        decision_title=decision.title,
                        message=(
                            f"이번 요청({draft.key})이 기존 결정 "
                            f"[{decision.decision_key}] '{decision.title}'와 겹칩니다. "
                            f"기존 결정: {decision.decision} "
                            "기존 정책을 유지할까요, 변경할까요?"
                        ),
                    )
                )
    return conflicts


def _significant_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣a-zA-Z0-9]{2,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}
