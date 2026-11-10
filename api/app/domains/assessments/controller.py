"""Rutas públicas del badge: verificación «hosted» de Open Badges 2.0 (E10).

Son las únicas de `/api/v1` sin token: cualquiera (una plataforma de credenciales, un empleador)
debe poder verificar la aserción. Se piden por el `public_id` (UUID), nunca por el id secuencial,
y la aserción solo lleva el receptor con hash y sal.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.domains.assessments import badges
from app.domains.assessments.dependencies import BadgeServiceDep

router = APIRouter(tags=["badges-public"])


@router.get(
    "/badges/{public_id}/assertion.json",
    response_model=dict[str, Any],
    responses={404: {"description": "BADGE_NOT_FOUND"}},
)
async def badge_assertion(
    public_id: UUID, request: Request, service: BadgeServiceDep
) -> JSONResponse:
    """Aserción `badge.v1` (Open Badges 2.0, verificación hosted)."""
    badge = await service.public(public_id)
    assert badge.open_badges_metadata is not None  # noqa: S101
    base = str(request.base_url).rstrip("/")
    return JSONResponse(badges.with_base_url(badge.open_badges_metadata, base))


@router.get(
    "/badges/{public_id}/image.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "BADGE_NOT_FOUND"}},
)
async def badge_image(public_id: UUID, service: BadgeServiceDep) -> Response:
    badge = await service.public(public_id)
    return Response(
        content=badges.badge_png(str(badge.public_id)),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


routers: list[APIRouter] = [router]
