"""Automatic item review (prompt ``item_review``): ``items.review`` and the review step of the
item-generation jobs (L-03: items without a single correct answer are discarded)."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import Field

from app.application.jobs import JobContext, JobHandler
from app.application.llm_runner import CallContext, LlmRunner
from app.domain.contracts.assessment import (
    ItemReview,
    ItemReviewLLM,
    ItemReviewResult,
    RubricCriterion,
)
from app.domain.contracts.common import BloomLevel, ContractModel, ItemType, Meta
from app.domain.contracts.validation import check_item_reviews, discarded_item_ids
from app.domain.errors import TaskError


class ReviewItem(ContractModel):
    """An item as the reviewer sees it (``docs/contracts/ai-service-v1.md``, ``items.review``)."""

    item_id: str = Field(min_length=1)
    item_type: ItemType
    bloom_level: BloomLevel
    stem: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    correct_option: int | None = None
    rubric: list[RubricCriterion] = Field(default_factory=list)
    outcome: str = Field(description="Statement of the learning outcome the item assesses")


class ItemsReviewInput(ContractModel):
    items: list[ReviewItem] = Field(min_length=1, max_length=200)


async def review_items(
    runner: LlmRunner, items: Sequence[ReviewItem], ctx: CallContext
) -> tuple[list[ItemReview], list[str], Meta]:
    """Review a batch; returns the reviews (in item order), the discarded ids and the meta."""
    ids = [i.item_id for i in items]
    if len(ids) != len(set(ids)):
        raise TaskError("INVALID_OUTPUT", "duplicated item ids in the batch to review")
    payload = json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False)
    llm, meta = await runner.run(
        "item_review",
        {"items": payload},
        ItemReviewLLM,
        ctx,
        check=lambda reviews: check_item_reviews(reviews, ids),
    )
    by_id = {r.item_id: r for r in llm.reviews}
    reviews = [ItemReview.model_validate(by_id[i].model_dump()) for i in ids]
    return reviews, discarded_item_ids(llm), meta


class ItemsReviewHandler(JobHandler[ItemsReviewInput]):
    job_type = "items.review"
    contract = "item_review.v1"
    input_model = ItemsReviewInput

    def __init__(self, runner: LlmRunner) -> None:
        self._runner = runner

    async def run(self, payload: ItemsReviewInput, ctx: JobContext) -> ItemReviewResult:
        reviews, discarded, meta = await review_items(self._runner, payload.items, ctx.call())
        return ItemReviewResult(reviews=reviews, discarded_item_ids=discarded, meta=meta)
