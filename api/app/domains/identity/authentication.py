"""Primer ingreso y autenticación de usuarios de la aplicación (CU-34, G-04, G-01).

Reglas (docs/contracts/api-v2.md, sección 2.1):
  1. Si hay un usuario enlazado al `sub` del token, es ese (no se exige nada más del correo).
  2. Si no, el correo debe venir verificado (`403 EMAIL_NOT_VERIFIED`): con el registro abierto, un
     correo sin verificar permitiría quedarse con el perfil de otra persona (por ejemplo, el del
     administrador sembrado).
  3. Con correo verificado, se enlaza al usuario con ese correo que aún no tenga identidad; si no
     existe, se crea con el rol `learner`.
  4. Es idempotente y seguro ante llamadas simultáneas: cada paso es una sentencia atómica
     (`UPDATE ... WHERE identity_subject IS NULL`, `INSERT ... ON CONFLICT DO NOTHING`) y, si otra
     petición ganó la carrera, se vuelve a leer al usuario.
  5. Un usuario con `active = false` recibe `403 ACCOUNT_DEACTIVATED`.
El rol que cuenta para autorizar es el de `user_roles`, no el que traiga el token.
"""

from dataclasses import dataclass

from app.common.constants import ROLE_PRIVILEGE_ORDER, RoleCode
from app.common.entities import require_id
from app.common.exceptions import ConflictError, ForbiddenError
from app.common.unit_of_work import UnitOfWork
from app.domains.identity.entities import User
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
    second_factor: bool = False


@dataclass(frozen=True)
class CurrentUser:
    """Usuario autenticado de la aplicación y sus roles (de la base de datos)."""

    id: int
    full_name: str
    email: str
    roles: frozenset[str]
    identity_provider: str | None
    identity_subject: str | None
    is_new_user: bool = False
    second_factor: bool = False

    def has_any_role(self, *codes: str) -> bool:
        return bool(self.roles & set(codes))

    @property
    def ordered_roles(self) -> list[str]:
        """Roles en el orden admin, instructor, learner (los desconocidos, al final)."""
        known = [code.value for code in ROLE_PRIVILEGE_ORDER if code.value in self.roles]
        return known + sorted(self.roles - set(known))

    @property
    def default_role(self) -> str | None:
        """El rol de mayor privilegio: con el que abre la app (CU-35)."""
        ordered = self.ordered_roles
        return ordered[0] if ordered else None


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
        user, is_new = await self._find_or_provision(identity)
        if not user.active:
            raise ForbiddenError("The account is deactivated.", code="ACCOUNT_DEACTIVATED")
        user_id = require_id(user)
        roles = await self._users.get_role_codes(user_id)
        return CurrentUser(
            id=user_id,
            full_name=user.full_name,
            email=user.email,
            roles=roles,
            identity_provider=user.identity_provider,
            identity_subject=user.identity_subject,
            is_new_user=is_new,
            second_factor=identity.second_factor,
        )

    async def _find_or_provision(self, identity: ExternalIdentity) -> tuple[User, bool]:
        linked = await self._users.get_by_identity(self._provider, identity.subject)
        if linked is not None:
            return linked, False

        if not identity.email or not identity.email_verified:
            raise ForbiddenError(
                "The identity provider has not verified the email of this account.",
                code="EMAIL_NOT_VERIFIED",
            )

        # Enlazar a un usuario existente (p. ej. el administrador sembrado o uno creado a mano).
        by_email = await self._users.link_identity_by_email(
            identity.email, self._provider, identity.subject
        )
        if by_email is not None:
            await self._uow.commit()
            return by_email, False

        created = await self._users.create_if_absent(
            User(
                full_name=identity.full_name or identity.email.split("@")[0],
                email=identity.email,
                identity_provider=self._provider,
                identity_subject=identity.subject,
            )
        )
        if created is not None:
            learner = await self._roles.get_by_code(RoleCode.LEARNER)
            if learner is None:
                raise RuntimeError("The learner role is missing: run the Liquibase changelog.")
            await self._user_roles.assign_if_absent(require_id(created), require_id(learner))
            await self._uow.commit()
            return created, True

        # Otra petición se adelantó (creó o enlazó al mismo usuario): se vuelve a leer.
        await self._uow.commit()  # cierra la transacción para ver lo que ya confirmó la otra
        concurrent = await self._users.get_by_identity(self._provider, identity.subject)
        if concurrent is not None:
            return concurrent, False
        if await self._users.get_by_email(identity.email) is not None:
            raise ConflictError(
                "This email already belongs to a user linked to another identity.",
                code="IDENTITY_ALREADY_LINKED",
            )
        raise ConflictError("The user could not be created; retry the request.")
