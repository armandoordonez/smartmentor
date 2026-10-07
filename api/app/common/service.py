"""Servicio de aplicación base: casos de uso CRUD con borrado lógico.

El servicio define la transacción: hace commit cuando el caso de uso termina bien. Si algo falla
antes, la sesión se cierra sin commit y se hace rollback. No depende de FastAPI ni de SQLAlchemy.
"""

from collections.abc import Mapping
from typing import Any

from app.common.entities import BaseEntity
from app.common.exceptions import NotFoundError
from app.common.repository import CrudRepository
from app.common.unit_of_work import UnitOfWork


class CrudService[E: BaseEntity]:
    resource_name = "Resource"

    def __init__(self, repository: CrudRepository[E], uow: UnitOfWork) -> None:
        self._repository = repository
        self._uow = uow

    # --- ganchos para reglas de negocio de cada dominio -----------------------------------
    async def _validate_create(self, entity: E) -> None:
        """Reglas previas a crear. Lanza un DomainError si no se cumplen."""

    async def _validate_update(self, current: E, changes: Mapping[str, Any]) -> None:
        """Reglas previas a actualizar. Lanza un DomainError si no se cumplen."""

    # --- casos de uso ----------------------------------------------------------------------
    async def create(self, entity: E) -> E:
        await self._validate_create(entity)
        created = await self._repository.add(entity)
        await self._uow.commit()
        return created

    async def get(self, entity_id: int) -> E:
        entity = await self._repository.get(entity_id)
        if entity is None:
            raise NotFoundError(self.resource_name, entity_id)
        return entity

    async def search(
        self,
        *,
        filters: Mapping[str, Any],
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[E], int]:
        present = {key: value for key, value in filters.items() if value is not None}
        return await self._repository.search(
            filters=present, active=active, limit=limit, offset=offset
        )

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> E:
        current = await self.get(entity_id)
        if not changes:
            return current
        await self._validate_update(current, changes)
        updated = await self._repository.update(entity_id, changes)
        if updated is None:
            raise NotFoundError(self.resource_name, entity_id)
        await self._uow.commit()
        return updated

    async def deactivate(self, entity_id: int) -> E:
        return await self._set_active(entity_id, False)

    async def activate(self, entity_id: int) -> E:
        return await self._set_active(entity_id, True)

    async def _set_active(self, entity_id: int, active: bool) -> E:
        entity = await self._repository.set_active(entity_id, active)
        if entity is None:
            raise NotFoundError(self.resource_name, entity_id)
        await self._uow.commit()
        return entity
