"""Entidades de evaluación humana (Python puro)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class CourseEvaluator(BaseEntity):
    course_id: int
    user_id: int
    assigned_by_user_id: int


@dataclass(kw_only=True)
class ItemAnnotation(BaseEntity):
    assessment_item_id: int
    annotator_user_id: int
    evaluator_slot: int
    single_correct: bool | None = None
    clear_stem: bool | None = None
    bloom_ok: bool | None = None
    plausible_distractors: bool | None = None
    verdict: str
    comment: str | None = None


@dataclass(kw_only=True)
class HumanGrading(BaseEntity):
    attempt_answer_id: int
    grader_user_id: int
    sample_type: str
    criteria: list[Any] | None = None
    score: float


@dataclass(frozen=True)
class AnswerForGrading:
    """Una respuesta corta tal como la ve el evaluador: sin la nota del LLM."""

    answer_id: int
    course_id: int
    topic_id: int
    item_id: int
    stem: str
    model_answer: str | None
    rubric: list[Any]
    text_answer: str | None
    review_requested_at: datetime | None


@dataclass(frozen=True)
class LlmGrade:
    """La nota del LLM, que solo se devuelve después de guardar la calificación humana."""

    score: float | None
    is_correct: bool | None
    rubric_detail: Any
    feedback: str | None


@dataclass(frozen=True)
class GradableAnswer:
    answer: AnswerForGrading
    grader: str | None
    llm: LlmGrade
