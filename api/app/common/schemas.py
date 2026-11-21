"""Esquemas HTTP comunes: respuesta base, paginación y fechas en UTC."""

from datetime import UTC, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _to_utc_iso(value: datetime) -> str:
    """ISO 8601 en UTC con sufijo Z (2026-11-07T14:02:11Z): la app muestra en America/Bogota."""
    moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=str, when_used="json")]


class RequestSchema(BaseModel):
    """Base de los cuerpos de entrada: rechaza campos desconocidos (id, active, created_at...)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseSchema(BaseModel):
    """Base de las respuestas: se construye desde las entidades del dominio."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    created_at: UtcDatetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 (pydantic resuelve mejor Generic[T] al parametrizar en ejecución)
    items: list[T]
    total: int
    limit: int
    offset: int
