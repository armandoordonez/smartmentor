"""SmartMentor AI service (HTTP process ``ai``, ADR 0008).

Run: ``uvicorn app.main:app --host 0.0.0.0 --port 8030``. The worker is ``python -m app.worker``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api import health, jobs, prompts, tasks
from app.container import Container, build_container
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import require_service_token

SERVICE_NAME = "smartmentor-ai"


def create_app(container: Container | None = None, settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass a ready ``container``; production builds it from settings."""
    settings = settings or (container.settings if container else get_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        own = container is None
        app.state.container = container or build_container(settings)
        try:
            yield
        finally:
            if own:
                await app.state.container.close()

    configure_logging(
        service=SERVICE_NAME,
        environment=settings.app_env,
        timezone=settings.app_timezone,
        level=settings.log_level,
    )
    app = FastAPI(
        title="SmartMentor AI",
        version="0.1.0",
        description="Internal AI service: jobs, synchronous tasks and versioned prompts.",
        lifespan=lifespan,
    )
    if container is not None:
        app.state.container = container
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    secured = [Depends(require_service_token)]
    app.include_router(jobs.router, dependencies=secured)
    app.include_router(tasks.router, dependencies=secured)
    app.include_router(prompts.router, dependencies=secured)
    return app


def __getattr__(name: str) -> FastAPI:
    # ``uvicorn app.main:app`` builds the app on first access (settings read at start-up).
    if name == "app":
        return create_app()
    raise AttributeError(name)
