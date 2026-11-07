"""Assessment items (diagnostic, topic quiz, final, retention), item review and simulated answers.

Prompts: ``diagnostic_generation``, ``topic_quiz``, ``final_assessment`` -> ``assessment_item.v1``
and ``assessment_item_bank.v1``; ``item_review`` -> ``item_review.v1``; ``simulated_learner``
-> ``simulated_answers.v1`` (evaluation only).
"""

from __future__ import annotations

import math
from typing import Self

from pydantic import Field, model_validator

from app.domain.contracts.common import (
    MULTIPLE_CHOICE_OPTIONS,
    BloomLevel,
    ContractModel,
    ItemSource,
    ItemType,
    LlmModel,
    Meta,
)

RUBRIC_MIN_CRITERIA = 2
RUBRIC_MAX_CRITERIA = 3
RUBRIC_POINTS_TOLERANCE = 0.01

# ---------- LLM output ----------


class RubricCriterionLLM(LlmModel):
    criterion: str
    points: float = Field(description="Points of the criterion; the rubric adds up to 1")


class AssessmentItemLLM(LlmModel):
    id: str = Field(description="Key inside the generated batch (d_<topic>_<n>, q<n>, f<n>)")
    topic_id: str = Field(description="Topic id from the syllabus")
    outcome_id: str = Field(description="Learning outcome id the item assesses")
    item_type: ItemType
    bloom_level: BloomLevel
    difficulty: int = Field(
        description="1 = low (remember), 2 = medium (apply), 3 = high (analyze)"
    )
    stem: str
    options: list[str] = Field(description="4 options in multiple choice; empty in short answer")
    correct_option: int = Field(
        description="0-based index of the correct option; -1 in short answer"
    )
    model_answer: str = Field(
        description="Rationale of the correct option and of each distractor (multiple choice) "
        "or expected answer (short answer)"
    )
    rubric: list[RubricCriterionLLM] = Field(description="Only short answer; empty otherwise")
    equivalence_group: str = Field(
        description="Same value for parallel items (final and retention); empty when not used"
    )


class AssessmentItemsLLM(LlmModel):
    items: list[AssessmentItemLLM]


class ItemReviewEntryLLM(LlmModel):
    item_id: str
    single_correct_answer: bool
    clear_stem: bool
    bloom_matches: bool
    aligned_with_outcome: bool
    issues: list[str]


class ItemReviewLLM(LlmModel):
    reviews: list[ItemReviewEntryLLM]


class LearnerAnswerLLM(LlmModel):
    item_id: str
    selected_option: int = Field(description="0-based index; -1 in short answer or «No lo sé»")
    dont_know: bool
    text_answer: str = Field(description="Written answer; empty in multiple choice")


class SimulatedAnswersLLM(LlmModel):
    answers: list[LearnerAnswerLLM]


# ---------- Contracts ----------


class RubricCriterion(ContractModel):
    criterion: str = Field(min_length=1)
    points: float = Field(gt=0, le=1)


class ItemReview(ContractModel):
    item_id: str
    single_correct_answer: bool
    clear_stem: bool
    bloom_matches: bool
    aligned_with_outcome: bool
    issues: list[str]

    @property
    def has_observations(self) -> bool:
        return bool(self.issues) or not (
            self.clear_stem and self.bloom_matches and self.aligned_with_outcome
        )


class AssessmentItem(ContractModel):
    id: str = Field(min_length=1)
    topic_id: str
    outcome_id: str
    source: ItemSource
    item_type: ItemType
    bloom_level: BloomLevel
    difficulty: int = Field(ge=1, le=3)
    stem: str = Field(min_length=1)
    options: list[str]
    correct_option: int | None = Field(default=None, ge=0, le=MULTIPLE_CHOICE_OPTIONS - 1)
    model_answer: str
    rubric: list[RubricCriterion]
    equivalence_group: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.item_type == "multiple_choice":
            if len(self.options) != MULTIPLE_CHOICE_OPTIONS:
                raise ValueError(f"{self.id}: multiple choice needs exactly 4 options")
            if len({o.strip().casefold() for o in self.options}) != MULTIPLE_CHOICE_OPTIONS:
                raise ValueError(f"{self.id}: options must be different")
            if self.correct_option is None:
                raise ValueError(f"{self.id}: multiple choice needs correct_option")
            if self.rubric:
                raise ValueError(f"{self.id}: multiple choice has no rubric")
        else:
            if self.options or self.correct_option is not None:
                raise ValueError(f"{self.id}: short answer has no options nor correct_option")
            if not RUBRIC_MIN_CRITERIA <= len(self.rubric) <= RUBRIC_MAX_CRITERIA:
                raise ValueError(f"{self.id}: short answer needs 2 to 3 rubric criteria")
            total = math.fsum(c.points for c in self.rubric)
            if abs(total - 1) > RUBRIC_POINTS_TOLERANCE:
                raise ValueError(f"{self.id}: rubric points must add up to 1 (got {total})")
        if self.source in ("final", "retention") and not self.equivalence_group:
            raise ValueError(f"{self.id}: final and retention items need equivalence_group")
        return self


class AssessmentItemBank(ContractModel):
    """Result of ``diagnostic.generate_items``, ``items.generate_quiz_bank`` and
    ``items.generate_final_bank``: items plus their automatic review."""

    topic_id: str | None = Field(default=None, description="Set for topic quiz banks")
    items: list[AssessmentItem] = Field(min_length=1)
    item_reviews: list[ItemReview]
    discarded_item_ids: list[str] = Field(
        description="Items without a single correct answer; stored as auto_rejected"
    )
    meta: Meta

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicated item ids in the bank")
        known = set(ids)
        reviewed = {r.item_id: r for r in self.item_reviews}
        if len(reviewed) != len(self.item_reviews):
            raise ValueError("an item has more than one review")
        if unknown := sorted(set(reviewed) - known):
            raise ValueError(f"reviews of unknown items: {unknown}")
        for item_id in self.discarded_item_ids:
            review = reviewed.get(item_id)
            if review is None or review.single_correct_answer:
                raise ValueError(
                    f"{item_id}: only reviewed items without a single answer are discarded"
                )
        if self.topic_id is not None and any(i.topic_id != self.topic_id for i in self.items):
            raise ValueError("every item of a topic bank belongs to that topic")
        return self


class ItemReviewResult(ContractModel):
    """Result of ``items.review``."""

    reviews: list[ItemReview] = Field(min_length=1)
    discarded_item_ids: list[str]
    meta: Meta

    @model_validator(mode="after")
    def _check_discarded(self) -> Self:
        rejected = {r.item_id for r in self.reviews if not r.single_correct_answer}
        if set(self.discarded_item_ids) != rejected:
            raise ValueError("discarded_item_ids must be the items without a single correct answer")
        return self


class LearnerAnswer(ContractModel):
    item_id: str
    selected_option: int | None = Field(default=None, ge=0, le=MULTIPLE_CHOICE_OPTIONS - 1)
    dont_know: bool = False
    text_answer: str | None = None

    @model_validator(mode="after")
    def _check_exclusive(self) -> Self:
        if self.dont_know and (self.selected_option is not None or self.text_answer):
            raise ValueError(f"{self.item_id}: «No lo sé» has no option nor text")
        if self.selected_option is not None and self.text_answer:
            raise ValueError(f"{self.item_id}: an answer is either an option or a text")
        return self


class SimulatedAnswers(ContractModel):
    """Result of ``eval.simulate_learner`` (evaluation harness only)."""

    answers: list[LearnerAnswer]
    meta: Meta


def item_from_llm(item: AssessmentItemLLM, source: ItemSource) -> AssessmentItem:
    """Contract item from a checked LLM item (-1 -> null, empty group -> null)."""
    return AssessmentItem(
        id=item.id,
        topic_id=item.topic_id,
        outcome_id=item.outcome_id,
        source=source,
        item_type=item.item_type,
        bloom_level=item.bloom_level,
        difficulty=item.difficulty,
        stem=item.stem,
        options=item.options,
        correct_option=item.correct_option if item.item_type == "multiple_choice" else None,
        model_answer=item.model_answer,
        rubric=[RubricCriterion(criterion=c.criterion, points=c.points) for c in item.rubric],
        equivalence_group=item.equivalence_group or None,
    )


def answer_from_llm(answer: LearnerAnswerLLM) -> LearnerAnswer:
    """Contract answer from a simulated LLM answer (-1 and empty text -> null)."""
    return LearnerAnswer(
        item_id=answer.item_id,
        selected_option=answer.selected_option if answer.selected_option >= 0 else None,
        dont_know=answer.dont_know,
        text_answer=answer.text_answer or None,
    )
