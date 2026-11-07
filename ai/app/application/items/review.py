"""Automatic review of generated items (``items.review``, L-03) and the bank it feeds.

Every bank (diagnostic, quiz, final) is reviewed before the instructor sees it: items without a
single correct answer go to ``discarded_item_ids`` and the API stores them as ``auto_rejected``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.application.content.context import TaskContext, TaskResult, to_json
from app.application.llm_runner import CallContext, LlmRunner
from app.domain.contracts.assessment import (
    AssessmentItem,
    AssessmentItemBank,
    AssessmentItemLLM,
    ItemReview,
    ItemReviewLLM,
    ItemReviewResult,
    item_from_llm,
)
from app.domain.contracts.common import ItemSource, Meta
from app.domain.contracts.validation import check_item_reviews, discarded_item_ids
from app.domain.errors import TaskError

BANK_CONTRACT = "assessment_item_bank.v1"
REVIEW_CONTRACT = "item_review.v1"


class ReviewItemInput(BaseModel):
    item_id: str
    item_type: str
    bloom_level: str
    stem: str
    options: list[str] = Field(default_factory=list)
    correct_option: int | None = None
    rubric: list[dict[str, Any]] = Field(default_factory=list)
    outcome: str = ""


class ReviewInput(BaseModel):
    items: list[ReviewItemInput] = Field(min_length=1)


def review_payload(
    items: Sequence[AssessmentItemLLM], outcome_text: Mapping[str, str]
) -> list[dict[str, Any]]:
    """The items as ``item_review`` receives them (JSON)."""
    return [
        {
            "item_id": i.id,
            "item_type": i.item_type,
            "bloom_level": i.bloom_level,
            "stem": i.stem,
            "options": i.options,
            "correct_option": i.correct_option if i.item_type == "multiple_choice" else None,
            "rubric": [{"criterion": c.criterion, "points": c.points} for c in i.rubric],
            "outcome": outcome_text.get(i.outcome_id, i.outcome_id),
        }
        for i in items
    ]


class ItemReviewer:
    def __init__(self, runner: LlmRunner) -> None:
        self._runner = runner

    async def review_raw(
        self, payload: list[dict[str, Any]], ctx: CallContext
    ) -> tuple[ItemReviewLLM, Meta]:
        item_ids = [str(p["item_id"]) for p in payload]
        return await self._runner.run(
            "item_review",
            {"items": to_json(payload)},
            ItemReviewLLM,
            ctx,
            check=lambda out: check_item_reviews(out, item_ids),
        )

    async def review(
        self,
        items: Sequence[AssessmentItemLLM],
        outcome_text: Mapping[str, str],
        ctx: CallContext,
    ) -> ItemReviewLLM:
        reviews, _ = await self.review_raw(review_payload(items, outcome_text), ctx)
        return reviews


class ReviewTask:
    """``items.review``: reviews a batch given in the input."""

    job_type = "items.review"

    def __init__(self, reviewer: ItemReviewer) -> None:
        self._reviewer = reviewer

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = ReviewInput.model_validate(raw)
        payload = [i.model_dump() for i in data.items]
        llm, meta = await self._reviewer.review_raw(payload, ctx.call(self.job_type))
        result = ItemReviewResult(
            reviews=[ItemReview.model_validate(r.model_dump()) for r in llm.reviews],
            discarded_item_ids=discarded_item_ids(llm),
            meta=meta,
        )
        return TaskResult(REVIEW_CONTRACT, result.model_dump(mode="json"))


def build_bank(
    items: Sequence[AssessmentItemLLM],
    sources: Mapping[str, ItemSource],
    reviews: ItemReviewLLM,
    meta: Meta,
    *,
    topic_id: str | None,
) -> AssessmentItemBank:
    """The contract bank from checked LLM items and their review."""
    try:
        contract_items: list[AssessmentItem] = [item_from_llm(i, sources[i.id]) for i in items]
        return AssessmentItemBank(
            topic_id=topic_id,
            items=contract_items,
            item_reviews=[ItemReview.model_validate(r.model_dump()) for r in reviews.reviews],
            discarded_item_ids=discarded_item_ids(reviews),
            meta=meta,
        )
    except ValidationError as exc:
        raise TaskError("INVALID_OUTPUT", f"the bank does not fit the contract: {exc}") from exc
