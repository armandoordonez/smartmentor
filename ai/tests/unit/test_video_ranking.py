"""Filters, score and backups of the video recommender (plan 5.4.9, ADR 0016)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.application.video.characterize import covered_subtopics, normalize
from app.domain.video_ranking import (
    Rankable,
    RankingPreferences,
    duration_score,
    exclusion_reason,
    language_score,
    parse_iso_duration,
    rank_videos,
    select_with_backups,
)

PREFS = RankingPreferences()


def video(
    video_id: str,
    similarity: float,
    *,
    language: str | None = "es",
    seconds: int | None = 600,
    trusted: bool = False,
) -> Rankable:
    return Rankable(video_id, similarity, language, seconds, trusted)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("PT4M13S", 253), ("PT1H", 3600), ("PT1H2M3S", 3723), ("P1DT1S", 86401), ("PT45S", 45)],
)
def test_iso_durations_are_parsed(value: str, seconds: int) -> None:
    assert parse_iso_duration(value) == seconds


@pytest.mark.parametrize("value", ["", "P", "PT", "4:13", "abc"])
def test_invalid_durations_are_none(value: str) -> None:
    assert parse_iso_duration(value) is None


def test_duration_outside_the_range_is_excluded() -> None:
    assert exclusion_reason(video("a", 0.5, seconds=100), PREFS) == "duration_out_of_range"
    assert exclusion_reason(video("a", 0.5, seconds=3600), PREFS) == "duration_out_of_range"
    assert exclusion_reason(video("a", 0.5, seconds=600), PREFS) is None


def test_english_is_excluded_unless_allowed() -> None:
    english = video("a", 0.5, language="en")
    assert exclusion_reason(english, PREFS) == "language_not_understood"
    assert exclusion_reason(english, RankingPreferences(english_allowed=True)) is None
    french = video("b", 0.5, language="fr")
    assert exclusion_reason(french, RankingPreferences(english_allowed=True)) is not None


def test_unknown_language_and_duration_are_kept() -> None:
    assert exclusion_reason(video("a", 0.5, language=None, seconds=None), PREFS) is None


def test_the_instructor_videos_skip_the_filters() -> None:
    assert (
        exclusion_reason(video("a", 0.1, language="en", seconds=7200, trusted=True), PREFS) is None
    )


def test_language_and_duration_scores() -> None:
    assert language_score("es", PREFS) == 1.0
    assert language_score(None, PREFS) == 0.5
    assert language_score("en", PREFS) == 0.0
    assert language_score("en", RankingPreferences(english_allowed=True)) == 0.3
    assert duration_score(600, PREFS) == 1.0
    assert duration_score(240, PREFS) == 0.0
    assert duration_score(1800, PREFS) == 0.0
    assert 0 < duration_score(360, PREFS) < 1
    assert duration_score(None, PREFS) == 0.5


def test_similarity_decides_and_adjustments_break_ties() -> None:
    ranked, _ = rank_videos(
        [
            video("far", 0.30, seconds=600),
            video("near_long", 0.60, seconds=1700),
            video("near_ideal", 0.60, seconds=600),
        ],
        PREFS,
    )
    assert [r.video_id for r in ranked] == ["near_ideal", "near_long", "far"]


def test_excluded_videos_are_reported_and_not_ranked() -> None:
    ranked, excluded = rank_videos(
        [video("ok", 0.4), video("short", 0.9, seconds=30), video("en", 0.9, language="en")], PREFS
    )
    assert [r.video_id for r in ranked] == ["ok"]
    assert excluded == {"short": "duration_out_of_range", "en": "language_not_understood"}


def test_at_most_max_candidates_are_kept() -> None:
    videos = [video(f"v{n:02d}", n / 100) for n in range(30)]
    ranked, _ = rank_videos(videos, PREFS)
    assert len(ranked) == PREFS.max_candidates
    assert ranked[0].video_id == "v29"


def test_top_three_are_the_selected_video_and_two_backups() -> None:
    ranked, _ = rank_videos([video(f"v{n}", n / 10) for n in range(5)], PREFS)
    assert select_with_backups(ranked, 2) == ("v4", ["v3", "v2"])
    assert select_with_backups([], 2) == (None, [])


@given(
    st.lists(
        st.tuples(st.floats(-1, 1), st.integers(1, 10_000), st.sampled_from(["es", "en", None])),
        max_size=25,
    )
)
def test_ranking_is_deterministic_and_sorted(rows: list[tuple[float, int, str | None]]) -> None:
    videos = [
        video(f"v{i:02d}", sim, language=lang, seconds=sec)
        for i, (sim, sec, lang) in enumerate(rows)
    ]
    first, _ = rank_videos(videos, PREFS)
    second, _ = rank_videos(list(reversed(videos)), PREFS)
    assert first == second
    assert [r.score for r in first] == sorted((r.score for r in first), reverse=True)


# ---------- characterisation ----------


def test_normalize_removes_accents_and_case() -> None:
    assert normalize("Regresión LINEAL") == "regresion lineal"


def test_covered_subtopics_come_from_the_closed_list() -> None:
    subtopics = ["Función sigmoide", "Umbral de decisión", "Regularización L2", "Log-loss"]
    evidence = "Vemos la función sigmoide y el umbral de decisión. Sin hablar de otras cosas."
    assert covered_subtopics(subtopics, evidence) == ["Función sigmoide", "Umbral de decisión"]
    assert covered_subtopics(subtopics, "Solo la sigmoide, sin la palabra completa") == []


def test_plural_and_accents_still_match() -> None:
    assert covered_subtopics(["Regresión"], "Aprende regresiones paso a paso") == ["Regresión"]


def test_nothing_covered_gives_an_empty_list() -> None:
    assert covered_subtopics(["Fuga de datos"], "Receta de cocina rápida") == []
