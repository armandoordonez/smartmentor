"""Grading of one answer: rule for multiple choice, ``short_answer_grading`` (LLM as judge)
for short answer -> ``grading.v1``."""

from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.contracts.assessment import RubricCriterion
from app.domain.contracts.common import ContractModel, ItemType, LlmModel, Meta

POINTS_TOLERANCE = 1e-6

# ---------- LLM output ----------


class CriterionResultLLM(LlmModel):
    criterion: str = Field(description="Same text as the rubric criterion")
    met: bool
    points_awarded: float = Field(description="Between 0 and the criterion points")
    evidence: str = Field(description="Part of the answer that justifies the decision")


class ShortAnswerGradingLLM(LlmModel):
    criteria: list[CriterionResultLLM]
    feedback: str = Field(description="Short guidance in Spanish that does not give the answer")


# ---------- Contract ----------


class CriterionResult(ContractModel):
    criterion: str
    met: bool
    points: float = Field(gt=0, le=1, description="Points of the criterion in the rubric")
    points_awarded: float = Field(ge=0, le=1)
    evidence: str

    @model_validator(mode="after")
    def _check_points(self) -> Self:
        if self.points_awarded > self.points + POINTS_TOLERANCE:
            raise ValueError(f"{self.criterion}: points_awarded exceeds the criterion points")
        return self


class AnswerGrading(ContractModel):
    """Grade of one answer (``attempt_answers`` in the API)."""

    item_id: str
    item_type: ItemType
    grader: Literal["rule", "llm_judge", "human"]
    approval_rule: Literal["single_correct_option", "min_criteria_ratio"]
    min_criteria_ratio: float | None = Field(
        default=None, gt=0, le=1, description="Short answer pass rule; 2/3 by default (DEF-21)"
    )
    score: float = Field(ge=0, le=100)
    is_correct: bool
    criteria_met: int = Field(ge=0)
    criteria_total: int = Field(ge=0)
    rubric_detail: list[CriterionResult]
    feedback: str
    meta: Meta | None = Field(default=None, description="Present when grader is llm_judge")

    @model_validator(mode="after")
    def _check_rule(self) -> Self:
        if (self.grader == "llm_judge") != (self.meta is not None):
            raise ValueError("meta is present only for llm_judge")
        if self.item_type == "multiple_choice":
            if self.approval_rule != "single_correct_option" or self.grader != "rule":
                raise ValueError("multiple choice is graded by rule with single_correct_option")
            if self.rubric_detail or self.criteria_total:
                raise ValueError("multiple choice has no rubric detail")
            if self.score not in (0, 100) or self.is_correct != (self.score == 100):
                raise ValueError("multiple choice scores 0 or 100")
            return self
        if self.approval_rule != "min_criteria_ratio" or self.min_criteria_ratio is None:
            raise ValueError("short answer uses min_criteria_ratio")
        if self.criteria_total != len(self.rubric_detail):
            raise ValueError("criteria_total must equal the rubric detail length")
        if self.criteria_met != sum(c.met for c in self.rubric_detail):
            raise ValueError("criteria_met must count the met criteria")
        if self.rubric_detail:
            ratio = self.criteria_met / self.criteria_total
            if self.is_correct != (ratio >= self.min_criteria_ratio - POINTS_TOLERANCE):
                raise ValueError("is_correct must follow min_criteria_ratio")
        elif self.is_correct or self.score:
            raise ValueError("an empty short answer scores 0")
        return self


def grading_from_llm(
    llm: ShortAnswerGradingLLM,
    *,
    item_id: str,
    rubric: list[RubricCriterion],
    min_criteria_ratio: float,
    meta: Meta,
) -> AnswerGrading:
    """Contract from a checked LLM grading (see ``validation.check_short_answer_grading``)."""
    points = {c.criterion: c.points for c in rubric}
    detail = [
        CriterionResult(
            criterion=c.criterion,
            met=c.met,
            points=points[c.criterion],
            points_awarded=c.points_awarded,
            evidence=c.evidence,
        )
        for c in llm.criteria
    ]
    total = math.fsum(points.values())
    awarded = math.fsum(c.points_awarded for c in detail)
    met = sum(c.met for c in detail)
    return AnswerGrading(
        item_id=item_id,
        item_type="short_answer",
        grader="llm_judge",
        approval_rule="min_criteria_ratio",
        min_criteria_ratio=min_criteria_ratio,
        score=round(100 * min(1.0, awarded / total), 1),
        is_correct=met / len(detail) >= min_criteria_ratio - POINTS_TOLERANCE,
        criteria_met=met,
        criteria_total=len(detail),
        rubric_detail=detail,
        feedback=llm.feedback,
        meta=meta,
    )
