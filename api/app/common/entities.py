"""Entidad base del dominio (Python puro, sin FastAPI ni SQLAlchemy)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(kw_only=True)
class BaseEntity:
    """Campos comunes de toda tabla de negocio. id y created_at los asigna la base de datos."""

    id: int | None = None
    active: bool = True
    created_at: datetime | None = None
