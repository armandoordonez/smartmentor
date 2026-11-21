"""Entidad base del dominio (Python puro, sin FastAPI ni SQLAlchemy)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(kw_only=True)
class BaseEntity:
    """Campos comunes de toda tabla de negocio. id y created_at los asigna la base de datos."""

    id: int | None = None
    active: bool = True
    created_at: datetime | None = None


def require_id(entity: BaseEntity) -> int:
    """El id de una entidad ya persistida (la base lo asigna al insertar)."""
    if entity.id is None:
        raise RuntimeError(f"{type(entity).__name__} has not been persisted yet.")
    return entity.id
