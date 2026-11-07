"""``items.generate_quiz_bank`` and ``items.generate_final_bank`` (ADR 0015, plan 5.4.3).

The bank is generated from the learning outcomes (not from the study text, L-02) when the course
is published, reviewed by ``item_review`` (L-03) and handed to the instructor. Items never repeat
the stems the bank already has (``previous_stems``), so each attempt can take unseen items.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.application.content.context import (
    TaskContext,
    TaskResult,
    load_topic,
    load_topics,
    to_json,
    topic_payload,
)
from app.application.items.checks import check_final_bank, check_quiz_bank, final_source
from app.application.items.review import BANK_CONTRACT, ItemReviewer, build_bank
from app.application.llm_runner import LlmRunner
from app.domain.contracts.assessment import AssessmentItemsLLM
from app.domain.contracts.common import ItemSource
from app.ports.catalog import CatalogReader, TopicRecord

MAX_QUIZ_ITEMS = 40
MAX_PREVIOUS_STEMS = 200
DEFAULT_QUIZ_ITEMS = 23  # 3 attempts x 5 items x 1.5 margin (ADR 0015)
SHORT_ANSWER_SHARE = 5  # of 23: about one short answer per attempt plus margin


def quiz_split(total: int) -> tuple[int, int]:
    """(multiple choice, short answer) for ``total`` items: 18 + 5 for the default 23."""
    short = max(1, round(total * SHORT_ANSWER_SHARE / DEFAULT_QUIZ_ITEMS)) if total > 1 else 0
    return total - short, short


class QuizBankInput(BaseModel):
    topic_id: str
    n_multiple_choice: int = Field(ge=0, le=MAX_QUIZ_ITEMS)
    n_short_answer: int = Field(ge=0, le=MAX_QUIZ_ITEMS)
    previous_stems: list[str] = Field(default_factory=list, max_length=MAX_PREVIOUS_STEMS)

    @model_validator(mode="after")
    def _at_least_one(self) -> QuizBankInput:
        if self.n_multiple_choice + self.n_short_answer < 1:
            raise ValueError("a bank needs at least one item")
        return self


class FinalBankInput(BaseModel):
    learning_path_id: int
    topic_ids: list[str] = Field(min_length=1)
    n_short_answer: int = Field(ge=0, le=10)
    n_versions: int = Field(ge=1, le=4)
    previous_stems: list[str] = Field(default_factory=list, max_length=MAX_PREVIOUS_STEMS)


def _outcome_text(topics: Sequence[TopicRecord]) -> dict[str, str]:
    return {o.id: o.statement for t in topics for o in t.outcomes}


class QuizBankTask:
    job_type = "items.generate_quiz_bank"

    def __init__(
        self, *, runner: LlmRunner, reviewer: ItemReviewer, catalog: CatalogReader
    ) -> None:
        self._runner = runner
        self._reviewer = reviewer
        self._catalog = catalog

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = QuizBankInput.model_validate(raw)
        topic = await load_topic(self._catalog, data.topic_id)
        call = ctx.call(self.job_type, course_id=topic.course_id)
        outcome_ids = {o.id for o in topic.outcomes}
        batch, meta = await self._runner.run(
            "topic_quiz",
            {
                "topic": to_json(topic_payload(topic)),
                "previous_items": to_json(data.previous_stems),
                "topic_id": topic.id,
                "n_multiple_choice": data.n_multiple_choice,
                "n_short_answer": data.n_short_answer,
            },
            AssessmentItemsLLM,
            call,
            check=lambda out: check_quiz_bank(
                out,
                topic_id=topic.id,
                outcome_ids=outcome_ids,
                n_multiple_choice=data.n_multiple_choice,
                n_short_answer=data.n_short_answer,
                previous_stems=data.previous_stems,
            ),
        )
        reviews = await self._reviewer.review(batch.items, _outcome_text([topic]), call)
        sources: Mapping[str, ItemSource] = {i.id: "topic_quiz" for i in batch.items}
        bank = build_bank(batch.items, sources, reviews, meta, topic_id=topic.id)
        return TaskResult(BANK_CONTRACT, bank.model_dump(mode="json"))


class FinalBankTask:
    job_type = "items.generate_final_bank"

    def __init__(
        self, *, runner: LlmRunner, reviewer: ItemReviewer, catalog: CatalogReader
    ) -> None:
        self._runner = runner
        self._reviewer = reviewer
        self._catalog = catalog

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = FinalBankInput.model_validate(raw)
        topics = await load_topics(self._catalog, data.topic_ids)
        call = ctx.call(self.job_type, course_id=topics[0].course_id)
        outcomes = {t.id: {o.id for o in t.outcomes} for t in topics}
        listing = [topic_payload(t) for t in topics]
        batch, meta = await self._runner.run(
            "final_assessment",
            {
                "topics": to_json(listing),
                "previous_items": to_json(data.previous_stems),
                "n_short_answer": data.n_short_answer,
                "n_versions": data.n_versions,
            },
            AssessmentItemsLLM,
            call,
            check=lambda out: check_final_bank(
                out,
                outcomes=outcomes,
                path_topic_ids=data.topic_ids,
                n_short_answer=data.n_short_answer,
                n_versions=data.n_versions,
                previous_stems=data.previous_stems,
            ),
        )
        reviews = await self._reviewer.review(batch.items, _outcome_text(topics), call)
        sources = {i.id: final_source(i.id) for i in batch.items}
        bank = build_bank(batch.items, sources, reviews, meta, topic_id=None)
        return TaskResult(BANK_CONTRACT, bank.model_dump(mode="json"))
