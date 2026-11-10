"""Entidades del dominio de rutas: ruta, inscripción, paso, intentos extra y alertas (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity

# Pesos del nivel por defecto (C-02): fracciones que suman 1, como las espera `ai/`.
DEFAULT_LEVEL_WEIGHTS: dict[str, float] = {"test": 0.8, "profile": 0.1, "resume": 0.1}
# Proporción mínima de criterios para aprobar una respuesta corta (DEF-21: 2 de 3).
DEFAULT_SHORT_ANSWER_MIN_RATIO = 0.667


@dataclass(kw_only=True)
class LearningPath(BaseEntity):
    course_id: int
    name: str
    group_label: str | None = None
    status: str = "draft"
    default_objective_bloom_verb: str | None = None
    default_objective_content: str | None = None
    default_objective_criterion: str | None = None
    topic_pass_threshold: float = 70.0
    final_pass_threshold: float = 80.0
    mastery_skip_threshold: float = 80.0
    max_attempts: int = 3
    level_weights: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_LEVEL_WEIGHTS))
    short_answer_min_ratio: float = DEFAULT_SHORT_ANSWER_MIN_RATIO
    updated_at: datetime | None = None

    @property
    def weights(self) -> dict[str, float]:
        """Pesos como fracciones que suman 1 (la base los siembra en porcentaje: 80/10/10)."""
        raw = {k: float(self.level_weights.get(k, 0) or 0) for k in ("test", "profile", "resume")}
        total = sum(raw.values())
        if total <= 0:
            return dict(DEFAULT_LEVEL_WEIGHTS)
        return {k: round(v / total, 4) for k, v in raw.items()}

    @property
    def default_objective_parts(self) -> dict[str, str] | None:
        parts = {
            "bloom_verb": self.default_objective_bloom_verb,
            "content": self.default_objective_content,
            "criterion": self.default_objective_criterion,
        }
        if all(v and v.strip() for v in parts.values()):
            return {k: str(v) for k, v in parts.items()}
        return None


@dataclass(kw_only=True)
class Enrollment(BaseEntity):
    user_id: int
    learning_path_id: int
    status: str = "enrolled"
    profile_description: str | None = None
    profile_snapshot: dict[str, Any] | None = None
    objective_bloom_verb: str | None = None
    objective_content: str | None = None
    objective_criterion: str | None = None
    objective_origin: str | None = None
    pilot_arm: str | None = None
    analysis_included: bool = False
    completed_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class PathStep(BaseEntity):
    enrollment_id: int
    topic_id: int
    step_order: int
    status: str = "pending"
    inclusion_reason: str | None = None
    diagnostic_level: float | None = None
    attempts_used: int = 0
    extra_attempts_granted: int = 0
    best_score: float | None = None
    last_score: float | None = None
    updated_at: datetime | None = None

    def remaining_attempts(self, max_attempts: int) -> int:
        """Intentos que quedan: los de la regla más los extra (que se reportan aparte)."""
        return max(max_attempts + self.extra_attempts_granted - self.attempts_used, 0)


@dataclass(kw_only=True)
class AttemptGrant(BaseEntity):
    granted_by_user_id: int
    attempts: int
    path_step_id: int | None = None
    enrollment_id: int | None = None
    note: str | None = None


@dataclass(kw_only=True)
class Alert(BaseEntity):
    recipient_user_id: int
    alert_type: str
    enrollment_id: int | None = None
    path_step_id: int | None = None
    read_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class TopicNode:
    """Un tema del curso visto por la ruta: orden del syllabus, prerrequisitos y obligatoriedad."""

    id: int
    name: str
    position: int
    estimated_minutes: int | None
    is_mandatory: bool
    prerequisites: tuple[int, ...]
