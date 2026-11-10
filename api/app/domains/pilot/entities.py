"""Entidades del piloto (Python puro)."""

from dataclasses import dataclass, field
from datetime import date, datetime

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Pilot(BaseEntity):
    learning_path_id: int
    starts_on: date | None = None
    ends_on: date | None = None
    delayed_posttest_on: date | None = None
    random_seed: int | None = None
    status: str = "draft"
    updated_at: datetime | None = None


@dataclass(frozen=True)
class PilotEnrollment:
    """Una inscripción de la ruta del piloto y si su dueño aceptó `pilot_research`."""

    enrollment_id: int
    user_id: int
    consented: bool
    pilot_arm: str | None = None


@dataclass(frozen=True)
class ContentFacts:
    """Lo que la ruta tiene listo para abrirse al piloto (insumo de `readiness`)."""

    topic_ids: list[int] = field(default_factory=list)
    topics_without_explanation: list[int] = field(default_factory=list)
    topics_without_items: list[int] = field(default_factory=list)
    topics_without_video: list[int] = field(default_factory=list)
    topics_without_backup: list[int] = field(default_factory=list)
    approved_diagnostic_items: int = 0
    approved_final_items: int = 0
