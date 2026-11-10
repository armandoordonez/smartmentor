"""Composición: construye los servicios de identidad con sus repositorios SQLAlchemy."""

from typing import Annotated

from fastapi import Depends, Request

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.config import get_settings
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.assessments.dependencies import build_profile_listener
from app.domains.identity.repository_impl import (
    SqlAlchemyConsentRepository,
    SqlAlchemyDataSubjectRequestRepository,
    SqlAlchemyProfileRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserRoleRepository,
)
from app.domains.identity.service import (
    ConsentService,
    DataSubjectRequestService,
    MeService,
    NullRoleSync,
    ProfileService,
    RoleService,
    RoleSyncPort,
    UserRolesAdminService,
    UserRoleService,
    UserService,
)


def get_role_service(session: SessionDep) -> RoleService:
    return RoleService(SqlAlchemyRoleRepository(session), SqlAlchemyUnitOfWork(session))


def get_user_service(session: SessionDep) -> UserService:
    return UserService(SqlAlchemyUserRepository(session), SqlAlchemyUnitOfWork(session))


def get_user_role_service(session: SessionDep) -> UserRoleService:
    return UserRoleService(
        SqlAlchemyUserRoleRepository(session),
        SqlAlchemyUserRepository(session),
        SqlAlchemyRoleRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_role_sync(request: Request) -> RoleSyncPort:
    sync: RoleSyncPort | None = getattr(request.app.state, "role_sync", None)
    return sync or NullRoleSync()


def get_user_roles_admin_service(
    session: SessionDep, sync: Annotated[RoleSyncPort, Depends(get_role_sync)]
) -> UserRolesAdminService:
    return UserRolesAdminService(
        SqlAlchemyUserRepository(session),
        SqlAlchemyRoleRepository(session),
        SqlAlchemyUserRoleRepository(session),
        SqlAlchemyUnitOfWork(session),
        sync,
    )


def get_profile_service(session: SessionDep, ai: AiServiceDep) -> ProfileService:
    """Con el recálculo de niveles y pasos pendientes al cambiar el perfil (E15)."""
    return ProfileService(
        SqlAlchemyProfileRepository(session),
        SqlAlchemyUnitOfWork(session),
        listener=build_profile_listener(session, ai),
    )


def get_consent_service(session: SessionDep) -> ConsentService:
    return ConsentService(SqlAlchemyConsentRepository(session), SqlAlchemyUnitOfWork(session))


def get_data_subject_request_service(session: SessionDep) -> DataSubjectRequestService:
    return DataSubjectRequestService(
        SqlAlchemyDataSubjectRequestRepository(session), SqlAlchemyUnitOfWork(session)
    )


def get_me_service(session: SessionDep) -> MeService:
    return MeService(
        ProfileService(SqlAlchemyProfileRepository(session), SqlAlchemyUnitOfWork(session)),
        get_consent_service(session),
        context=get_settings().app_context_profile,
    )
