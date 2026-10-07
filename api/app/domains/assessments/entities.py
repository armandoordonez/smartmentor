"""Entidades del dominio de evaluaciones (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Diagnostic(BaseEntity):
    enrollment_id: int
    questions: list[Any] = field(default_factory=list)
    answers: list[Any] | dict[str, Any] | None = None
    level_by_topic: dict[str, Any] | None = None
    completed_at: datetime | None = None


@dataclass(kw_only=True)
class AssessmentAttempt(BaseEntity):
    enrollment_id: int
    assessment_type: str
    path_step_id: int | None = None
    attempt_number: int = 1
    questions: list[Any] = field(default_factory=list)
    answers: list[Any] | dict[str, Any] | None = None
    score: float | None = None
    passed: bool | None = None
    submitted_at: datetime | None = None


@dataclass(kw_only=True)
class Badge(BaseEntity):
    enrollment_id: int
    issued_at: datetime | None = None
    image_url: str | None = None
    open_badges_metadata: dict[str, Any] | None = None
