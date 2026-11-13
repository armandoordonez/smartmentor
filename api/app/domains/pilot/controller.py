"""Endpoints del piloto (administrador): configuración, sorteo, inicio y preparación (AD4, AD4b)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN
from app.common.entities import require_id
from app.common.schemas import Page, RequestSchema, UtcDatetime
from app.domains.identity.authentication import CurrentUser
from app.domains.learning_paths.schemas import PathRef
from app.domains.pilot.dependencies import get_pilot_service
from app.domains.pilot.service import PilotConfig, PilotService, PilotView

AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN))]


PilotServiceDep = Annotated[PilotService, Depends(get_pilot_service)]


class PilotWrite(RequestSchema):
    learning_path_id: int = Field(gt=0)
    starts_on: date
    ends_on: date
    delayed_posttest_on: date | None = None
    random_seed: int | None = Field(default=None, ge=0, le=2**62)


class ArmCounts(BaseModel):
    personalized: int
    fixed: int


class PilotResponse(BaseModel):
    id: int
    learning_path_id: int
    starts_on: date
    ends_on: date
    delayed_posttest_on: date | None
    random_seed: int | None
    status: str
    arms: ArmCounts
    created_at: UtcDatetime | None
    updated_at: UtcDatetime | None
    # Nombre y grupo de la ruta para AD4 sin otra llamada (aditivo, 2026-11-12).
    learning_path: PathRef | None


class RandomizeResponse(BaseModel):
    personalized: int
    fixed: int
    skipped_without_consent: int
    random_seed: int


class ReadinessResponse(BaseModel):
    ready: bool
    missing: list[str]
    # Lo que AD4 muestra junto a los pendientes (aditivo, 2026-11-12).
    consents_accepted: int
    consents_total: int
    topics_total: int
    topics_with_items: int
    # Temas con versiones paralelas (mismo `equivalence_group`) para la ganancia de Hake.
    topics_with_equivalent_items: int


def _response(view: PilotView) -> PilotResponse:
    pilot = view.pilot
    return PilotResponse(
        id=require_id(pilot),
        learning_path_id=pilot.learning_path_id,
        starts_on=pilot.starts_on,
        ends_on=pilot.ends_on,
        delayed_posttest_on=pilot.delayed_posttest_on,
        random_seed=pilot.random_seed,
        status=pilot.status,
        arms=ArmCounts(
            personalized=view.arms.get("personalized", 0), fixed=view.arms.get("fixed", 0)
        ),
        created_at=pilot.created_at,
        updated_at=pilot.updated_at,
        learning_path=(
            PathRef(
                id=pilot.learning_path_id,
                name=view.path.name,
                group_label=view.path.group_label,
            )
            if view.path is not None
            else None
        ),
    )


def _config(payload: PilotWrite) -> PilotConfig:
    return PilotConfig(
        learning_path_id=payload.learning_path_id,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        delayed_posttest_on=payload.delayed_posttest_on,
        random_seed=payload.random_seed,
    )


router = APIRouter(tags=["pilot"])


@router.post("/pilots", response_model=PilotResponse, status_code=201)
async def create_pilot(
    payload: PilotWrite, _admin: AdminUser, service: PilotServiceDep
) -> PilotResponse:
    """Crea el piloto de una ruta en borrador (solo uno sin cerrar por ruta)."""
    return _response(await service.create(_config(payload)))


@router.get("/pilots", response_model=Page[PilotResponse])
async def list_pilots(
    _admin: AdminUser,
    service: PilotServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PilotResponse]:
    views, total = await service.list_all(limit=limit, offset=offset)
    return Page[PilotResponse](
        items=[_response(v) for v in views], total=total, limit=limit, offset=offset
    )


@router.get("/pilots/{pilot_id}", response_model=PilotResponse)
async def get_pilot(pilot_id: int, _admin: AdminUser, service: PilotServiceDep) -> PilotResponse:
    return _response(await service.get(pilot_id))


@router.put("/pilots/{pilot_id}", response_model=PilotResponse)
async def update_pilot(
    pilot_id: int, payload: PilotWrite, _admin: AdminUser, service: PilotServiceDep
) -> PilotResponse:
    """Cambia la configuración; `409 PILOT_ALREADY_STARTED` una vez iniciado."""
    return _response(await service.update(pilot_id, _config(payload)))


@router.post("/pilots/{pilot_id}/randomize", response_model=RandomizeResponse)
async def randomize_pilot(
    pilot_id: int, _admin: AdminUser, service: PilotServiceDep
) -> RandomizeResponse:
    """Sorteo con semilla entre quienes aceptaron `pilot_research`; solo antes de iniciar."""
    result = await service.randomize(pilot_id)
    return RandomizeResponse(
        personalized=result.personalized,
        fixed=result.fixed,
        skipped_without_consent=result.skipped_without_consent,
        random_seed=result.random_seed,
    )


@router.post("/pilots/{pilot_id}/start", response_model=PilotResponse)
async def start_pilot(pilot_id: int, _admin: AdminUser, service: PilotServiceDep) -> PilotResponse:
    return _response(await service.start(pilot_id))


@router.get("/pilots/{pilot_id}/readiness", response_model=ReadinessResponse)
async def pilot_readiness(
    pilot_id: int, _admin: AdminUser, service: PilotServiceDep
) -> ReadinessResponse:
    result = await service.readiness(pilot_id)
    return ReadinessResponse(
        ready=result.ready,
        missing=result.missing,
        consents_accepted=result.consents_accepted,
        consents_total=result.consents_total,
        topics_total=result.topics_total,
        topics_with_items=result.topics_with_items,
        topics_with_equivalent_items=result.topics_with_equivalent_items,
    )


@router.get("/pilots/{pilot_id}/fixed-path-preview", response_model=dict[str, Any])
async def fixed_path_preview(
    pilot_id: int, _admin: AdminUser, service: PilotServiceDep
) -> dict[str, Any]:
    """Vista previa de la ruta fija (`learning_path.v1` con `pilot_arm=fixed`)."""
    return await service.fixed_path_preview(pilot_id)


routers: list[APIRouter] = [router]
