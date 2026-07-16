"""프로젝트 적합도 분류 게이트 (spec 01 §37).

판정은 LLM이 아니라 결정론적 코드로 수행한다.
키워드 정책은 configs/auto-block-policy.yaml에서 로드한다.
MVP 자동 차단 항목(결제/민감 개인정보/운영 DB)은 자문과 무관하게 차단한다.
"""

from pathlib import Path
from typing import Any

import yaml

from app.core.enums import AutomationClass, ClassificationGate
from app.product.schemas import ClassificationResult

DEFAULT_POLICY_PATH = Path("configs") / "auto-block-policy.yaml"


class Classifier:
    def __init__(self, policy_path: Path = DEFAULT_POLICY_PATH) -> None:
        with open(policy_path, encoding="utf-8") as f:
            self._policy: dict[str, Any] = yaml.safe_load(f)

    def classify(self, text: str) -> ClassificationResult:
        normalized = text.lower()

        blocked_labels: list[str] = []
        alternatives: list[str] = []
        for rule in self._policy.get("prohibited", {}).values():
            if _contains_any(normalized, rule["keywords"]):
                blocked_labels.append(rule["label"])
                alternatives.append(rule["alternative"])
        if blocked_labels:
            return ClassificationResult(
                automation_class=AutomationClass.EXPERT_REVIEW_REQUIRED,
                gate=ClassificationGate.BLOCKED,
                reasons=[f"자동 차단 항목 감지: {label}" for label in blocked_labels],
                prohibited_features=blocked_labels,
                user_message=(
                    "다음 기능은 안전을 위해 이 시스템이 자동으로 만들지 않습니다: "
                    + ", ".join(blocked_labels)
                    + "\n대안: "
                    + " / ".join(alternatives)
                ),
            )

        unsupported = self._policy.get("unsupported", {})
        matched_unsupported = _matched(normalized, unsupported.get("keywords", []))
        if matched_unsupported:
            return ClassificationResult(
                automation_class=AutomationClass.UNSUPPORTED,
                gate=ClassificationGate.UNSUPPORTED,
                reasons=[f"지원 범위 밖 기능: {kw}" for kw in matched_unsupported],
                user_message=(
                    "요청하신 프로젝트에는 현재 시스템이 만들 수 없는 부분이 있습니다: "
                    + ", ".join(matched_unsupported)
                    + "\n해당 부분을 제외하거나 다른 방식(웹 서비스 등)으로 바꾸면 "
                    "진행할 수 있습니다."
                ),
            )

        expert = self._policy.get("expert_review", {})
        matched_expert = _matched(normalized, expert.get("keywords", []))
        if matched_expert:
            return ClassificationResult(
                automation_class=AutomationClass.EXPERT_REVIEW_REQUIRED,
                gate=ClassificationGate.NEEDS_EXPERT,
                reasons=[f"전문가 검토 필요 항목: {kw}" for kw in matched_expert],
                user_message=(
                    "다음 내용은 진행 전에 개발자 확인이 필요합니다: "
                    + ", ".join(matched_expert)
                    + "\n개발자에게 전달할 자료를 준비해 드릴 수 있습니다."
                ),
            )

        risky = self._policy.get("risky", {})
        matched_risky = _matched(normalized, risky.get("keywords", []))
        if matched_risky:
            return ClassificationResult(
                automation_class=AutomationClass.AI_ASSISTED,
                gate=ClassificationGate.NEEDS_APPROVAL,
                reasons=[f"위험 경계 기능: {kw}" for kw in matched_risky],
                risky_features=matched_risky,
                user_message=(
                    "다음 기능은 오류 위험이 있어 첫 버전에서 제외하기를 권장합니다: "
                    + ", ".join(matched_risky)
                    + "\n제외한 범위로 진행하는 것을 승인하시겠어요? "
                    "이후 단계적으로 추가할 수 있습니다."
                ),
            )

        return ClassificationResult(
            automation_class=AutomationClass.SELF_SERVICE,
            gate=ClassificationGate.PROCEED,
            reasons=["자동 차단·위험 항목이 감지되지 않음"],
            user_message="이 프로젝트는 AI가 자동으로 진행할 수 있습니다.",
        )


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _matched(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw.lower() in text]
