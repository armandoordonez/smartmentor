"""Composición de la aplicación FastAPI: lifespan, middleware, errores y routers."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.dependencies import DOCS_LOGIN_SCOPES
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import TokenValidator
from app.domains.ai_gateway.controller import routers as ai_gateway_routers
from app.domains.ai_gateway.factory import create_ai_service
from app.domains.ai_gateway.sweeper import run_sweeper
from app.domains.content.controller import routers as content_routers
from app.domains.courses.controller import routers as courses_routers
from app.domains.identity.controller import routers as identity_routers
from app.health.controller import router as health_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings)
    app.state.session_factory = create_session_factory(engine)
    app.state.token_validator = TokenValidator.from_settings(settings)
    ai_service, ai_client = create_ai_service(settings)
    app.state.ai_service = ai_service
    sweeper: asyncio.Task[None] | None = None
    if settings.ai_sweep_interval_seconds > 0:
        # Ingesta los trabajos de `ai/` terminados que nadie consultó (plan 5.3.3).
        sweeper = asyncio.create_task(
            run_sweeper(app.state.session_factory, ai_service, settings.ai_sweep_interval_seconds),
            name="ai-jobs-sweeper",
        )
    try:
        yield
    finally:
        if sweeper is not None:
            sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweeper
        if ai_client is not None:
            await ai_client.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    docs_client = settings.oidc_docs_client_id
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "API de negocio de SmartMentor. Autenticación con bearer tokens de Keycloak "
            "(realm smartmentor); la autorización usa los roles de user_roles.\n\n"
            "**Cómo probar desde esta página:** pulsa *Authorize* y usa *Login (usuario y "
            "contraseña)*, o pega un access token en *Token (pegar)*."
        ),
        lifespan=lifespan,
        # Swagger UI: el login con usuario y contraseña usa este cliente (solo desarrollo).
        swagger_ui_init_oauth=(
            {"clientId": docs_client, "scopes": " ".join(DOCS_LOGIN_SCOPES)}
            if docs_client
            else None
        ),
        swagger_ui_parameters={"persistAuthorization": True},
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    for routers in (identity_routers, courses_routers, ai_gateway_routers, content_routers):
        for router in routers:
            app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
