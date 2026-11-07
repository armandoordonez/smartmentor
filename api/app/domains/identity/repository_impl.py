"""Repositorios SQLAlchemy de identidad."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.common.entities import require_id
from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.identity.entities import (
    Consent,
    DataSubjectRequest,
    Role,
    User,
    UserProfile,
    UserRole,
)
from app.domains.identity.models import (
    ConsentModel,
    DataSubjectRequestModel,
    RoleModel,
    UserModel,
    UserProfileModel,
    UserRoleModel,
)


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

    async def list_by_codes(self, codes: list[str]) -> list[Role]:
        rows = (
            (
                await self._session.execute(
                    select(RoleModel).where(RoleModel.code.in_(codes), RoleModel.active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


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

    async def link_identity_by_email(self, email: str, provider: str, subject: str) -> User | None:
        # Una sola sentencia: dos peticiones simultáneas no pueden enlazar al mismo usuario dos
        # veces (la segunda espera el bloqueo de fila y ya no cumple `identity_subject IS NULL`).
        row = (
            await self._session.execute(
                update(UserModel)
                .where(func.lower(UserModel.email) == email.lower())
                .where(UserModel.identity_subject.is_(None))
                .values(identity_provider=provider, identity_subject=subject)
                .returning(UserModel)
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def create_if_absent(self, user: User) -> User | None:
        row = (
            await self._session.execute(
                pg_insert(UserModel)
                .values(
                    full_name=user.full_name,
                    email=user.email,
                    identity_provider=user.identity_provider,
                    identity_subject=user.identity_subject,
                )
                .on_conflict_do_nothing()
                .returning(UserModel)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def count_active_admins(self, *, excluding_user_id: int | None = None) -> int:
        query = (
            select(func.count(func.distinct(UserModel.id)))
            .select_from(UserModel)
            .join(UserRoleModel, UserRoleModel.user_id == UserModel.id)
            .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            .where(
                RoleModel.code == "admin",
                RoleModel.active.is_(True),
                UserRoleModel.active.is_(True),
                UserModel.active.is_(True),
            )
        )
        if excluding_user_id is not None:
            query = query.where(UserModel.id != excluding_user_id)
        return int((await self._session.execute(query)).scalar_one())

    async def lock_admin_membership(self) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('smartmentor.admin_membership'))")
        )


class SqlAlchemyUserRoleRepository(SqlAlchemyCrudRepository[UserRoleModel, UserRole]):
    model = UserRoleModel
    entity = UserRole
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "user_roles_user_role_uq": ("ROLE_ALREADY_ASSIGNED", "The user already has this role."),
        "user_roles_user_id_fk": ("USER_NOT_FOUND", "The user does not exist."),
        "user_roles_role_id_fk": ("ROLE_NOT_FOUND", "The role does not exist."),
    }

    async def assign_if_absent(self, user_id: int, role_id: int) -> None:
        statement = pg_insert(UserRoleModel).values(user_id=user_id, role_id=role_id)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id", "role_id"], set_={"active": True}
            )
        )

    async def list_for_user(self, user_id: int) -> list[UserRole]:
        rows = (
            (
                await self._session.execute(
                    select(UserRoleModel)
                    .where(UserRoleModel.user_id == user_id)
                    .order_by(UserRoleModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyProfileRepository(SqlAlchemyCrudRepository[UserProfileModel, UserProfile]):
    model = UserProfileModel
    entity = UserProfile
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "user_profiles_user_id_uq": ("CONFLICT", "The user already has a profile."),
    }

    async def get_by_user_id(self, user_id: int) -> UserProfile | None:
        row = (
            await self._session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def save(self, profile: UserProfile) -> UserProfile:
        current = await self.get_by_user_id(profile.user_id)
        if current is None:
            return await self.add(profile)
        changes = {
            key: value
            for key, value in asdict(profile).items()
            if key not in ("id", "user_id", "active", "created_at", "updated_at")
        }
        updated = await self.update(require_id(current), changes)
        if updated is None:
            raise RuntimeError("The profile disappeared during the update.")
        return updated


class SqlAlchemyConsentRepository(SqlAlchemyCrudRepository[ConsentModel, Consent]):
    model = ConsentModel
    entity = Consent

    async def list_for_user(self, user_id: int) -> list[Consent]:
        rows = (
            (
                await self._session.execute(
                    select(ConsentModel)
                    .where(ConsentModel.user_id == user_id)
                    .order_by(ConsentModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]

    async def latest(self, user_id: int, consent_type: str) -> Consent | None:
        row = (
            (
                await self._session.execute(
                    select(ConsentModel)
                    .where(
                        ConsentModel.user_id == user_id,
                        ConsentModel.consent_type == consent_type,
                    )
                    .order_by(ConsentModel.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def revoke(self, consent_id: int) -> Consent | None:
        return await self.update(consent_id, {"revoked_at": datetime.now(UTC)})


class SqlAlchemyDataSubjectRequestRepository(
    SqlAlchemyCrudRepository[DataSubjectRequestModel, DataSubjectRequest]
):
    model = DataSubjectRequestModel
    entity = DataSubjectRequest
