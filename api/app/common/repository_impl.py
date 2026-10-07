"""Implementación SQLAlchemy del repositorio genérico y de la unidad de trabajo."""

from collections.abc import Mapping
from dataclasses import fields
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.entities import BaseEntity
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    DomainError,
    ReferenceNotFoundError,
)
from app.common.models import TableModel

# Códigos SQLSTATE de PostgreSQL
_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_NOT_NULL_VIOLATION = "23502"
_CHECK_VIOLATION = "23514"


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


def _plain(value: Any) -> Any:
    """Convierte tipos de la base (Decimal, arreglos de numpy) a tipos simples del dominio."""
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


class SqlAlchemyCrudRepository[M: TableModel, E: BaseEntity]:
    """Repositorio CRUD genérico. Cada dominio indica su modelo y su entidad.

    Nunca hace commit: solo flush. Los errores de integridad de PostgreSQL se traducen a
    errores de dominio para que la API no exponga mensajes de la base de datos.
    """

    model: type[M]
    entity: type[E]
    # nombre de la restricción -> (código, mensaje) para respuestas más claras
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {}

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, row: M) -> E:
        values = {f.name: _plain(getattr(row, f.name)) for f in fields(self.entity)}
        return self.entity(**values)

    def _translate(self, exc: IntegrityError) -> DomainError:
        origin = exc.orig
        cause = getattr(origin, "__cause__", None)
        sqlstate = getattr(origin, "sqlstate", None) or getattr(cause, "sqlstate", None)
        constraint = getattr(cause, "constraint_name", None) or getattr(
            origin, "constraint_name", None
        )
        code, message = self.constraint_messages.get(constraint or "", (None, None))
        if sqlstate == _UNIQUE_VIOLATION:
            return ConflictError(
                message or "A record with the same unique values already exists.", code=code
            )
        if sqlstate == _FOREIGN_KEY_VIOLATION:
            return ReferenceNotFoundError(
                message or "A referenced record does not exist.", code=code
            )
        if sqlstate in (_CHECK_VIOLATION, _NOT_NULL_VIOLATION):
            return BusinessRuleError(message or "The data violates a business rule.", code=code)
        return BusinessRuleError("The data could not be saved.", code=code)

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise self._translate(exc) from exc

    async def add(self, entity: E) -> E:
        # Los valores None se omiten: la base aplica su DEFAULT (p. ej. issued_at) o deja NULL.
        values = {
            f.name: getattr(entity, f.name)
            for f in fields(entity)
            if f.name not in ("id", "created_at") and getattr(entity, f.name) is not None
        }
        row = self.model(**values)
        self._session.add(row)
        await self._flush()
        return self._to_entity(row)

    async def get(self, entity_id: int) -> E | None:
        row = await self._session.get(self.model, entity_id)
        return None if row is None else self._to_entity(row)

    async def search(
        self,
        *,
        filters: Mapping[str, Any],
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[E], int]:
        conditions = [getattr(self.model, key) == value for key, value in filters.items()]
        if active is not None:
            conditions.append(self.model.active == active)
        total = (
            await self._session.execute(
                select(func.count()).select_from(self.model).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(self.model)
                    .where(*conditions)
                    .order_by(self.model.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows], total

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> E | None:
        row = await self._session.get(self.model, entity_id)
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value)
        await self._flush()
        return self._to_entity(row)

    async def set_active(self, entity_id: int, active: bool) -> E | None:
        return await self.update(entity_id, {"active": active})
