"""Interfaces (puertos) de los repositorios de identidad."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.identity.entities import (
    Consent,
    DataSubjectRequest,
    Role,
    User,
    UserProfile,
    UserRole,
)


class RoleRepository(CrudRepository[Role], Protocol):
    async def get_by_code(self, code: str) -> Role | None: ...

    async def list_by_codes(self, codes: list[str]) -> list[Role]:
        """Roles activos con esos códigos (los que no existan simplemente no vienen)."""
        ...


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

    async def link_identity_by_email(self, email: str, provider: str, subject: str) -> User | None:
        """Enlaza de forma atómica al usuario con ese correo que aún no tiene identidad.

        Devuelve `None` si no existe o si ya estaba enlazado (a esta u otra identidad).
        """
        ...

    async def create_if_absent(self, user: User) -> User | None:
        """Inserta el usuario; devuelve `None` si ya existía uno con ese correo o identidad.

        Es la pieza que hace seguro el primer ingreso ante dos llamadas simultáneas
        (`INSERT ... ON CONFLICT DO NOTHING`).
        """
        ...

    async def count_active_admins(self, *, excluding_user_id: int | None = None) -> int:
        """Usuarios activos con el rol `admin` activo, sin contar al indicado."""
        ...

    async def lock_admin_membership(self) -> None:
        """Serializa los cambios que pueden dejar la plataforma sin administrador."""
        ...


class UserRoleRepository(CrudRepository[UserRole], Protocol):
    async def assign_if_absent(self, user_id: int, role_id: int) -> None:
        """Asigna el rol sin fallar si ya estaba (activa la asignación si estaba inactiva)."""
        ...

    async def list_for_user(self, user_id: int) -> list[UserRole]:
        """Todas las asignaciones del usuario, activas o no."""
        ...


class ProfileRepository(Protocol):
    async def get_by_user_id(self, user_id: int) -> UserProfile | None: ...

    async def save(self, profile: UserProfile) -> UserProfile:
        """Crea o actualiza el perfil del usuario (uno por usuario)."""
        ...


class ConsentRepository(Protocol):
    async def add(self, consent: Consent) -> Consent: ...

    async def list_for_user(self, user_id: int) -> list[Consent]:
        """Todas las autorizaciones del usuario, de la más antigua a la más reciente."""
        ...

    async def latest(self, user_id: int, consent_type: str) -> Consent | None:
        """La autorización más reciente de ese tipo (vigente o revocada)."""
        ...

    async def revoke(self, consent_id: int) -> Consent | None: ...


class DataSubjectRequestRepository(Protocol):
    async def add(self, request: DataSubjectRequest) -> DataSubjectRequest: ...
