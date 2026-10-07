"""Repositorios en memoria para probar servicios sin base de datos."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from app.common.entities import BaseEntity


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class InMemoryRepository[E: BaseEntity]:
    def __init__(self, items: list[E] | None = None) -> None:
        self.items: dict[int, E] = {}
        self._next_id = 1
        for item in items or []:
            self._store(item)

    def _store(self, entity: E) -> E:
        stored = replace(entity, id=self._next_id) if entity.id is None else entity
        assert stored.id is not None
        self.items[stored.id] = stored
        self._next_id = max(self._next_id, stored.id) + 1
        return stored

    async def add(self, entity: E) -> E:
        return self._store(entity)

    async def get(self, entity_id: int) -> E | None:
        return self.items.get(entity_id)

    async def search(
        self, *, filters: Mapping[str, Any], active: bool | None, limit: int, offset: int
    ) -> tuple[list[E], int]:
        found = [
            e
            for e in self.items.values()
            if all(getattr(e, k) == v for k, v in filters.items())
            and (active is None or e.active == active)
        ]
        return found[offset : offset + limit], len(found)

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> E | None:
        current = self.items.get(entity_id)
        if current is None:
            return None
        self.items[entity_id] = replace(current, **changes)
        return self.items[entity_id]

    async def set_active(self, entity_id: int, active: bool) -> E | None:
        return await self.update(entity_id, {"active": active})
