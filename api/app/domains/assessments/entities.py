"""Entidades del dominio de evaluaciones: banco, diagnóstico, intentos, respuestas y badge."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class AssessmentItem(BaseEntity):
    topic_id: int
    source: str
    item_type: str
    bloom_level: str
    difficulty: int
    stem: str
    learning_outcome_id: int | None = None
    options: list[str] | None = None
    correct_option: str | None = None  # índice 0..3 como texto (columna varchar)
    model_answer: str | None = None
    rubric: list[dict[str, Any]] | None = None
    equivalence_group: str | None = None
    review_status: str = "pending_review"
    auto_review: dict[str, Any] | None = None
    prompt_version: str | None = None
    ai_job_id: int | None = None
    updated_at: datetime | None = None

    @property
    def correct_index(self) -> int | None:
        if self.correct_option is None or not str(self.correct_option).strip().isdigit():
            return None
        return int(self.correct_option)


@dataclass(kw_only=True)
class Diagnostic(BaseEntity):
    enrollment_id: int
    status: str = "created"
    item_ids: list[int] | None = None
    answers: dict[str, Any] | None = None
    level_by_topic: dict[str, Any] | None = None
    submitted_at: datetime | None = None
    scored_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class AssessmentAttempt(BaseEntity):
    enrollment_id: int
    assessment_type: str
    attempt_number: int
    path_step_id: int | None = None
    status: str = "created"
    item_ids: list[int] | None = None
    uses_extra_grant: bool = False
    score: float | None = None
    passed: bool | None = None
    submitted_at: datetime | None = None
    graded_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class AttemptAnswer(BaseEntity):
    assessment_attempt_id: int
    assessment_item_id: int
    selected_option: str | None = None
    dont_know: bool = False
    text_answer: str | None = None
    is_correct: bool | None = None
    score: float | None = None
    grader: str | None = None
    rubric_detail: dict[str, Any] | None = None  # `grading.v1` sin `meta`
    feedback: str | None = None
    review_requested_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def selected_index(self) -> int | None:
        if self.selected_option is None or not self.selected_option.isdigit():
            return None
        return int(self.selected_option)


@dataclass(kw_only=True)
class Badge(BaseEntity):
    enrollment_id: int
    public_id: UUID | None = None
    issued_at: datetime | None = None
    image_url: str | None = None
    image_path: str | None = None
    open_badges_metadata: dict[str, Any] | None = None
    updated_at: datetime | None = None
