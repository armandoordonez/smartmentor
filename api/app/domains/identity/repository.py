"""Interfaces (puertos) de los repositorios de identidad."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.identity.entities import Role, User, UserRole


class RoleRepository(CrudRepository[Role], Protocol):
    async def get_by_code(self, code: str) -> Role | None: ...


class UserRepository(CrudRepository[User], Protocol):
    async def get_by_identity(self, provider: str, subject: str) -> User | None:
        """Usuario enlazado a una identidad del proveedor (p. ej. el sub de Keycloak)."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Usuario con ese correo, sin distinguir mayúsculas."""
        ...

    async def get_role_codes(self, user_id: int) -> frozenset[str]:
        """Códigos de los roles activos asignados al usuario."""
        ...


class UserRoleRepository(CrudRepository[UserRole], Protocol): ...
