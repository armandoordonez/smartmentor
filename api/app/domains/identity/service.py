"""Casos de uso de identidad: roles, usuarios, perfil, autorizaciones y solicitudes de derechos."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from app.common.constants import (
    ConsentType,
    DataSubjectRequestType,
    EducationLevel,
    ExperienceBand,
    RoleCode,
)
from app.common.entities import require_id
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.common.service import CrudService
from app.common.unit_of_work import UnitOfWork
from app.domains.identity import labels
from app.domains.identity.authentication import CurrentUser
from app.domains.identity.entities import (
    Consent,
    DataSubjectRequest,
    Role,
    User,
    UserProfile,
    UserRole,
)
from app.domains.identity.repository import (
    ConsentRepository,
    DataSubjectRequestRepository,
    ProfileRepository,
    RoleRepository,
    UserRepository,
    UserRoleRepository,
)

logger = logging.getLogger("app.identity")


class RoleSyncPort(Protocol):
    """Refleja los roles de la base en el proveedor de identidad (DEF-27, G-03).

    La base manda. La implementación real llama a la API de administración de Keycloak (Fase 8);
    mientras tanto no hace nada.
    """

    async def sync_roles(self, identity_subject: str, roles: list[str]) -> None: ...


class NullRoleSync:
    async def sync_roles(
        self,
        identity_subject: str,  # noqa: ARG002
        roles: list[str],  # noqa: ARG002
    ) -> None:
        return None


class ProfileChangeListener(Protocol):
    """Recalcula niveles y pasos pendientes al cambiar el perfil con una ruta en curso (E15).

    Lo implementa el dominio `learning_paths` (agente posterior); devuelve las inscripciones
    recalculadas.
    """

    async def on_profile_changed(self, user_id: int) -> list[int]: ...


class NoRecalculation:
    async def on_profile_changed(self, user_id: int) -> list[int]:  # noqa: ARG002
        return []


class RoleService(CrudService[Role]):
    resource_name = "Role"


class _AdminGuard:
    """Regla CU-14: la plataforma nunca se queda sin administrador."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def ensure_another_admin(self, user_id: int) -> None:
        await self._users.lock_admin_membership()
        if await self._users.count_active_admins(excluding_user_id=user_id) == 0:
            raise ConflictError(
                "This change would leave the platform without an administrator.",
                code="LAST_ADMIN",
            )

    async def user_is_active_admin(self, user: User) -> bool:
        if not user.active:
            return False
        return RoleCode.ADMIN in await self._users.get_role_codes(require_id(user))


class UserService(CrudService[User]):
    resource_name = "User"

    def __init__(self, repository: UserRepository, uow: UnitOfWork) -> None:
        super().__init__(repository, uow)
        self._users = repository
        self._guard = _AdminGuard(repository)

    async def _validate_deactivate(self, current: User) -> None:
        if await self._guard.user_is_active_admin(current):
            await self._guard.ensure_another_admin(require_id(current))

    async def _validate_update(self, current: User, changes: Mapping[str, Any]) -> None:
        if changes.get("active") is False:
            await self._validate_deactivate(current)


class UserRoleService(CrudService[UserRole]):
    """CRUD de asignaciones: crear reactiva una asignación inactiva, inactivar protege al admin."""

    resource_name = "User role"

    def __init__(
        self,
        repository: UserRoleRepository,
        users: UserRepository,
        roles: RoleRepository,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repository, uow)
        self._user_roles = repository
        self._users = users
        self._roles = roles
        self._guard = _AdminGuard(users)

    async def create(self, entity: UserRole) -> UserRole:
        if await self._users.get(entity.user_id) is None:
            raise NotFoundError("User", entity.user_id, code="USER_NOT_FOUND")
        if await self._roles.get(entity.role_id) is None:
            raise NotFoundError("Role", entity.role_id, code="ROLE_NOT_FOUND")
        for existing in await self._user_roles.list_for_user(entity.user_id):
            if existing.role_id == entity.role_id:
                if existing.active:
                    raise ConflictError(
                        "The user already has this role.", code="ROLE_ALREADY_ASSIGNED"
                    )
                reactivated = await self._user_roles.set_active(require_id(existing), True)
                await self._uow.commit()
                if reactivated is None:
                    raise RuntimeError("The user role disappeared during the update.")
                return reactivated
        return await super().create(entity)

    async def _validate_deactivate(self, current: UserRole) -> None:
        role = await self._roles.get(current.role_id)
        user = await self._users.get(current.user_id)
        if (
            role is not None
            and role.code == RoleCode.ADMIN
            and user is not None
            and user.active
            and current.active
        ):
            await self._guard.ensure_another_admin(current.user_id)


class UserRolesAdminService:
    """`PUT /users/{id}/roles`: reemplaza el conjunto de roles de un usuario (CU-14).

    Cada cambio queda en la auditoría porque la base audita `user_roles` con el usuario que actúa.
    """

    def __init__(
        self,
        users: UserRepository,
        roles: RoleRepository,
        user_roles: UserRoleRepository,
        uow: UnitOfWork,
        sync: RoleSyncPort | None = None,
    ) -> None:
        self._users = users
        self._roles = roles
        self._user_roles = user_roles
        self._uow = uow
        self._sync = sync or NullRoleSync()
        self._guard = _AdminGuard(users)

    async def get_roles(self, user_id: int) -> list[str]:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id, code="USER_NOT_FOUND")
        return _ordered(await self._users.get_role_codes(user_id))

    async def set_roles(self, user_id: int, codes: list[str]) -> list[str]:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id, code="USER_NOT_FOUND")
        wanted = set(codes)
        found = {role.code: role for role in await self._roles.list_by_codes(sorted(wanted))}
        missing = sorted(wanted - found.keys())
        if missing:
            raise NotFoundError("Role", ", ".join(missing), code="ROLE_NOT_FOUND")

        current = await self._users.get_role_codes(user_id)
        if RoleCode.ADMIN in current and RoleCode.ADMIN not in wanted and user.active:
            await self._guard.ensure_another_admin(user_id)

        existing = {a.role_id: a for a in await self._user_roles.list_for_user(user_id)}
        by_id = {require_id(role): role for role in found.values()}
        for role_id in by_id:
            await self._user_roles.assign_if_absent(user_id, role_id)
        for role_id, assignment in existing.items():
            if role_id not in by_id and assignment.active:
                await self._user_roles.set_active(require_id(assignment), False)
        await self._uow.commit()

        result = _ordered(await self._users.get_role_codes(user_id))
        if user.identity_subject:
            try:
                await self._sync.sync_roles(user.identity_subject, result)
            except Exception:
                # La base manda: si Keycloak no responde, el cambio ya está hecho y se reintenta.
                logger.exception("could not mirror the roles in the identity provider")
        return result


def _ordered(codes: frozenset[str]) -> list[str]:
    known = [r.value for r in (RoleCode.ADMIN, RoleCode.INSTRUCTOR, RoleCode.LEARNER)]
    return [c for c in known if c in codes] + sorted(codes - set(known))


@dataclass(frozen=True)
class ProfileCompleteness:
    description: bool
    resume: bool

    @property
    def percent(self) -> int:
        return 50 * int(self.description) + 50 * int(self.resume)


def _resume_is_complete(profile: UserProfile) -> bool:
    return profile.education_level is not None and profile.experience_band is not None


class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        uow: UnitOfWork,
        listener: ProfileChangeListener | None = None,
    ) -> None:
        self._profiles = profiles
        self._uow = uow
        self._listener = listener or NoRecalculation()

    async def get(self, user_id: int) -> UserProfile:
        return await self._profiles.get_by_user_id(user_id) or UserProfile(user_id=user_id)

    async def completeness(self, user_id: int) -> ProfileCompleteness:
        profile = await self.get(user_id)
        return ProfileCompleteness(description=profile.has_description, resume=profile.has_resume)

    async def update(
        self, user_id: int, values: Mapping[str, Any]
    ) -> tuple[UserProfile, list[int]]:
        """Reemplaza la descripción y la hoja de vida; recalcula las rutas en curso (E15)."""
        for key, allowed in (
            ("education_level", EducationLevel),
            ("experience_band", ExperienceBand),
        ):
            value = values.get(key)
            if value is not None and value not in {item.value for item in allowed}:
                raise BusinessRuleError(f"{key} is not a valid value.", code="VALIDATION_ERROR")
        current = await self.get(user_id)
        draft = replace(
            current,
            description=values.get("description"),
            education_level=values.get("education_level"),
            qualification_title=values.get("qualification_title"),
            job_title=values.get("job_title"),
            experience_band=values.get("experience_band"),
            tools=list(values.get("tools") or []),
            languages=list(values.get("languages") or []),
        )
        if _resume_is_complete(draft):
            draft = replace(
                draft, resume_completed_at=current.resume_completed_at or datetime.now(UTC)
            )
        else:
            draft = replace(draft, resume_completed_at=None)
        saved = await self._profiles.save(draft)
        recalculated = await self._listener.on_profile_changed(user_id)
        await self._uow.commit()
        return saved, recalculated


class ConsentService:
    def __init__(self, consents: ConsentRepository, uow: UnitOfWork) -> None:
        self._consents = consents
        self._uow = uow

    async def list_consents(self, user_id: int) -> list[Consent]:
        return await self._consents.list_for_user(user_id)

    async def status(self, user_id: int) -> dict[str, Consent | None]:
        """La autorización más reciente de cada tipo (`None` si nunca se dio)."""
        return {t.value: await self._consents.latest(user_id, t.value) for t in ConsentType}

    async def has_data_processing(self, user_id: int) -> bool:
        latest = await self._consents.latest(user_id, ConsentType.DATA_PROCESSING)
        return latest is not None and latest.in_force

    async def grant(
        self, user_id: int, consent_type: ConsentType, document_version: str
    ) -> tuple[Consent, bool]:
        """Da la autorización. Devuelve `(consent, created)`: idempotente si ya está vigente."""
        latest = await self._consents.latest(user_id, consent_type)
        if latest is not None and latest.in_force and latest.document_version == document_version:
            return latest, False
        if latest is not None and latest.in_force:
            await self._consents.revoke(require_id(latest))  # nueva versión del documento
        created = await self._consents.add(
            Consent(user_id=user_id, consent_type=consent_type, document_version=document_version)
        )
        await self._uow.commit()
        return created, True

    async def revoke(self, user_id: int, consent_type: ConsentType) -> Consent:
        latest = await self._consents.latest(user_id, consent_type)
        if latest is None:
            raise NotFoundError("Consent", consent_type.value)
        if not latest.in_force:
            raise ConflictError("The consent is already revoked.", code="CONSENT_ALREADY_REVOKED")
        revoked = await self._consents.revoke(require_id(latest))
        await self._uow.commit()
        if revoked is None:
            raise RuntimeError("The consent disappeared during the update.")
        return revoked


class DataSubjectRequestService:
    def __init__(self, requests: DataSubjectRequestRepository, uow: UnitOfWork) -> None:
        self._requests = requests
        self._uow = uow

    async def create(
        self, user_id: int, request_type: DataSubjectRequestType, comment: str | None
    ) -> DataSubjectRequest:
        created = await self._requests.add(
            DataSubjectRequest(user_id=user_id, request_type=request_type, details=comment)
        )
        await self._uow.commit()
        return created


@dataclass(frozen=True)
class MeView:
    """Todo lo que `GET /me` devuelve, ya calculado (la capa HTTP solo lo serializa)."""

    user: CurrentUser
    role_labels: dict[str, str]
    role_short_labels: dict[str, str]
    consents: dict[str, Consent | None]
    requires_consent: bool
    completeness: ProfileCompleteness


class MeService:
    def __init__(self, profiles: ProfileService, consents: ConsentService, *, context: str) -> None:
        self._profiles = profiles
        self._consents = consents
        self._context = context

    async def view(self, user: CurrentUser) -> MeView:
        consents = await self._consents.status(user.id)
        data_processing = consents[ConsentType.DATA_PROCESSING]
        return MeView(
            user=user,
            role_labels=labels.role_labels(self._context),
            role_short_labels=labels.role_short_labels(self._context),
            consents=consents,
            requires_consent=data_processing is None or not data_processing.in_force,
            completeness=await self._profiles.completeness(user.id),
        )
