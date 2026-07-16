"""요구사항·질문 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.core.auth import get_app_settings, get_current_user
from app.core.config import Settings
from app.db.models.project import Project
from app.db.models.project_requirement import ProjectRequirement
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.user import User
from app.db.session import get_db
from app.product.workflow import WorkflowStateError, build_workflow

router = APIRouter(prefix="/api/projects/{project_id}", tags=["requirements"])


class RequirementResponse(BaseModel):
    req_key: str
    category: str
    description: str
    status: str
    priority: str | None
    version: int


class QuestionResponse(BaseModel):
    question_key: str
    question: str
    reason: str | None
    status: str
    answer: str | None


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


@router.get("/requirements")
async def list_requirements(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RequirementResponse]:
    stmt = (
        select(ProjectRequirement)
        .where(
            ProjectRequirement.project_id == project.id,
            ProjectRequirement.is_active.is_(True),
        )
        .order_by(ProjectRequirement.req_key)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        RequirementResponse(
            req_key=r.req_key,
            category=r.category,
            description=r.description,
            status=r.status,
            priority=r.priority,
            version=r.version,
        )
        for r in rows
    ]


@router.get("/questions")
async def list_questions(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuestionResponse]:
    stmt = (
        select(RequirementQuestion)
        .where(RequirementQuestion.project_id == project.id)
        .order_by(RequirementQuestion.question_key)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        QuestionResponse(
            question_key=q.question_key,
            question=q.question,
            reason=q.reason,
            status=q.status,
            answer=q.answer,
        )
        for q in rows
    ]


@router.post("/questions/{question_key}/answer")
async def answer_question(
    question_key: str,
    payload: AnswerRequest,
    project: Annotated[Project, Depends(get_owned_project)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, str]:
    workflow = build_workflow(db, settings)
    try:
        await workflow.answer_question(project, question_key, payload.answer, user)
    except WorkflowStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    return {"status": project.status, "status_reason": project.status_reason or ""}
