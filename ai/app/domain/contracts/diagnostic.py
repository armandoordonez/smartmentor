"""Diagnostic result (``levels.estimate``) and objective (``learning_objective`` prompt).

The diagnostic items live in the item bank (``assessment_item.v1``); the learner answers live
in the API (``attempt_answers``). This module only describes the computed levels and the
proposed objective.
"""

from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel, LlmModel, Meta

Classification = Literal["mastered", "to_reinforce", "to_learn"]
WEIGHT_TOLERANCE = 1e-6

# ---------- Diagnostic result (deterministic, no LLM) ----------


class LevelWeights(ContractModel):
    """Weights of each signal; they add up to 1 (80/10/10 by default, C-02)."""

    test: float = Field(ge=0, le=1)
    profile: float = Field(ge=0, le=1)
    resume: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _check_sum(self) -> Self:
        total = math.fsum((self.test, self.profile, self.resume))
        if abs(total - 1) > WEIGHT_TOLERANCE:
            raise ValueError(f"weights must add up to 1 (got {total})")
        return self


class LevelThresholds(ContractModel):
    mastery_skip_threshold: float = Field(ge=0, le=100, description="Mastered at or above")
    reinforce_cutoff: float = Field(ge=0, le=100, description="To reinforce at or above")

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.reinforce_cutoff > self.mastery_skip_threshold:
            raise ValueError("reinforce_cutoff cannot exceed mastery_skip_threshold")
        return self

    def classify(self, level: float) -> Classification:
        if level >= self.mastery_skip_threshold:
            return "mastered"
        return "to_reinforce" if level >= self.reinforce_cutoff else "to_learn"


class TopicLevel(ContractModel):
    topic_id: str
    test_score: float | None = Field(
        ge=0, le=100, description="Difficulty-weighted hits; «No lo sé» counts as a miss"
    )
    profile_similarity: float | None = Field(ge=-1, le=1, description="Cosine profile vs topic")
    profile_prior: float | None = Field(ge=0, le=100, description="Normalised similarity")
    resume_prior: float | None = Field(ge=0, le=100, description="Resume signal (DEF-10)")
    weights: LevelWeights = Field(description="Weights actually applied (redistributed)")
    level: float = Field(ge=0, le=100)
    classification: Classification


class DiagnosticResult(ContractModel):
    """Result of ``levels.estimate`` (``diagnostics.level_by_topic`` in the API)."""

    algorithm: str = Field(description="Algorithm and version, e.g. weighted_difficulty v1")
    configured_weights: LevelWeights = Field(description="Weights of the learning path")
    thresholds: LevelThresholds
    level_by_topic: list[TopicLevel] = Field(min_length=1)
    overall_score: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _check_levels(self) -> Self:
        ids = [t.topic_id for t in self.level_by_topic]
        if len(ids) != len(set(ids)):
            raise ValueError("a topic appears more than once in level_by_topic")
        for topic in self.level_by_topic:
            expected = self.thresholds.classify(topic.level)
            if topic.classification != expected:
                raise ValueError(f"{topic.topic_id}: classification must be {expected}")
            missing = [
                name
                for name, value, weight in (
                    ("test", topic.test_score, topic.weights.test),
                    ("profile", topic.profile_prior, topic.weights.profile),
                    ("resume", topic.resume_prior, topic.weights.resume),
                )
                if value is None and weight > 0
            ]
            if missing:
                raise ValueError(f"{topic.topic_id}: weight given to missing signals {missing}")
        return self


# ---------- Objective ----------


class ObjectiveLLM(LlmModel):
    statement: str = Field(description="Bloom verb + content + criterion, in Spanish")
    bloom_verb: str
    content: str
    criterion: str
    focus_topics: list[str] = Field(description="Ids of the gap topics (only from the list)")
    rationale: str


ObjectiveOrigin = Literal["path_default", "llm_proposed", "learner_edited"]


class Objective(ContractModel):
    origin: ObjectiveOrigin
    statement: str = Field(min_length=1)
    bloom_verb: str = Field(min_length=1)
    content: str = Field(min_length=1)
    criterion: str = Field(min_length=1, description="Empty criterion = OBJECTIVE_NOT_MEASURABLE")
    focus_topics: list[str]
    rationale: str
    meta: Meta | None = Field(default=None, description="Present when origin is llm_proposed")

    @model_validator(mode="after")
    def _check_meta(self) -> Self:
        if (self.origin == "llm_proposed") != (self.meta is not None):
            raise ValueError("meta is present only for an objective proposed by the LLM")
        return self


class DiagnosticFinalization(ContractModel):
    """Result of the ``diagnostic.finalize`` job: levels plus the proposed objective."""

    diagnostic_result: DiagnosticResult
    objective: Objective

    @model_validator(mode="after")
    def _check_focus(self) -> Self:
        known = {t.topic_id for t in self.diagnostic_result.level_by_topic}
        if unknown := sorted(set(self.objective.focus_topics) - known):
            raise ValueError(f"objective focus topics not in the diagnostic: {unknown}")
        return self
