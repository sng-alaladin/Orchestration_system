"""API 공통 의존성 — 프로젝트 소유권 검증 등."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db


async def get_owned_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        # 존재 여부를 노출하지 않도록 타인 프로젝트도 동일하게 404
        raise HTTPException(status.HTTP_404_NOT_FOUND, "프로젝트를 찾을 수 없습니다.")
    return project
