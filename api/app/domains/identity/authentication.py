"""Autenticación de usuarios de la aplicación a partir de una identidad del proveedor (Keycloak).

Reglas (decisión D-03):
  1. Si hay un usuario enlazado al `sub` del token, es ese.
  2. Si no, se busca por el correo del token, solo si el proveedor lo marca como verificado:
     si existe y no está enlazado a otra identidad, se enlaza.
  3. Si tampoco existe, se crea automáticamente con el rol `student`.
Los administradores y docentes los crea un administrador desde la propia API; el rol que cuenta
para autorizar es el de `user_roles`, no el que traiga el token.
"""

from dataclasses import dataclass

from app.common.constants import RoleCode
from app.common.exceptions import ConflictError, ForbiddenError
from app.common.unit_of_work import UnitOfWork
from app.domains.identity.entities import User, UserRole
from app.domains.identity.repository import (
    RoleRepository,
    UserRepository,
    UserRoleRepository,
)


@dataclass(frozen=True)
class ExternalIdentity:
    """Identidad que entrega el proveedor, ya validada."""

    subject: str
    email: str | None
    email_verified: bool
    full_name: str | None


@dataclass(frozen=True)
class CurrentUser:
    """Usuario autenticado de la aplicación y sus roles (de la base de datos)."""

    id: int
    full_name: str
    email: str
    roles: frozenset[str]
    identity_provider: str | None
    identity_subject: str | None

    def has_any_role(self, *codes: str) -> bool:
        return bool(self.roles & set(codes))


class AuthenticationService:
    def __init__(
        self,
        users: UserRepository,
        roles: RoleRepository,
        user_roles: UserRoleRepository,
        uow: UnitOfWork,
        *,
        provider: str,
    ) -> None:
        self._users = users
        self._roles = roles
        self._user_roles = user_roles
        self._uow = uow
        self._provider = provider

    async def resolve(self, identity: ExternalIdentity) -> CurrentUser:
        user = await self._find_or_provision(identity)
        if not user.active:
            raise ForbiddenError("The account is deactivated.", code="ACCOUNT_DEACTIVATED")
        assert user.id is not None
        roles = await self._users.get_role_codes(user.id)
        return CurrentUser(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            roles=roles,
            identity_provider=user.identity_provider,
            identity_subject=user.identity_subject,
        )

    async def _find_or_provision(self, identity: ExternalIdentity) -> User:
        linked = await self._users.get_by_identity(self._provider, identity.subject)
        if linked is not None:
            return linked

        if not identity.email or not identity.email_verified:
            raise ForbiddenError(
                "The identity provider has not verified the email of this account.",
                code="EMAIL_NOT_VERIFIED",
            )

        existing = await self._users.get_by_email(identity.email)
        if existing is not None:
            return await self._link(existing, identity)

        try:
            return await self._provision_student(identity)
        except ConflictError:
            # Otra petición creó o enlazó al mismo usuario a la vez: se vuelve a buscar.
            concurrent = await self._users.get_by_identity(self._provider, identity.subject)
            if concurrent is not None:
                return concurrent
            raise

    async def _link(self, user: User, identity: ExternalIdentity) -> User:
        if user.identity_subject is not None:
            raise ForbiddenError(
                "This email already belongs to a user linked to another identity.",
                code="IDENTITY_CONFLICT",
            )
        assert user.id is not None
        linked = await self._users.update(
            user.id,
            {"identity_provider": self._provider, "identity_subject": identity.subject},
        )
        await self._uow.commit()
        assert linked is not None
        return linked

    async def _provision_student(self, identity: ExternalIdentity) -> User:
        assert identity.email is not None
        student = await self._roles.get_by_code(RoleCode.STUDENT)
        if student is None or student.id is None:
            raise RuntimeError("The student role is missing: run the Liquibase changelog.")
        user = await self._users.add(
            User(
                full_name=identity.full_name or identity.email.split("@")[0],
                email=identity.email,
                identity_provider=self._provider,
                identity_subject=identity.subject,
            )
        )
        assert user.id is not None
        await self._user_roles.add(UserRole(user_id=user.id, role_id=student.id))
        await self._uow.commit()
        return user
