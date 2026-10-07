"""Interfaz genérica de repositorio (puerto). La implementa la infraestructura."""

from collections.abc import Mapping
from typing import Any, Protocol

from app.common.entities import BaseEntity


class CrudRepository[E: BaseEntity](Protocol):
    async def add(self, entity: E) -> E: ...

    async def get(self, entity_id: int) -> E | None: ...

    async def search(
        self,
        *,
        filters: Mapping[str, Any],
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[E], int]: ...

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> E | None: ...

    async def set_active(self, entity_id: int, active: bool) -> E | None: ...
