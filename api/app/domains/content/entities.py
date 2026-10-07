"""Entidades del dominio de contenido (Python puro)."""

from dataclasses import dataclass
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Resource(BaseEntity):
    topic_id: int
    resource_type: str
    url: str | None = None
    content: str | None = None
    sources: list[Any] | None = None
    prompt_version: str | None = None
