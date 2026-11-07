"""``app/domain/leveling.py``: examples of the contract and properties (hypothesis)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.contracts.assessment import LearnerAnswer
from app.domain.contracts.diagnostic import LevelThresholds, LevelWeights
from app.domain.leveling import (
    ScoredItem,
    applied_weights,
    combine,
    estimate_levels,
    normalized_priors,
)
from app.domain.leveling import test_scores as score_items

WEIGHTS = LevelWeights(test=0.8, profile=0.1, resume=0.1)
THRESHOLDS = LevelThresholds(mastery_skip_threshold=80, reinforce_cutoff=50)


def _items(topic: str) -> list[ScoredItem]:
    return [
        ScoredItem(f"{topic}_{d}", topic, "multiple_choice", d, correct_option=1) for d in (1, 2, 3)
    ]


def test_combine_reproduces_the_contract_example() -> None:
    _, weights, level = combine(100.0, 85.0, 70.0, WEIGHTS)
    assert round(level, 1) == 95.5
    assert weights == WEIGHTS
    _, weights, level = combine(0.0, 40.0, None, WEIGHTS)
    assert round(level, 1) == 4.4
    assert weights.resume == 0
    assert math.isclose(weights.test, 0.8 / 0.9)


def test_difficulty_weighted_score_and_dont_know_is_a_miss() -> None:
    items = _items("t")
    answers = [
        LearnerAnswer(item_id="t_1", selected_option=1),
        LearnerAnswer(item_id="t_2", dont_know=True),
        LearnerAnswer(item_id="t_3", selected_option=1),
    ]
    scores, overall = score_items(["t"], items, answers)
    assert scores["t"] == pytest.approx(100 * 4 / 6)
    assert overall == pytest.approx(100 * 4 / 6)


def test_topic_without_items_redistributes_its_weight() -> None:
    result = estimate_levels(
        topic_ids=["a", "b"],
        items=_items("a"),
        answers=[],
        weights=WEIGHTS,
        thresholds=THRESHOLDS,
        profile_similarity={"a": 0.2, "b": 0.6},
    )
    by_topic = {t.topic_id: t for t in result.level_by_topic}
    assert by_topic["b"].test_score is None
    assert by_topic["b"].weights.profile == 1.0
    assert by_topic["b"].level == 100.0
    assert by_topic["b"].classification == "mastered"


def test_no_signal_at_all_counts_the_test_as_zero() -> None:
    result = estimate_levels(
        topic_ids=["a"], items=[], answers=[], weights=WEIGHTS, thresholds=THRESHOLDS
    )
    level = result.level_by_topic[0]
    assert level.test_score == 0.0
    assert level.weights.test == 1.0
    assert level.classification == "to_learn"


def test_flat_similarities_give_zero_priors() -> None:
    assert normalized_priors([0.3, 0.3, 0.3]) == [0.0, 0.0, 0.0]
    assert normalized_priors([0.1, 0.3]) == [0.0, 100.0]


def test_all_weights_missing_returns_none() -> None:
    weights = LevelWeights(test=0, profile=1, resume=0)
    assert applied_weights(weights, test=True, profile=False, resume=False) is None


answer_strategy = st.sampled_from(["hit", "miss", "dont_know", "none"])


@settings(max_examples=150, deadline=None)
@given(
    outcomes=st.lists(answer_strategy, min_size=0, max_size=9),
    sims=st.lists(st.floats(-1, 1), min_size=3, max_size=3),
    with_profile=st.booleans(),
    weights=st.tuples(st.integers(0, 10), st.integers(0, 10), st.integers(0, 10)).filter(
        lambda w: sum(w) > 0
    ),
)
def test_levels_are_valid_for_any_input(
    outcomes: list[str], sims: list[float], with_profile: bool, weights: tuple[int, int, int]
) -> None:
    topics = ["a", "b", "c"]
    items = [
        ScoredItem(f"i{n}", topics[n % 3], "multiple_choice", n % 3 + 1, correct_option=0)
        for n in range(len(outcomes))
    ]
    answers = []
    for n, kind in enumerate(outcomes):
        if kind == "hit":
            answers.append(LearnerAnswer(item_id=f"i{n}", selected_option=0))
        elif kind == "miss":
            answers.append(LearnerAnswer(item_id=f"i{n}", selected_option=2))
        elif kind == "dont_know":
            answers.append(LearnerAnswer(item_id=f"i{n}", dont_know=True))
    total = sum(weights)
    configured = LevelWeights(
        test=weights[0] / total,
        profile=weights[1] / total,
        resume=1 - (weights[0] + weights[1]) / total,
    )
    result = estimate_levels(
        topic_ids=topics,
        items=items,
        answers=answers,
        weights=configured,
        thresholds=THRESHOLDS,
        profile_similarity=dict(zip(topics, sims, strict=True)) if with_profile else None,
    )
    # The contract validators (weights add up to 1, classification, missing signals) passed.
    assert [t.topic_id for t in result.level_by_topic] == topics
    for level in result.level_by_topic:
        assert 0 <= level.level <= 100
        assert math.isclose(
            level.weights.test + level.weights.profile + level.weights.resume, 1, abs_tol=1e-6
        )
    assert 0 <= result.overall_score <= 100


@settings(max_examples=100, deadline=None)
@given(hits=st.integers(0, 3))
def test_more_hits_never_lower_the_test_score(hits: int) -> None:
    items = _items("t")

    def score(n: int) -> float:
        answers = [LearnerAnswer(item_id=i.item_id, selected_option=1) for i in items[:n]]
        value = score_items(["t"], items, answers)[0]["t"]
        assert value is not None
        return value

    if hits < 3:
        assert score(hits + 1) >= score(hits)
