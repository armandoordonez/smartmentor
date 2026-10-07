"""Composición: construye los servicios de identidad con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.identity.repository_impl import (
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserRoleRepository,
)
from app.domains.identity.service import RoleService, UserRoleService, UserService


def get_role_service(session: SessionDep) -> RoleService:
    return RoleService(SqlAlchemyRoleRepository(session), SqlAlchemyUnitOfWork(session))


def get_user_service(session: SessionDep) -> UserService:
    return UserService(SqlAlchemyUserRepository(session), SqlAlchemyUnitOfWork(session))


def get_user_role_service(session: SessionDep) -> UserRoleService:
    return UserRoleService(SqlAlchemyUserRoleRepository(session), SqlAlchemyUnitOfWork(session))
