"""Level per topic from the diagnostic (plan 5.4.8, brief P1). Deterministic, no LLM.

Signals per topic (0-100):

* ``test``: difficulty-weighted hits of the diagnostic items; «No lo sé», a missing answer or a
  short answer without grading count as a miss.
* ``profile``: cosine between the learner description and the topic, min-max normalised over
  the topics (as the notebook v2).
* ``resume``: the same with the resume text (DEF-10).

The level is the weighted sum with the path weights (80/10/10 by default, C-02). A missing
signal gives its weight to the present ones in proportion; if nothing is left, the test counts
alone with score 0.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.contracts.assessment import LearnerAnswer
from app.domain.contracts.common import ItemType
from app.domain.contracts.diagnostic import (
    DiagnosticResult,
    LevelThresholds,
    LevelWeights,
    TopicLevel,
)

ALGORITHM = "weighted_difficulty v1"
SPREAD_EPSILON = 1e-6


@dataclass(frozen=True)
class ScoredItem:
    item_id: str
    topic_id: str
    item_type: ItemType
    difficulty: int
    correct_option: int | None


def is_hit(item: ScoredItem, answer: LearnerAnswer | None) -> bool:
    if answer is None or answer.dont_know or item.item_type != "multiple_choice":
        return False
    return item.correct_option is not None and answer.selected_option == item.correct_option


def test_scores(
    topic_ids: Sequence[str], items: Sequence[ScoredItem], answers: Sequence[LearnerAnswer]
) -> tuple[dict[str, float | None], float]:
    """Score per topic (``None`` without items) and the overall score, both 0-100."""
    by_item = {a.item_id: a for a in answers}
    known = set(topic_ids)
    weight: dict[str, int] = {}
    earned: dict[str, int] = {}
    for item in items:
        if item.topic_id not in known:
            continue
        weight[item.topic_id] = weight.get(item.topic_id, 0) + item.difficulty
        if is_hit(item, by_item.get(item.item_id)):
            earned[item.topic_id] = earned.get(item.topic_id, 0) + item.difficulty
    scores: dict[str, float | None] = {
        t: (100 * earned.get(t, 0) / weight[t] if weight.get(t) else None) for t in topic_ids
    }
    total_weight = sum(weight.values())
    overall = 100 * sum(earned.values()) / total_weight if total_weight else 0.0
    return scores, overall


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = math.fsum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(math.fsum(x * x for x in a)) * math.sqrt(math.fsum(y * y for y in b))
    return max(-1.0, min(1.0, dot / norm)) if norm > 0 else 0.0


def normalized_priors(similarities: Sequence[float]) -> list[float]:
    """Min-max to 0-100 over the topics; all zero when the spread is negligible (notebook)."""
    if not similarities:
        return []
    low, high = min(similarities), max(similarities)
    spread = high - low
    if spread <= SPREAD_EPSILON:
        return [0.0 for _ in similarities]
    return [min(100.0, max(0.0, 100 * (s - low) / spread)) for s in similarities]


def applied_weights(
    configured: LevelWeights, *, test: bool, profile: bool, resume: bool
) -> LevelWeights | None:
    """Redistribute the weights of missing signals; ``None`` when nothing has weight."""
    present = {
        "test": configured.test if test else 0.0,
        "profile": configured.profile if profile else 0.0,
        "resume": configured.resume if resume else 0.0,
    }
    total = math.fsum(present.values())
    if total <= 0:
        return None
    return LevelWeights(
        test=present["test"] / total,
        profile=present["profile"] / total,
        resume=present["resume"] / total,
    )


def combine(
    test: float | None,
    profile_prior: float | None,
    resume_prior: float | None,
    configured: LevelWeights,
) -> tuple[float | None, LevelWeights, float]:
    """Return (test score used, weights applied, level 0-100 before rounding)."""
    weights = applied_weights(
        configured,
        test=test is not None,
        profile=profile_prior is not None,
        resume=resume_prior is not None,
    )
    if weights is None:
        test = test if test is not None else 0.0
        weights = LevelWeights(test=1.0, profile=0.0, resume=0.0)
    level = math.fsum(
        (
            weights.test * (test or 0.0),
            weights.profile * (profile_prior or 0.0),
            weights.resume * (resume_prior or 0.0),
        )
    )
    return test, weights, max(0.0, min(100.0, level))


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def estimate_levels(
    *,
    topic_ids: Sequence[str],
    items: Sequence[ScoredItem],
    answers: Sequence[LearnerAnswer],
    weights: LevelWeights,
    thresholds: LevelThresholds,
    profile_similarity: Mapping[str, float] | None = None,
    resume_similarity: Mapping[str, float] | None = None,
) -> DiagnosticResult:
    """``diagnostic_result.v1`` for the given topics (order kept)."""
    if len(set(topic_ids)) != len(topic_ids):
        raise ValueError("topic_ids has duplicates")
    scores, overall = test_scores(topic_ids, items, answers)
    profile_priors = _priors(topic_ids, profile_similarity)
    resume_priors = _priors(topic_ids, resume_similarity)
    levels: list[TopicLevel] = []
    for topic_id in topic_ids:
        prior = profile_priors.get(topic_id)
        resume = resume_priors.get(topic_id)
        # The configured weight of a signal with value 0 does not hide it: only None is missing.
        test, applied, level = combine(
            _round(scores[topic_id], 1), _round(prior, 1), _round(resume, 1), weights
        )
        rounded = round(level, 1)
        similarity = profile_similarity.get(topic_id) if profile_similarity else None
        levels.append(
            TopicLevel(
                topic_id=topic_id,
                test_score=test,
                profile_similarity=_round(similarity, 4),
                profile_prior=_round(prior, 1),
                resume_prior=_round(resume, 1),
                weights=applied,
                level=rounded,
                classification=thresholds.classify(rounded),
            )
        )
    return DiagnosticResult(
        algorithm=ALGORITHM,
        configured_weights=weights,
        thresholds=thresholds,
        level_by_topic=levels,
        overall_score=round(overall, 1),
    )


def _priors(topic_ids: Sequence[str], similarity: Mapping[str, float] | None) -> dict[str, float]:
    if not similarity:
        return {}
    present = [t for t in topic_ids if t in similarity]
    values = normalized_priors([similarity[t] for t in present])
    return dict(zip(present, values, strict=True))
