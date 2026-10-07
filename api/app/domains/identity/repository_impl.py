"""Repositorios SQLAlchemy de identidad."""

from typing import ClassVar

from sqlalchemy import func, select

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.identity.entities import Role, User, UserRole
from app.domains.identity.models import RoleModel, UserModel, UserRoleModel


class SqlAlchemyRoleRepository(SqlAlchemyCrudRepository[RoleModel, Role]):
    model = RoleModel
    entity = Role
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "roles_code_uq": ("ROLE_CODE_ALREADY_EXISTS", "A role with this code already exists."),
    }

    async def get_by_code(self, code: str) -> Role | None:
        row = (
            await self._session.execute(select(RoleModel).where(RoleModel.code == code))
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)


class SqlAlchemyUserRepository(SqlAlchemyCrudRepository[UserModel, User]):
    model = UserModel
    entity = User
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "users_email_uq": ("EMAIL_ALREADY_REGISTERED", "A user with this email already exists."),
        "users_identity_uq": (
            "IDENTITY_ALREADY_LINKED",
            "This identity is already linked to another user.",
        ),
        "users_identity_ck": (
            "IDENTITY_INCOMPLETE",
            "identity_provider and identity_subject must be set together.",
        ),
    }

    async def get_by_identity(self, provider: str, subject: str) -> User | None:
        row = (
            await self._session.execute(
                select(UserModel).where(
                    UserModel.identity_provider == provider, UserModel.identity_subject == subject
                )
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def get_by_email(self, email: str) -> User | None:
        row = (
            await self._session.execute(
                select(UserModel).where(func.lower(UserModel.email) == email.lower())
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def get_role_codes(self, user_id: int) -> frozenset[str]:
        result = await self._session.execute(
            select(RoleModel.code)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.active.is_(True),
                RoleModel.active.is_(True),
            )
        )
        return frozenset(result.scalars().all())


class SqlAlchemyUserRoleRepository(SqlAlchemyCrudRepository[UserRoleModel, UserRole]):
    model = UserRoleModel
    entity = UserRole
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "user_roles_user_role_uq": ("ROLE_ALREADY_ASSIGNED", "The user already has this role."),
        "user_roles_user_id_fk": ("USER_NOT_FOUND", "The user does not exist."),
        "user_roles_role_id_fk": ("ROLE_NOT_FOUND", "The role does not exist."),
    }
