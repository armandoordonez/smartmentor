"""Administración de las solicitudes de derechos del titular (ADR 0018, CU-17, E11b).

El aprendiz crea la solicitud (`POST /me/data-subject-requests`); aquí el administrador la lista y
resuelve. Resolver una **supresión** (`deletion`) es: seudonimizar al titular (nombre, correo,
identidad, perfil, hoja de vida, textos libres), revocar sus autorizaciones y desactivar sus roles,
y **purgar sus filas de `_audit`** con el procedimiento de la base `purge_user_audit(bigint)`.

Ese procedimiento lo debe crear un changeset de Liquibase con permiso explícito sobre las tablas
`_audit` (ADR 0019); mientras no exista, la supresión se rechaza con `503` sin tocar nada, porque
seudonimizar sin purgar dejaría el correo y el nombre en `<tabla>_audit`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Protocol

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN
from app.common.constants import DataSubjectRequestStatus, DataSubjectRequestType
from app.common.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.common.schemas import Page, RequestSchema, UtcDatetime
from app.common.unit_of_work import UnitOfWork
from app.core.database import SessionDep
from app.domains.identity.authentication import CurrentUser
from app.domains.identity.entities import DataSubjectRequest
from app.domains.identity.models import DataSubjectRequestModel

PURGE_FUNCTION = "purge_user_audit(bigint)"
_FINAL = frozenset({DataSubjectRequestStatus.RESOLVED, DataSubjectRequestStatus.REJECTED})
_NEXT: dict[str, frozenset[str]] = {
    DataSubjectRequestStatus.PENDING: frozenset(
        {
            DataSubjectRequestStatus.IN_PROGRESS,
            DataSubjectRequestStatus.RESOLVED,
            DataSubjectRequestStatus.REJECTED,
        }
    ),
    DataSubjectRequestStatus.IN_PROGRESS: _FINAL,
}


class DataSubjectStore(Protocol):
    async def search(
        self, *, status: str | None, request_type: str | None, limit: int, offset: int
    ) -> tuple[list[DataSubjectRequest], int]: ...

    async def get_for_update(self, request_id: int) -> DataSubjectRequest | None: ...

    async def update(self, request_id: int, changes: dict[str, Any]) -> DataSubjectRequest: ...

    async def purge_available(self) -> bool: ...

    async def pseudonymize(self, user_id: int) -> None: ...

    async def purge_audit(self, user_id: int) -> None: ...


@dataclass(frozen=True)
class Erasure:
    pseudonymized: bool
    audit_purged: bool
    identity_provider_action_required: bool


@dataclass(frozen=True)
class Resolution:
    request: DataSubjectRequest
    erasure: Erasure | None


class DataSubjectAdminService:
    def __init__(self, store: DataSubjectStore, uow: UnitOfWork) -> None:
        self._store = store
        self._uow = uow

    async def list_requests(
        self, *, status: str | None, request_type: str | None, limit: int, offset: int
    ) -> tuple[list[DataSubjectRequest], int]:
        return await self._store.search(
            status=status, request_type=request_type, limit=limit, offset=offset
        )

    async def update_status(
        self, admin: CurrentUser, request_id: int, status: str, note: str | None
    ) -> Resolution:
        request = await self._store.get_for_update(request_id)
        if request is None or not request.active:
            raise NotFoundError("Data subject request", request_id, code="NOT_FOUND")
        if status not in _NEXT.get(request.status, frozenset()):
            raise InvalidStateTransitionError(
                f"A request that is {request.status} cannot become {status}."
            )
        erasure: Erasure | None = None
        if (
            status == DataSubjectRequestStatus.RESOLVED
            and request.request_type == DataSubjectRequestType.DELETION
        ):
            erasure = await self._erase(admin, request)
        changes: dict[str, Any] = {"status": status}
        if status in _FINAL:
            changes.update(resolved_at=datetime.now(UTC), resolved_by_user_id=admin.id)
        if note is not None:
            changes["details"] = None if erasure else note
        updated = await self._store.update(request_id, changes)
        await self._uow.commit()
        return Resolution(updated, erasure)

    async def _erase(self, admin: CurrentUser, request: DataSubjectRequest) -> Erasure:
        if request.user_id == admin.id:
            raise ConflictError("An administrator cannot erase their own account.")
        if not await self._store.purge_available():
            # Nada cambia: seudonimizar sin purgar `_audit` dejaría los datos en la auditoría.
            raise ServiceUnavailableError(
                "The audit purge procedure purge_user_audit(bigint) is not installed; "
                "the erasure cannot be completed (ADR 0018)."
            )
        await self._store.pseudonymize(request.user_id)
        await self._store.purge_audit(request.user_id)
        return Erasure(
            pseudonymized=True, audit_purged=True, identity_provider_action_required=True
        )


# Seudonimización: tablas del titular y de sus inscripciones. Los textos libres se vacían; las filas
# de negocio que sostienen las métricas (intentos, notas, inscripciones) se conservan.
_PSEUDONYMIZE = (
    "UPDATE users SET full_name = 'Usuario eliminado', "
    "email = 'deleted-' || public_id || '@deleted.invalid', identity_provider = NULL, "
    "identity_subject = NULL, active = false WHERE id = :u",
    "UPDATE user_profiles SET description = NULL, education_level = NULL, "
    "qualification_title = NULL, job_title = NULL, experience_band = NULL, "
    "tools = '[]'::jsonb, languages = '[]'::jsonb, resume_completed_at = NULL WHERE user_id = :u",
    "UPDATE consents SET revoked_at = now() WHERE user_id = :u AND revoked_at IS NULL",
    "UPDATE user_roles SET active = false WHERE user_id = :u AND active",
    "UPDATE data_subject_requests SET details = NULL WHERE user_id = :u",
    "UPDATE enrollments SET profile_description = NULL, profile_snapshot = NULL WHERE user_id = :u",
    "UPDATE survey_responses SET comment = NULL WHERE enrollment_id IN "
    "(SELECT id FROM enrollments WHERE user_id = :u)",
    "UPDATE video_feedback SET comment = NULL WHERE enrollment_id IN "
    "(SELECT id FROM enrollments WHERE user_id = :u)",
)


def _entity(row: DataSubjectRequestModel) -> DataSubjectRequest:
    return DataSubjectRequest(
        id=row.id,
        active=row.active,
        created_at=row.created_at,
        user_id=row.user_id,
        request_type=row.request_type,
        status=row.status,
        details=row.details,
        resolved_at=row.resolved_at,
        resolved_by_user_id=row.resolved_by_user_id,
        updated_at=row.updated_at,
    )


class SqlAlchemyDataSubjectStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self, *, status: str | None, request_type: str | None, limit: int, offset: int
    ) -> tuple[list[DataSubjectRequest], int]:
        conditions: list[Any] = [DataSubjectRequestModel.active.is_(True)]
        if status:
            conditions.append(DataSubjectRequestModel.status == status)
        if request_type:
            conditions.append(DataSubjectRequestModel.request_type == request_type)
        total = (
            await self._session.execute(
                select(func.count()).select_from(DataSubjectRequestModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(DataSubjectRequestModel)
                    .where(*conditions)
                    .order_by(DataSubjectRequestModel.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [_entity(r) for r in rows], int(total)

    async def get_for_update(self, request_id: int) -> DataSubjectRequest | None:
        row = (
            await self._session.execute(
                select(DataSubjectRequestModel)
                .where(DataSubjectRequestModel.id == request_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else _entity(row)

    async def update(self, request_id: int, changes: dict[str, Any]) -> DataSubjectRequest:
        row = await self._session.get(DataSubjectRequestModel, request_id)
        if row is None:
            raise NotFoundError("Data subject request", request_id, code="NOT_FOUND")
        for key, value in changes.items():
            setattr(row, key, value)
        await self._session.flush()
        return _entity(row)

    async def purge_available(self) -> bool:
        found = (
            await self._session.execute(
                text("SELECT to_regprocedure(:name) IS NOT NULL"), {"name": PURGE_FUNCTION}
            )
        ).scalar_one()
        return bool(found)

    async def pseudonymize(self, user_id: int) -> None:
        for statement in _PSEUDONYMIZE:
            await self._session.execute(text(statement), {"u": user_id})

    async def purge_audit(self, user_id: int) -> None:
        await self._session.execute(text("SELECT purge_user_audit(:u)"), {"u": user_id})


# --- HTTP -------------------------------------------------------------------------------------


class DataSubjectRequestAdminResponse(BaseModel):
    id: int
    user_id: int
    request_type: str
    status: str
    details: str | None
    created_at: UtcDatetime | None
    resolved_at: UtcDatetime | None
    resolved_by_user_id: int | None


class ErasureResponse(BaseModel):
    pseudonymized: bool
    audit_purged: bool
    identity_provider_action_required: bool


class DataSubjectRequestResolved(DataSubjectRequestAdminResponse):
    erasure: ErasureResponse | None


class DataSubjectRequestUpdate(RequestSchema):
    status: Literal["in_progress", "resolved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


def get_data_subject_admin_service(session: SessionDep) -> DataSubjectAdminService:
    return DataSubjectAdminService(
        SqlAlchemyDataSubjectStore(session), SqlAlchemyUnitOfWork(session)
    )


AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN))]
AdminServiceDep = Annotated[DataSubjectAdminService, Depends(get_data_subject_admin_service)]


def _response(request: DataSubjectRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "user_id": request.user_id,
        "request_type": request.request_type,
        "status": request.status,
        "details": request.details,
        "created_at": request.created_at,
        "resolved_at": request.resolved_at,
        "resolved_by_user_id": request.resolved_by_user_id,
    }


router = APIRouter(tags=["data-subject-requests"])


@router.get("/data-subject-requests", response_model=Page[DataSubjectRequestAdminResponse])
async def list_data_subject_requests(
    _admin: AdminUser,
    service: AdminServiceDep,
    status: Annotated[
        str | None, Query(pattern="^(pending|in_progress|resolved|rejected)$")
    ] = None,
    request_type: Annotated[str | None, Query(pattern="^(deletion|access|rectification)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DataSubjectRequestAdminResponse]:
    found, total = await service.list_requests(
        status=status, request_type=request_type, limit=limit, offset=offset
    )
    return Page[DataSubjectRequestAdminResponse](
        items=[DataSubjectRequestAdminResponse(**_response(r)) for r in found],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/data-subject-requests/{request_id}", response_model=DataSubjectRequestResolved)
async def resolve_data_subject_request(
    request_id: int, payload: DataSubjectRequestUpdate, admin: AdminUser, service: AdminServiceDep
) -> DataSubjectRequestResolved:
    """Pasa la solicitud a `in_progress`, `resolved` o `rejected`.

    Resolver una supresión seudonimiza al titular y purga su `_audit`; exige que la base tenga el
    procedimiento `purge_user_audit(bigint)` (si no, `503` y no cambia nada).
    """
    result = await service.update_status(admin, request_id, payload.status, payload.note)
    erasure = result.erasure
    return DataSubjectRequestResolved(
        **_response(result.request),
        erasure=(
            ErasureResponse(
                pseudonymized=erasure.pseudonymized,
                audit_purged=erasure.audit_purged,
                identity_provider_action_required=erasure.identity_provider_action_required,
            )
            if erasure
            else None
        ),
    )


routers: list[APIRouter] = [router]
