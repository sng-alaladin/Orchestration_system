"""헬스체크 엔드포인트.

- /health       프로세스 생존 (컨테이너 healthcheck 대상)
- /health/ready DB 연결 포함 준비 상태
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health_ready_db_failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "down"}
    return {"status": "ok", "database": "up"}
