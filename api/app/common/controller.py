"""Fábrica de routers CRUD: mismos endpoints y convenciones para todos los recursos.

Convenciones (estándar de microservicios, sección 12):
  POST   /<recursos>                   crea (201)
  GET    /<recursos>/{id}              consulta (200)
  GET    /<recursos>?limit=&offset=&active=&<filtros>   lista paginada (200)
  PATCH  /<recursos>/{id}              actualiza parcialmente (200)
  PATCH  /<recursos>/{id}/deactivate   inactiva (200)
  PATCH  /<recursos>/{id}/activate     activa (200)
No hay DELETE: el borrado es lógico.

Las rutas de lectura (GET) llevan `read_guard` y las de escritura (POST, PATCH) `write_guard`:
dependencias de autorización que entrega cada controlador (ver app/auth/policies.py).
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.common.entities import BaseEntity
from app.common.schemas import Page, RequestSchema, ResponseSchema
from app.common.service import CrudService


def no_filters() -> dict[str, Any]:
    return {}


def build_crud_router(
    *,
    prefix: str,
    tag: str,
    get_service: Callable[..., Any],
    entity_cls: type[BaseEntity],
    create_schema: type[RequestSchema],
    update_schema: type[RequestSchema],
    response_schema: type[ResponseSchema],
    read_guard: Callable[..., Any],
    write_guard: Callable[..., Any],
    filters: Callable[..., dict[str, Any]] = no_filters,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    read = [Depends(read_guard)]
    write = [Depends(write_guard)]
    page_schema = Page[response_schema]
    ServiceDep = Annotated[CrudService[Any], Depends(get_service)]  # noqa: N806
    FiltersDep = Annotated[dict[str, Any], Depends(filters)]  # noqa: N806

    @router.post("", response_model=response_schema, status_code=201, dependencies=write)
    async def create(payload: create_schema, service: ServiceDep) -> BaseModel:
        entity = await service.create(entity_cls(**payload.model_dump()))
        return response_schema.model_validate(entity)

    @router.get("", response_model=page_schema, dependencies=read)
    async def list_items(
        service: ServiceDep,
        filter_values: FiltersDep,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        active: Annotated[
            bool, Query(description="Filtra por estado; por defecto solo activos")
        ] = True,
    ) -> BaseModel:
        items, total = await service.search(
            filters=filter_values, active=active, limit=limit, offset=offset
        )
        return page_schema(
            items=[response_schema.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    @router.get("/{item_id}", response_model=response_schema, dependencies=read)
    async def get_item(item_id: int, service: ServiceDep) -> BaseModel:
        return response_schema.model_validate(await service.get(item_id))

    @router.patch("/{item_id}", response_model=response_schema, dependencies=write)
    async def update_item(
        item_id: int,
        payload: update_schema,
        service: ServiceDep,
    ) -> BaseModel:
        changes = payload.model_dump(exclude_unset=True)
        return response_schema.model_validate(await service.update(item_id, changes))

    @router.patch("/{item_id}/deactivate", response_model=response_schema, dependencies=write)
    async def deactivate_item(item_id: int, service: ServiceDep) -> BaseModel:
        return response_schema.model_validate(await service.deactivate(item_id))

    @router.patch("/{item_id}/activate", response_model=response_schema, dependencies=write)
    async def activate_item(item_id: int, service: ServiceDep) -> BaseModel:
        return response_schema.model_validate(await service.activate(item_id))

    return router
