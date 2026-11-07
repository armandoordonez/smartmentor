"""Diagnostic: item generation (``diagnostic.generate_items``), levels (``levels.estimate``,
synchronous) and finalisation with the objective (``diagnostic.finalize``)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from app.application.items import ReviewItem, review_items
from app.application.jobs import JobContext, JobHandler
from app.application.llm_runner import CallContext, EmbeddingRunner, LlmRunner
from app.domain.contracts.assessment import (
    AssessmentItemBank,
    AssessmentItemsLLM,
    LearnerAnswer,
    item_from_llm,
)
from app.domain.contracts.common import ContractModel, ItemType
from app.domain.contracts.diagnostic import (
    DiagnosticFinalization,
    DiagnosticResult,
    LevelThresholds,
    LevelWeights,
    Objective,
    ObjectiveLLM,
)
from app.domain.contracts.validation import (
    check_assessment_items,
    check_diagnostic_coverage,
    check_objective,
)
from app.domain.errors import InputReferenceNotFoundError, TaskError
from app.domain.leveling import ScoredItem, cosine, estimate_levels
from app.domain.pseudonymize import pseudonymize
from app.ports.catalog import CatalogReader, TopicRecord

# ---------- diagnostic.generate_items ----------


class DiagnosticGenerateInput(ContractModel):
    course_id: int = Field(ge=1)


def topics_payload(topics: Sequence[TopicRecord]) -> str:
    """Topics with their outcomes for the generation prompts (ids are the database ids)."""
    return json.dumps(
        [
            {
                "id": t.id,
                "name": t.name,
                "subtopics": t.subtopics,
                "learning_outcomes": [{"id": o.id, "statement": o.statement} for o in t.outcomes],
            }
            for t in topics
        ],
        ensure_ascii=False,
    )


class DiagnosticGenerateHandler(JobHandler[DiagnosticGenerateInput]):
    job_type = "diagnostic.generate_items"
    contract = "assessment_item_bank.v1"
    input_model = DiagnosticGenerateInput

    def __init__(self, runner: LlmRunner, catalog: CatalogReader) -> None:
        self._runner = runner
        self._catalog = catalog

    async def run(self, payload: DiagnosticGenerateInput, ctx: JobContext) -> AssessmentItemBank:
        topics = await self._catalog.course_topics(payload.course_id)
        if not topics:
            raise InputReferenceNotFoundError(f"course {payload.course_id} has no topics")
        outcomes = {t.id: {o.id for o in t.outcomes} for t in topics}
        statements = {o.id: o.statement for t in topics for o in t.outcomes}
        topic_ids = [t.id for t in topics]
        generated, meta = await self._runner.run(
            "diagnostic_generation",
            {"topics": topics_payload(topics)},
            AssessmentItemsLLM,
            ctx.call(),
            check=lambda items: (
                check_assessment_items(items, outcomes)
                + check_diagnostic_coverage(items, topic_ids)
            ),
        )
        items = [item_from_llm(i, "diagnostic") for i in generated.items]
        to_review = [
            ReviewItem(
                item_id=i.id,
                item_type=i.item_type,
                bloom_level=i.bloom_level,
                stem=i.stem,
                options=i.options,
                correct_option=i.correct_option,
                rubric=i.rubric,
                outcome=statements.get(i.outcome_id, ""),
            )
            for i in items
        ]
        reviews, discarded, _ = await review_items(self._runner, to_review, ctx.call())
        return AssessmentItemBank(
            topic_id=None,
            items=items,
            item_reviews=reviews,
            discarded_item_ids=discarded,
            meta=meta,
        )


# ---------- levels.estimate ----------


class DiagnosticItemInput(ContractModel):
    item_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    item_type: ItemType
    difficulty: int = Field(ge=1, le=3)
    correct_option: int | None = Field(default=None, ge=0, le=3)


class LevelsEstimateInput(ContractModel):
    topic_ids: list[str] = Field(min_length=1, max_length=200)
    items: list[DiagnosticItemInput] = Field(max_length=1000)
    answers: list[LearnerAnswer] = Field(max_length=1000)
    profile_text: str | None = Field(default=None, max_length=10_000)
    resume_text: str | None = Field(default=None, max_length=10_000)
    weights: LevelWeights
    thresholds: LevelThresholds

    @model_validator(mode="after")
    def _check_ids(self) -> Self:
        if len(set(self.topic_ids)) != len(self.topic_ids):
            raise ValueError("topic_ids has duplicates")
        item_ids = [i.item_id for i in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("items has duplicated item_id")
        return self


class LevelEstimator:
    """Deterministic levels plus the profile and resume signals (embeddings)."""

    def __init__(self, embeddings: EmbeddingRunner, catalog: CatalogReader) -> None:
        self._embeddings = embeddings
        self._catalog = catalog

    async def _similarities(
        self, payload: LevelsEstimateInput, ctx: CallContext
    ) -> tuple[dict[str, float] | None, dict[str, float] | None]:
        texts = {
            "profile": (payload.profile_text or "").strip(),
            "resume": (payload.resume_text or "").strip(),
        }
        wanted = [name for name, text in texts.items() if text]
        if not wanted:
            return None, None
        topics = {t.id: t for t in await self._catalog.topics(payload.topic_ids)}
        if missing := [t for t in payload.topic_ids if t not in topics]:
            raise InputReferenceNotFoundError(f"unknown topics: {missing}")
        topic_texts = [topics[t].similarity_text() for t in payload.topic_ids]
        person_texts = [pseudonymize(texts[name]) for name in wanted]
        vectors = await self._embeddings.embed([*topic_texts, *person_texts], "similarity", ctx)
        topic_vectors = vectors[: len(topic_texts)]
        result: dict[str, dict[str, float]] = {}
        for offset, name in enumerate(wanted):
            person = vectors[len(topic_texts) + offset]
            result[name] = {
                topic_id: cosine(vector, person)
                for topic_id, vector in zip(payload.topic_ids, topic_vectors, strict=True)
            }
        return result.get("profile"), result.get("resume")

    async def estimate(self, payload: LevelsEstimateInput, ctx: CallContext) -> DiagnosticResult:
        profile, resume = await self._similarities(payload, ctx)
        items = [
            ScoredItem(
                item_id=i.item_id,
                topic_id=i.topic_id,
                item_type=i.item_type,
                difficulty=i.difficulty,
                correct_option=i.correct_option,
            )
            for i in payload.items
        ]
        return estimate_levels(
            topic_ids=payload.topic_ids,
            items=items,
            answers=payload.answers,
            weights=payload.weights,
            thresholds=payload.thresholds,
            profile_similarity=profile,
            resume_similarity=resume,
        )


# ---------- diagnostic.finalize ----------


class ObjectiveParts(ContractModel):
    bloom_verb: str = Field(min_length=1)
    content: str = Field(min_length=1)
    criterion: str = Field(min_length=1)


class DiagnosticFinalizeInput(LevelsEstimateInput):
    objective_mode: Literal["llm", "path_default"]
    path_objective: str = Field(min_length=1, max_length=2_000)
    path_objective_parts: ObjectiveParts | None = None

    @model_validator(mode="after")
    def _check_parts(self) -> Self:
        if self.objective_mode == "path_default" and self.path_objective_parts is None:
            raise ValueError("path_default needs path_objective_parts")
        return self


class DiagnosticFinalizeHandler(JobHandler[DiagnosticFinalizeInput]):
    job_type = "diagnostic.finalize"
    contract = "diagnostic_finalization.v1"
    input_model = DiagnosticFinalizeInput

    def __init__(self, runner: LlmRunner, estimator: LevelEstimator) -> None:
        self._runner = runner
        self._estimator = estimator

    async def run(
        self, payload: DiagnosticFinalizeInput, ctx: JobContext
    ) -> DiagnosticFinalization:
        result = await self._estimator.estimate(payload, ctx.call())
        gaps = [t.topic_id for t in result.level_by_topic if t.classification != "mastered"]
        if payload.objective_mode == "path_default":
            parts = payload.path_objective_parts
            if parts is None:  # pragma: no cover - guaranteed by the input validator
                raise TaskError("INTERNAL_ERROR", "path_objective_parts missing")
            objective = Objective(
                origin="path_default",
                statement=payload.path_objective,
                bloom_verb=parts.bloom_verb,
                content=parts.content,
                criterion=parts.criterion,
                focus_topics=gaps,
                rationale="",
            )
            return DiagnosticFinalization(diagnostic_result=result, objective=objective)
        levels = [
            {"topic_id": t.topic_id, "level": t.level, "classification": t.classification}
            for t in result.level_by_topic
        ]
        topic_ids = set(payload.topic_ids)
        llm, meta = await self._runner.run(
            "learning_objective",
            {
                "path_objective": payload.path_objective,
                "profile": pseudonymize(payload.profile_text or "") or "(sin descripción)",
                "levels": json.dumps(levels, ensure_ascii=False),
            },
            ObjectiveLLM,
            ctx.call(),
            check=lambda objective: check_objective(objective, topic_ids),
            # Personal content (profile): never shared through the cache (plan 5.4.11).
            use_cache=False,
        )
        objective = Objective(
            origin="llm_proposed",
            statement=llm.statement,
            bloom_verb=llm.bloom_verb,
            content=llm.content,
            criterion=llm.criterion,
            focus_topics=llm.focus_topics,
            rationale=llm.rationale,
            meta=meta,
        )
        return DiagnosticFinalization(diagnostic_result=result, objective=objective)
