"""Endpoints de identidad: /me (CU-34, CU-35), perfil, autorizaciones y administración (CU-14)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from app.auth.dependencies import CurrentUserDep, require_roles
from app.auth.policies import ADMIN, ANY_ROLE
from app.common.constants import ConsentType
from app.common.controller import build_crud_router
from app.domains.identity.dependencies import (
    get_consent_service,
    get_data_subject_request_service,
    get_me_service,
    get_profile_service,
    get_role_service,
    get_user_role_service,
    get_user_roles_admin_service,
    get_user_service,
)
from app.domains.identity.entities import Consent, Role, User, UserProfile, UserRole
from app.domains.identity.schemas import (
    ConsentCreate,
    ConsentResponse,
    ConsentState,
    DataSubjectRequestCreate,
    DataSubjectRequestResponse,
    LanguageSkill,
    MeResponse,
    ProfileCompletenessResponse,
    ProfileResponse,
    ProfileUpdate,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserResponse,
    UserRoleCreate,
    UserRoleResponse,
    UserRolesResponse,
    UserRolesUpdate,
    UserRoleUpdate,
    UserUpdate,
)
from app.domains.identity.service import (
    ConsentService,
    DataSubjectRequestService,
    MeService,
    ProfileService,
    UserRolesAdminService,
)


def role_filters(code: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    return {"code": code}


def user_role_filters(
    user_id: Annotated[int | None, Query()] = None,
    role_id: Annotated[int | None, Query()] = None,
) -> dict[str, Any]:
    return {"user_id": user_id, "role_id": role_id}


def _profile_response(
    profile: UserProfile, recalculated: list[int] | None = None
) -> ProfileResponse:
    return ProfileResponse(
        description=profile.description,
        education_level=profile.education_level,
        qualification_title=profile.qualification_title,
        job_title=profile.job_title,
        experience_band=profile.experience_band,
        tools=[str(tool) for tool in profile.tools],
        languages=[LanguageSkill.model_validate(item) for item in profile.languages],
        resume_completed_at=profile.resume_completed_at,
        recalculated_enrollment_ids=recalculated,
    )


def _consent_response(consent: Consent) -> ConsentResponse:
    return ConsentResponse(
        id=consent.id or 0,
        consent_type=consent.consent_type,
        document_version=consent.document_version,
        granted_at=consent.granted_at,
        revoked_at=consent.revoked_at,
        granted=consent.in_force,
    )


me_router = APIRouter(tags=["me"])


@me_router.get("/me", response_model=MeResponse)
async def read_me(
    user: CurrentUserDep, service: Annotated[MeService, Depends(get_me_service)]
) -> MeResponse:
    """El usuario autenticado. El primer ingreso lo crea con el rol `learner` (CU-34)."""
    view = await service.view(user)
    consent_status = {
        code: ConsentState(
            granted=consent is not None and consent.in_force,
            document_version=consent.document_version if consent and consent.in_force else None,
            granted_at=consent.granted_at if consent and consent.in_force else None,
        )
        for code, consent in view.consents.items()
    }
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=user.ordered_roles,
        role_labels=view.role_labels,
        role_short_labels=view.role_short_labels,
        default_role=user.default_role,
        is_new_user=user.is_new_user,
        consent_status=consent_status,
        requires_consent=view.requires_consent,
        profile_completeness=ProfileCompletenessResponse(
            description=view.completeness.description,
            resume=view.completeness.resume,
            percent=view.completeness.percent,
        ),
        second_factor=user.second_factor,
    )


@me_router.get("/me/profile", response_model=ProfileResponse)
async def read_profile(
    user: CurrentUserDep, service: Annotated[ProfileService, Depends(get_profile_service)]
) -> ProfileResponse:
    return _profile_response(await service.get(user.id))


@me_router.put("/me/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: CurrentUserDep,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    """Reemplaza la descripción y la hoja de vida (E2, E2b, E15)."""
    values = payload.model_dump(mode="json")
    profile, recalculated = await service.update(user.id, values)
    return _profile_response(profile, recalculated)


@me_router.get("/me/consents", response_model=list[ConsentResponse])
async def list_consents(
    user: CurrentUserDep, service: Annotated[ConsentService, Depends(get_consent_service)]
) -> list[ConsentResponse]:
    return [_consent_response(c) for c in await service.list_consents(user.id)]


@me_router.post(
    "/me/consents",
    response_model=ConsentResponse,
    status_code=201,
    responses={200: {"model": ConsentResponse, "description": "Ya estaba vigente"}},
)
async def grant_consent(
    payload: ConsentCreate,
    user: CurrentUserDep,
    service: Annotated[ConsentService, Depends(get_consent_service)],
    response: Response,
) -> ConsentResponse:
    consent, created = await service.grant(user.id, payload.consent_type, payload.document_version)
    if not created:
        response.status_code = 200
    return _consent_response(consent)


@me_router.patch("/me/consents/{consent_type}/revoke", response_model=ConsentResponse)
async def revoke_consent(
    consent_type: ConsentType,
    user: CurrentUserDep,
    service: Annotated[ConsentService, Depends(get_consent_service)],
) -> ConsentResponse:
    return _consent_response(await service.revoke(user.id, consent_type))


@me_router.post(
    "/me/data-subject-requests", response_model=DataSubjectRequestResponse, status_code=201
)
async def create_data_subject_request(
    payload: DataSubjectRequestCreate,
    user: CurrentUserDep,
    service: Annotated[DataSubjectRequestService, Depends(get_data_subject_request_service)],
) -> DataSubjectRequestResponse:
    """Solicitud de acceso, rectificación o supresión (E11b). El administrador la ejecuta."""
    created = await service.create(user.id, payload.request_type, payload.comment)
    return DataSubjectRequestResponse(
        id=created.id or 0, request_type=created.request_type, status=created.status
    )


admin_router = APIRouter(tags=["users"])


@admin_router.get(
    "/users/{user_id}/roles",
    response_model=UserRolesResponse,
    dependencies=[Depends(require_roles(*ADMIN))],
)
async def read_user_roles(
    user_id: int,
    service: Annotated[UserRolesAdminService, Depends(get_user_roles_admin_service)],
) -> UserRolesResponse:
    return UserRolesResponse(roles=await service.get_roles(user_id))


@admin_router.put(
    "/users/{user_id}/roles",
    response_model=UserRolesResponse,
    dependencies=[Depends(require_roles(*ADMIN))],
)
async def replace_user_roles(
    user_id: int,
    payload: UserRolesUpdate,
    service: Annotated[UserRolesAdminService, Depends(get_user_roles_admin_service)],
) -> UserRolesResponse:
    """Asigna o quita roles (varios por usuario). Nunca deja la plataforma sin administrador."""
    return UserRolesResponse(
        roles=await service.set_roles(user_id, [r.value for r in payload.roles])
    )


routers: list[APIRouter] = [
    me_router,
    admin_router,
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
        read_guard=require_roles(*ADMIN),
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
