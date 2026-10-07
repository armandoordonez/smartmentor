"""Composición de la aplicación FastAPI: lifespan, middleware, errores y routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import TokenValidator
from app.domains.assessments.controller import routers as assessments_routers
from app.domains.content.controller import routers as content_routers
from app.domains.courses.controller import routers as courses_routers
from app.domains.identity.controller import routers as identity_routers
from app.domains.learning_paths.controller import routers as learning_paths_routers
from app.domains.observability.controller import routers as observability_routers
from app.health.controller import router as health_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings)
    app.state.session_factory = create_session_factory(engine)
    app.state.token_validator = TokenValidator.from_settings(settings)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "API de negocio de SmartMentor. Autenticación con bearer tokens de Keycloak "
            "(realm smartmentor); la autorización usa los roles de user_roles."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    for routers in (
        identity_routers,
        courses_routers,
        learning_paths_routers,
        content_routers,
        assessments_routers,
        observability_routers,
    ):
        for router in routers:
            app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
