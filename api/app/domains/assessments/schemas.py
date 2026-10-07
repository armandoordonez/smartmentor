"""Contratos HTTP de evaluaciones."""

from typing import Any, Self

from pydantic import AwareDatetime, Field, model_validator

from app.common.constants import AssessmentType
from app.common.schemas import LocalDatetime, RequestSchema, ResponseSchema


class DiagnosticCreate(RequestSchema):
    enrollment_id: int = Field(gt=0)
    questions: list[Any] = Field(default_factory=list)
    answers: list[Any] | dict[str, Any] | None = None
    level_by_topic: dict[str, Any] | None = None
    completed_at: AwareDatetime | None = None


class DiagnosticUpdate(RequestSchema):
    questions: list[Any] | None = None
    answers: list[Any] | dict[str, Any] | None = None
    level_by_topic: dict[str, Any] | None = None
    completed_at: AwareDatetime | None = None


class DiagnosticResponse(ResponseSchema):
    enrollment_id: int
    questions: list[Any]
    answers: list[Any] | dict[str, Any] | None
    level_by_topic: dict[str, Any] | None
    completed_at: LocalDatetime | None


class AssessmentAttemptCreate(RequestSchema):
    """attempt_number y passed los calcula la API a partir de los umbrales de la ruta."""

    enrollment_id: int = Field(gt=0)
    assessment_type: AssessmentType
    path_step_id: int | None = Field(default=None, gt=0)
    questions: list[Any] = Field(default_factory=list)
    answers: list[Any] | dict[str, Any] | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    submitted_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def step_matches_type(self) -> Self:
        if self.assessment_type == AssessmentType.TOPIC and self.path_step_id is None:
            raise ValueError("a topic assessment needs a path_step_id")
        if self.assessment_type == AssessmentType.FINAL and self.path_step_id is not None:
            raise ValueError("a final assessment cannot have a path_step_id")
        return self


class AssessmentAttemptUpdate(RequestSchema):
    answers: list[Any] | dict[str, Any] | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    submitted_at: AwareDatetime | None = None


class AssessmentAttemptResponse(ResponseSchema):
    enrollment_id: int
    path_step_id: int | None
    assessment_type: str
    attempt_number: int
    questions: list[Any]
    answers: list[Any] | dict[str, Any] | None
    score: float | None
    passed: bool | None
    submitted_at: LocalDatetime | None


class BadgeCreate(RequestSchema):
    enrollment_id: int = Field(gt=0)
    issued_at: AwareDatetime | None = None
    image_url: str | None = Field(default=None, max_length=1000)
    open_badges_metadata: dict[str, Any] | None = None


class BadgeUpdate(RequestSchema):
    image_url: str | None = Field(default=None, max_length=1000)
    open_badges_metadata: dict[str, Any] | None = None


class BadgeResponse(ResponseSchema):
    enrollment_id: int
    issued_at: LocalDatetime
    image_url: str | None
    open_badges_metadata: dict[str, Any] | None
