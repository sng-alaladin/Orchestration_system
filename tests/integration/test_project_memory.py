"""Project Memory 통합 테스트 — 저장, 버전, Decision Log, Feedback."""

import uuid

from app.core.enums import (
    DecisionSource,
    ProductState,
    RequirementCategory,
    RequirementStatus,
)
from app.core.security import hash_password
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import SessionFactory
from app.product.schemas import RequirementDraft
from app.project_memory.service import ProjectMemoryService


def _draft(key: str, description: str, status: RequirementStatus) -> RequirementDraft:
    return RequirementDraft(
        key=key,
        description=description,
        status=status,
        category=RequirementCategory.FUNCTIONAL,
    )


async def _make_project(session_factory: SessionFactory) -> uuid.UUID:
    async with session_factory() as session:
        user = User(
            email=f"memory-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("pw-123456"),
            display_name="메모리 테스트",
        )
        session.add(user)
        await session.flush()
        project = Project(
            user_id=user.id, name="메모리 테스트", status=ProductState.IDEA_RECEIVED
        )
        session.add(project)
        await session.commit()
        return project.id


async def test_requirement_versioning(session_factory: SessionFactory) -> None:
    project_id = await _make_project(session_factory)
    async with session_factory() as session:
        memory = ProjectMemoryService(session)
        await memory.requirements.sync(
            project_id,
            [_draft("FR-001", "엑셀을 읽는다", RequirementStatus.CONFIRMED)],
            change_reason="최초 초안",
        )
        # 내용 변경 → 버전 증가 + 이력 기록
        [updated] = await memory.requirements.sync(
            project_id,
            [_draft("FR-001", "엑셀과 CSV를 읽는다", RequirementStatus.CONFIRMED)],
            change_reason="사용자 답변 반영",
        )
        assert updated.version == 2
        history = await memory.versions.history(updated.id)
        assert [v.version for v in history] == [1, 2]
        assert history[0].description == "엑셀을 읽는다"

        # 동일 내용 재동기화 → 버전 유지
        [same] = await memory.requirements.sync(
            project_id,
            [_draft("FR-001", "엑셀과 CSV를 읽는다", RequirementStatus.CONFIRMED)],
            change_reason="변경 없음",
        )
        assert same.version == 2
        await session.commit()


async def test_removed_requirement_is_deactivated_not_deleted(
    session_factory: SessionFactory,
) -> None:
    project_id = await _make_project(session_factory)
    async with session_factory() as session:
        memory = ProjectMemoryService(session)
        await memory.requirements.sync(
            project_id,
            [
                _draft("FR-001", "엑셀을 읽는다", RequirementStatus.CONFIRMED),
                _draft("FR-002", "차트를 그린다", RequirementStatus.INFERRED),
            ],
            change_reason="최초 초안",
        )
        await memory.requirements.sync(
            project_id,
            [_draft("FR-001", "엑셀을 읽는다", RequirementStatus.CONFIRMED)],
            change_reason="범위 축소",
        )
        active = await memory.requirements.list_active(project_id)
        assert [r.req_key for r in active] == ["FR-001"]
        await session.commit()


async def test_decision_log_and_feedback(session_factory: SessionFactory) -> None:
    project_id = await _make_project(session_factory)
    async with session_factory() as session:
        memory = ProjectMemoryService(session)
        first = await memory.decisions.add(
            project_id,
            title="파일 보관 기간",
            decision="1년간 보관",
            source=DecisionSource.USER_CONFIRMED,
        )
        second = await memory.decisions.add(
            project_id, title="보고서 형식", decision="Word 문서로 생성"
        )
        assert (first.decision_key, second.decision_key) == ("DEC-001", "DEC-002")

        await memory.decisions.supersede(first)
        active = await memory.decisions.list_active(project_id)
        assert [d.decision_key for d in active] == ["DEC-002"]

        user_id = (await session.get(Project, project_id)).user_id  # type: ignore[union-attr]
        await memory.feedback.add(project_id, user_id, "보고서에 로고를 넣어 주세요")
        feedback = await memory.feedback.list_for_project(project_id)
        assert len(feedback) == 1
        await session.commit()
