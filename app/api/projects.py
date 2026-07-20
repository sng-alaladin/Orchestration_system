"""프로젝트 API — 생성, 조회, 기획안 분석 실행."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.core.auth import get_app_settings, get_current_user
from app.core.config import Settings
from app.core.enums import ProductState
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.user import User
from app.db.session import get_db
from app.orchestrator.state_machine import StateMachineError
from app.product.workflow import (
    EXPERT_CONSULTATION_NOT_READY,
    WorkflowStateError,
    build_workflow,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    idea_text: str | None = None


class ProjectUpdateRequest(BaseModel):
    idea_text: str = Field(min_length=1)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    status_reason: str | None

    @classmethod
    def from_model(cls, project: Project) -> "ProjectResponse":
        return cls(
            id=project.id,
            name=project.name,
            status=project.status,
            status_reason=project.status_reason,
        )


class ClassificationResponse(BaseModel):
    automation_class: str
    gate: str
    reasons: list[str]
    prohibited_features: list[str]
    risky_features: list[str]
    user_message: str


class ProjectDetailResponse(ProjectResponse):
    idea_text: str | None
    classification: ClassificationResponse | None


@router.post("", status_code=201)
async def create_project(
    payload: ProjectCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    project = Project(
        user_id=user.id,
        name=payload.name,
        idea_text=payload.idea_text,
        status=ProductState.IDEA_RECEIVED,
    )
    db.add(project)
    await db.commit()
    return ProjectResponse.from_model(project)


@router.get("")
async def list_projects(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectResponse]:
    stmt = (
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )
    projects = (await db.execute(stmt)).scalars().all()
    return [ProjectResponse.from_model(p) for p in projects]


@router.get("/{project_id}")
async def get_project(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectDetailResponse:
    stmt = (
        select(ProjectClassification)
        .where(ProjectClassification.project_id == project.id)
        .order_by(ProjectClassification.created_at.desc())
        .limit(1)
    )
    classification = (await db.execute(stmt)).scalar_one_or_none()
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        status=project.status,
        status_reason=project.status_reason,
        idea_text=project.idea_text,
        classification=(
            ClassificationResponse(
                automation_class=classification.automation_class,
                gate=classification.gate,
                reasons=classification.reasons,
                prohibited_features=classification.prohibited_features,
                risky_features=classification.risky_features,
                user_message=classification.user_message,
            )
            if classification
            else None
        ),
    )


@router.patch("/{project_id}")
async def update_idea(
    payload: ProjectUpdateRequest,
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    project.idea_text = payload.idea_text
    await db.commit()
    return ProjectResponse.from_model(project)


@router.post("/{project_id}/analyze")
async def analyze_project(
    project: Annotated[Project, Depends(get_owned_project)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ProjectResponse:
    workflow = build_workflow(db, settings)
    try:
        await workflow.run_analysis(project, actor_id=user.id)
    except (WorkflowStateError, StateMachineError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    return ProjectResponse.from_model(project)


@router.post("/{project_id}/consultation")
async def request_consultation(
    project: Annotated[Project, Depends(get_owned_project)],
) -> None:
    """전문가 상담 패키지 생성 — Phase 7(세션 4)에서 구현 예정.

    조용히 실패하지 않도록 명시적 501(Not Implemented)을 반환한다.
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, EXPERT_CONSULTATION_NOT_READY)
