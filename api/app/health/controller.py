"""Verificación de salud (liveness) y disponibilidad (readiness). Sin versión: /health y /ready."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import problem_response

logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: el proceso responde. No consulta nada externo."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness: hay conexión a la base y la extensión vector está instalada."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    check = "database"
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            check = "vector_extension"
            found = await session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if found.scalar_one_or_none() is None:
                raise RuntimeError("vector extension is not installed")
    except Exception:
        logger.exception("readiness check failed", extra={"code": check})
        return problem_response(
            request,
            status=503,
            title="Service not ready",
            detail=f"Readiness check failed: {check}.",
            code="NOT_READY",
            extra={"failed_check": check},
        )
    return JSONResponse({"status": "ready", "checks": ["database", "vector_extension"]})
