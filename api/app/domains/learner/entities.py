"""Entidades del aprendiz que no pertenecen a la ruta ni a las evaluaciones: encuesta y eventos."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class SurveyResponse(BaseEntity):
    enrollment_id: int
    survey_type: str = "final"
    likert: dict[str, Any] | None = None
    sus_items: list[int] | None = None
    sus_score: float | None = None
    comment: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class InteractionEvent:
    """Evento de uso para el «tiempo en tarea» del brief (`interaction_events`, solo se agrega)."""

    enrollment_id: int
    event_type: str
    occurred_at: datetime
    topic_id: int | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class StudyGoals:
    """Metas personales (E11, CU-23, P2) con el avance del día y del mes."""

    daily_minutes_goal: int
    monthly_topics_goal: int
    daily_minutes_done: int = 0
    monthly_topics_done: int = 0
    streak_days: int = 0
