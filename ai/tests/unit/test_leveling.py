"""``app/domain/leveling.py``: examples of the contract and properties (hypothesis)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import Settings
from app.domain.contracts.assessment import LearnerAnswer
from app.domain.contracts.diagnostic import LevelThresholds, LevelWeights
from app.domain.leveling import (
    ALGORITHM,
    DEFAULT_SIMILARITY_CEILING,
    DEFAULT_SIMILARITY_FLOOR,
    PriorScale,
    ScoredItem,
    absolute_priors,
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


# ---------- R-002: escala del prior (variante (c) de E4) ----------

# Hallazgo 1 del primer corte: 0,011 de diferencia entre las similitudes de dos temas.
FINDING = [0.611, 0.622]
ABSOLUTE = PriorScale(mode="absolute")


def test_finding_minmax_exaggerates_a_tiny_difference() -> None:
    assert PriorScale().priors(FINDING) == [0.0, 100.0]
    assert PriorScale(mode="minmax").priors(FINDING) == normalized_priors(FINDING)


def test_finding_absolute_keeps_a_tiny_difference_tiny() -> None:
    low, high = ABSOLUTE.priors(FINDING)
    assert low == pytest.approx(100 * 0.111 / 0.3)
    assert high == pytest.approx(100 * 0.122 / 0.3)
    assert high - low == pytest.approx(100 * 0.011 / 0.3)  # 3,7 puntos, no 100
    assert high - low < 4


def test_absolute_limits() -> None:
    assert absolute_priors([]) == []
    assert ABSOLUTE.priors([0.3, 0.3, 0.3]) == [0.0, 0.0, 0.0]  # iguales y bajo el piso
    assert ABSOLUTE.priors([0.65, 0.65]) == [pytest.approx(50.0)] * 2  # iguales, no se anulan
    assert ABSOLUTE.priors([0.7]) == [pytest.approx(200 / 3)]  # una sola: no depende de otras
    assert normalized_priors([0.7]) == [0.0]
    # Fuera de la banda (y del rango del coseno) se recorta a 0..100.
    assert ABSOLUTE.priors([-1.0, 0.2, 0.5, 0.8, 0.95, 1.5]) == [0.0, 0.0, 0.0, 100.0, 100.0, 100.0]
    assert absolute_priors([0.0, 0.5, 1.0], floor=0.0, ceiling=1.0) == [0.0, 50.0, 100.0]


def test_absolute_rejects_an_empty_band() -> None:
    with pytest.raises(ValueError, match="ceiling must be greater"):
        absolute_priors([0.5], floor=0.8, ceiling=0.8)
    with pytest.raises(ValueError, match="floor < ceiling"):
        PriorScale(mode="absolute", floor=0.8, ceiling=0.5)
    with pytest.raises(ValueError, match="floor < ceiling"):
        PriorScale(mode="absolute", floor=-2.0, ceiling=0.5)


@settings(max_examples=200, deadline=None)
@given(a=st.floats(-1, 1), b=st.floats(-1, 1))
def test_absolute_moves_the_prior_in_proportion_to_the_similarity(a: float, b: float) -> None:
    pa, pb = ABSOLUTE.priors([a, b])
    width = DEFAULT_SIMILARITY_CEILING - DEFAULT_SIMILARITY_FLOOR
    assert abs(pa - pb) <= 100 * abs(a - b) / width + 1e-9
    assert 0 <= pa <= 100 and 0 <= pb <= 100
    assert (pa <= pb) == (a <= b) or pa == pb


def _levels_with_profile(scale: PriorScale | None) -> dict[str, object]:
    result = estimate_levels(
        topic_ids=["a", "b", "c"],
        items=_items("a"),
        answers=[LearnerAnswer(item_id="a_2", selected_option=1)],
        weights=WEIGHTS,
        thresholds=THRESHOLDS,
        profile_similarity={"a": 0.611, "b": 0.622, "c": 0.4},
        resume_similarity={"a": 0.7, "b": 0.55, "c": 0.62},
        prior_scale=scale,
    )
    return result.model_dump()


def test_default_scale_does_not_change_the_current_output() -> None:
    current = _levels_with_profile(None)
    assert current == _levels_with_profile(PriorScale())
    assert current == _levels_with_profile(PriorScale(mode="minmax", floor=0.1, ceiling=0.2))
    assert current["algorithm"] == ALGORITHM == "weighted_difficulty v1"
    # Valores de la implementación anterior a R-002 (misma entrada, salida idéntica).
    by_topic = {t["topic_id"]: t for t in current["level_by_topic"]}  # type: ignore[attr-defined]
    assert [
        (t["profile_prior"], t["resume_prior"], t["level"], t["classification"])
        for t in by_topic.values()
    ] == [
        (95.0, 100.0, 46.1, "to_learn"),
        (100.0, 0.0, 50.0, "to_reinforce"),
        (0.0, 46.7, 23.4, "to_learn"),
    ]


def test_absolute_scale_in_the_levels() -> None:
    result = _levels_with_profile(ABSOLUTE)
    assert result["algorithm"] == "weighted_difficulty v1 (absolute prior 0.5-0.8)"
    by_topic = {t["topic_id"]: t for t in result["level_by_topic"]}  # type: ignore[attr-defined]
    assert by_topic["a"]["profile_prior"] == 37.0
    assert by_topic["b"]["profile_prior"] == 40.7
    assert by_topic["c"]["profile_prior"] == 0.0
    assert by_topic["a"]["resume_prior"] == pytest.approx(66.7)


def test_settings_default_to_minmax_with_the_domain_thresholds() -> None:
    configured = Settings()
    assert configured.ai_leveling_prior_scale == "minmax"
    assert configured.ai_leveling_similarity_floor == DEFAULT_SIMILARITY_FLOOR
    assert configured.ai_leveling_similarity_ceiling == DEFAULT_SIMILARITY_CEILING
    with pytest.raises(ValueError, match="AI_LEVELING_SIMILARITY_FLOOR"):
        Settings(ai_leveling_similarity_floor=0.8, ai_leveling_similarity_ceiling=0.5)


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
