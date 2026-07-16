"""질문 카드 생성 — UNKNOWN 요구사항과 미해결 질문을 비개발자 질문으로 변환."""

from app.product.schemas import QuestionDraft, RequirementSet


def build_question_cards(requirement_set: RequirementSet) -> list[QuestionDraft]:
    """중복(key 기준)을 제거한 질문 카드 목록. 기술 용어를 사용자에게 묻지 않는다."""
    cards: dict[str, QuestionDraft] = {}
    for question in requirement_set.open_questions:
        cards.setdefault(question.key, question)
    return list(cards.values())
