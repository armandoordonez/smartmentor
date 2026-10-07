"""Puerto de la unidad de trabajo: el servicio decide el commit."""

from typing import Protocol


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...
