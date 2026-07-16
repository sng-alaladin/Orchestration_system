"""요구사항 ↔ Decision 충돌 탐지 단위 테스트."""

import uuid

from app.core.enums import RequirementCategory, RequirementStatus
from app.db.models.project_decision import ProjectDecision
from app.product.schemas import RequirementDraft
from app.project_memory.conflict_detector import find_conflicts


def _decision(decision_text: str, title: str = "동일 파일명 처리 방식") -> ProjectDecision:
    return ProjectDecision(
        project_id=uuid.uuid4(),
        decision_key="DEC-001",
        title=title,
        decision=decision_text,
        source="user_confirmed",
        status="active",
    )


def _draft(description: str) -> RequirementDraft:
    return RequirementDraft(
        key="FR-001",
        description=description,
        status=RequirementStatus.CONFIRMED,
        category=RequirementCategory.FUNCTIONAL,
    )


def test_overlapping_requirement_is_flagged() -> None:
    decision = _decision("기존 파일을 덮어쓰지 않고 번호를 붙인다")
    conflicts = find_conflicts([_draft("기존 파일을 같은 이름으로 덮어쓴다")], [decision])
    assert len(conflicts) == 1
    assert conflicts[0].decision_key == "DEC-001"
    assert "기존 정책" in conflicts[0].message  # 사용자 확인 질문 형태


def test_unrelated_requirement_is_not_flagged() -> None:
    decision = _decision("기존 파일을 덮어쓰지 않고 번호를 붙인다")
    conflicts = find_conflicts(
        [_draft("매주 월요일에 요약 리포트를 이메일로 발송한다")], [decision]
    )
    assert conflicts == []


def test_agreement_is_not_flagged() -> None:
    decision = _decision("기존 파일을 덮어쓰지 않고 번호를 붙인다")
    conflicts = find_conflicts(
        [_draft("저장 시 기존 파일을 덮어쓰지 않고 번호를 붙인다")], [decision]
    )
    assert conflicts == []


def test_superseded_decision_is_ignored_by_caller_contract() -> None:
    # find_conflicts는 활성 결정만 받는 계약이다 — 비활성 결정을 걸러 전달하면 충돌 없음
    conflicts = find_conflicts([_draft("기존 파일을 같은 이름으로 덮어쓴다")], [])
    assert conflicts == []
