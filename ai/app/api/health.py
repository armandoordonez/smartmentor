"""``GET /health`` (process alive) and ``GET /ready`` (database, prompts, prices, settings)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.api.schemas import HealthResponse
from app.core.errors import ApiError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", responses={503: {"description": "NOT_READY with the missing items"}})
async def ready(container: ContainerDep) -> HealthResponse:
    missing = await container.readiness()
    if missing:
        raise ApiError(
            503,
            "NOT_READY",
            "The AI service is not ready: see 'missing'.",
            extra={"missing": missing},
        )
    return HealthResponse(status="ready")
