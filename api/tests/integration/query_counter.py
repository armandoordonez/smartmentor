"""Cuenta las sentencias SQL que llegan a la base durante un bloque (R-008, B-018).

Cada sentencia es un viaje de ida y vuelta a la base; contra Neon cada una cuesta ~110 ms, así que
el número de sentencias por petición es lo que más pesa en la latencia de la API.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class QueryLog:
    statements: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.statements)

    def describe(self) -> str:
        return "\n".join(
            f"{n:>3}. {s.splitlines()[0][:160]}" for n, s in enumerate(self.statements, 1)
        )


@contextmanager
def count_queries(engine: AsyncEngine) -> Iterator[QueryLog]:
    """Registra cada sentencia ejecutada por el motor mientras dura el bloque."""
    log = QueryLog()

    def _record(*args: Any) -> None:
        log.statements.append(str(args[2]))  # (conn, cursor, statement, params, context, many)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield log
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)
