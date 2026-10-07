"""Endpoints de identidad: /roles, /users y /user-roles."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUserDep, require_roles
from app.auth.policies import ADMIN, ANY_ROLE, STAFF
from app.common.controller import build_crud_router
from app.domains.identity.dependencies import (
    get_role_service,
    get_user_role_service,
    get_user_service,
)
from app.domains.identity.entities import Role, User, UserRole
from app.domains.identity.schemas import (
    MeResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserResponse,
    UserRoleCreate,
    UserRoleResponse,
    UserRoleUpdate,
    UserUpdate,
)


def role_filters(code: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    return {"code": code}


def user_role_filters(
    user_id: Annotated[int | None, Query()] = None,
    role_id: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    return {"user_id": user_id, "role_id": role_id}


me_router = APIRouter(tags=["me"])


@me_router.get("/me", response_model=MeResponse)
async def read_me(user: CurrentUserDep) -> MeResponse:
    """El usuario autenticado, con sus roles de la base de datos."""
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        roles=sorted(user.roles),
        identity_provider=user.identity_provider,
        identity_subject=user.identity_subject,
    )


routers: list[APIRouter] = [
    me_router,
    build_crud_router(
        prefix="/roles",
        read_guard=require_roles(*ANY_ROLE),
        write_guard=require_roles(*ADMIN),
        tag="roles",
        get_service=get_role_service,
        entity_cls=Role,
        create_schema=RoleCreate,
        update_schema=RoleUpdate,
        response_schema=RoleResponse,
        filters=role_filters,
    ),
    build_crud_router(
        prefix="/users",
        read_guard=require_roles(*STAFF),
        write_guard=require_roles(*ADMIN),
        tag="users",
        get_service=get_user_service,
        entity_cls=User,
        create_schema=UserCreate,
        update_schema=UserUpdate,
        response_schema=UserResponse,
    ),
    build_crud_router(
        prefix="/user-roles",
        read_guard=require_roles(*ADMIN),
        write_guard=require_roles(*ADMIN),
        tag="user-roles",
        get_service=get_user_role_service,
        entity_cls=UserRole,
        create_schema=UserRoleCreate,
        update_schema=UserRoleUpdate,
        response_schema=UserRoleResponse,
        filters=user_role_filters,
    ),
]
