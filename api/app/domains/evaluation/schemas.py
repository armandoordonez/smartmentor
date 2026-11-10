"""Contratos HTTP de evaluación humana (docs/contracts/api-v2.md, sección 5.1)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.common.schemas import RequestSchema, UtcDatetime


class EvaluatorCreate(RequestSchema):
    user_id: int = Field(gt=0)


class EvaluatorResponse(BaseModel):
    id: int
    course_id: int
    user_id: int
    assigned_by_user_id: int
    created_at: UtcDatetime | None


class AnnotationCreate(RequestSchema):
    single_correct: bool | None = None
    clear_stem: bool | None = None
    bloom_ok: bool | None = None
    plausible_distractors: bool | None = None
    verdict: Literal["valid", "invalid"]
    comment: str | None = Field(default=None, max_length=2000)


class AnnotationResponse(BaseModel):
    id: int
    assessment_item_id: int
    evaluator_slot: int
    single_correct: bool | None
    clear_stem: bool | None
    bloom_ok: bool | None
    plausible_distractors: bool | None
    verdict: str
    comment: str | None
    created_at: UtcDatetime | None


class QueueItem(BaseModel):
    """Un ítem por anotar: con la clave y la rúbrica, nunca la anotación de otro evaluador."""

    id: int
    topic_id: int
    learning_outcome_id: int | None
    source: str
    item_type: str
    bloom_level: str
    difficulty: int
    stem: str
    options: list[Any] | None
    correct_option: int | None
    model_answer: str | None
    rubric: list[Any] | None
    review_status: str
    own_annotation: AnnotationResponse | None


class CriterionGrade(RequestSchema):
    criterion: str = Field(min_length=1, max_length=1000)
    met: bool
    points_awarded: float = Field(ge=0, le=1)


class HumanGradingCreate(RequestSchema):
    criteria: list[CriterionGrade] = Field(min_length=1, max_length=10)
    score: float = Field(ge=0, le=100)
    sample_type: Literal["random", "learner_request"]


class GradingQueueEntry(BaseModel):
    """Una respuesta corta por calificar: sin la nota del LLM ni la identidad del aprendiz."""

    attempt_answer_id: int
    item_id: int
    topic_id: int
    stem: str
    model_answer: str | None
    rubric: list[Any]
    text_answer: str | None
    review_requested_at: UtcDatetime | None


class LlmGradeResponse(BaseModel):
    score: float | None
    is_correct: bool | None
    rubric_detail: Any
    feedback: str | None


class HumanGradingResponse(BaseModel):
    id: int
    attempt_answer_id: int
    sample_type: str
    criteria: list[Any] | None
    score: float
    llm_grading: LlmGradeResponse
    created_at: UtcDatetime | None
