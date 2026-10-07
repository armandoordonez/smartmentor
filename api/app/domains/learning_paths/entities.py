"""Entidades del dominio de rutas de aprendizaje (Python puro)."""

from dataclasses import dataclass

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class LearningPath(BaseEntity):
    course_id: int
    name: str
    default_objective: str | None = None
    topic_pass_threshold: float = 70
    final_pass_threshold: float = 80
    mastery_skip_threshold: float = 80
    max_attempts: int = 3


@dataclass(kw_only=True)
class Enrollment(BaseEntity):
    user_id: int
    learning_path_id: int
    profile_description: str | None = None
    profile_embedding: list[float] | None = None
    personal_objective: str | None = None
    status: str = "enrolled"

    @property
    def has_profile_embedding(self) -> bool:
        return self.profile_embedding is not None


@dataclass(kw_only=True)
class PathStep(BaseEntity):
    enrollment_id: int
    topic_id: int
    step_order: int
    status: str = "pending"
    score: float | None = None
