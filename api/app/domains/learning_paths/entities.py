"""Entidad mínima de la ruta de aprendizaje (la completa llega con el dominio `learning_paths`)."""

from dataclasses import dataclass
from datetime import datetime

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class LearningPath(BaseEntity):
    course_id: int
    name: str
    group_label: str | None = None
    status: str = "draft"
    updated_at: datetime | None = None
