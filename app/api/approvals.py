"""승인 API — 요구사항 승인, 축소 범위 승인."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.core.auth import get_app_settings, get_current_user
from app.core.config import Settings
from app.core.enums import ApprovalDecision, ApprovalType
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.db.session import get_db
from app.orchestrator.state_machine import StateMachineError
from app.product.workflow import WorkflowStateError, build_workflow

router = APIRouter(prefix="/api/projects/{project_id}/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    approval_type: ApprovalType
    decision: ApprovalDecision
    comment: str | None = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    approval_type: str
    decision: str
    comment: str | None


@router.post("")
async def decide(
    payload: ApprovalRequest,
    project: Annotated[Project, Depends(get_owned_project)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, str]:
    workflow = build_workflow(db, settings)
    try:
        if payload.approval_type == ApprovalType.REQUIREMENTS:
            await workflow.decide_requirements(project, user, payload.decision, payload.comment)
        elif payload.approval_type == ApprovalType.REDUCED_SCOPE:
            await workflow.decide_reduced_scope(project, user, payload.decision, payload.comment)
        elif payload.approval_type == ApprovalType.EXPANSION:
            await workflow.decide_expansion(project, user, payload.decision, payload.comment)
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{payload.approval_type} 승인은 아직 지원되지 않습니다.",
            )
    except (WorkflowStateError, StateMachineError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    return {"status": project.status, "status_reason": project.status_reason or ""}


@router.get("")
async def list_approvals(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApprovalResponse]:
    stmt = (
        select(UserApproval)
        .where(UserApproval.project_id == project.id)
        .order_by(UserApproval.created_at)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ApprovalResponse(
            id=a.id, approval_type=a.approval_type, decision=a.decision, comment=a.comment
        )
        for a in rows
    ]
