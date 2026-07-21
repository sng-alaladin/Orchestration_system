"""FastAPI 애플리케이션 팩토리."""

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response

from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.requirements import router as requirements_router
from app.capabilities.registry import CapabilityRegistry
from app.core.bootstrap import seed_admin_user
from app.core.config import Settings, get_settings
from app.db.session import create_engine_and_factory
from app.mcp.registry import McpRegistry
from app.observability.logging import configure_logging, get_logger


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(log_level=app_settings.log_level, log_json=app_settings.log_json)
    logger = get_logger("app.main")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, factory = create_engine_and_factory(app_settings)
        app.state.engine = engine
        app.state.session_factory = factory
        await seed_admin_user(factory, app_settings)
        async with factory() as session:
            await CapabilityRegistry(session).sync_from_config(
                Path(app_settings.capabilities_config)
            )
            await McpRegistry(session).sync_from_config(
                Path(app_settings.mcp_servers_config)
            )
            await session.commit()
        logger.info("app_started", env=app_settings.env)
        yield
        await engine.dispose()
        logger.info("app_stopped")

    app = FastAPI(
        title="AI Orchestrator",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return response

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    app.include_router(requirements_router)
    app.include_router(approvals_router)
    return app


app = create_app()
