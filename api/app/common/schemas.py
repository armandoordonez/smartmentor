"""Esquemas HTTP comunes: respuesta base, paginación y fechas en la zona de la aplicación."""

from datetime import datetime
from typing import Annotated, Generic, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app.core.config import get_settings


def _to_local_iso(value: datetime) -> str:
    """ISO-8601 con el desfase de la zona horaria de la aplicación (2026-10-07T09:30:00-05:00)."""
    return value.astimezone(ZoneInfo(get_settings().app_timezone)).isoformat()


LocalDatetime = Annotated[
    datetime, PlainSerializer(_to_local_iso, return_type=str, when_used="json")
]


class RequestSchema(BaseModel):
    """Base de los cuerpos de entrada: rechaza campos desconocidos (id, active, created_at...)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseSchema(BaseModel):
    """Base de las respuestas: se construye desde las entidades del dominio."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    created_at: LocalDatetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 (pydantic resuelve mejor Generic[T] al parametrizar en ejecución)
    items: list[T]
    total: int
    limit: int
    offset: int
