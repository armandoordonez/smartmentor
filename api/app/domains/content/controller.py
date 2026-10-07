"""Endpoints de contenido: /resources."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ANY_ROLE, STAFF
from app.common.controller import build_crud_router
from app.domains.content.dependencies import get_resource_service
from app.domains.content.entities import Resource
from app.domains.content.schemas import ResourceCreate, ResourceResponse, ResourceUpdate


def resource_filters(
    topic_id: Annotated[int | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"topic_id": topic_id, "resource_type": resource_type}


routers: list[APIRouter] = [
    build_crud_router(
        prefix="/resources",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*STAFF),
        tag="resources",
        get_service=get_resource_service,
        entity_cls=Resource,
        create_schema=ResourceCreate,
        update_schema=ResourceUpdate,
        response_schema=ResourceResponse,
        filters=resource_filters,
    ),
]
