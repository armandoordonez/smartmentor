"""Entidades del piloto (Python puro)."""

from dataclasses import dataclass, field
from datetime import date, datetime

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Pilot(BaseEntity):
    learning_path_id: int
    starts_on: date
    ends_on: date
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
class PathSummary:
    """Lo que AD4 y AD4b muestran de la ruta del piloto sin otra llamada (aditivo, 2026-11-12)."""

    name: str
    group_label: str | None
    final_pass_threshold: float


@dataclass(frozen=True)
class ContentFacts:
    """Lo que la ruta tiene listo para abrirse al piloto (insumo de `readiness`)."""

    topic_ids: list[int] = field(default_factory=list)
    topics_without_explanation: list[int] = field(default_factory=list)
    topics_without_items: list[int] = field(default_factory=list)
    topics_without_video: list[int] = field(default_factory=list)
    topics_without_backup: list[int] = field(default_factory=list)
    topics_without_equivalents: list[int] = field(default_factory=list)
    """Temas sin un `equivalence_group` con dos o más versiones paralelas (final y retención),
    necesarias para comparar la ganancia de Hake (docs/evaluation/metrics.md)."""
    approved_diagnostic_items: int = 0
    approved_final_items: int = 0
