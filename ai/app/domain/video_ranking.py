"""Filters, score and backups of the video recommender (plan 5.4.9, ADR 0016, DEF-07).

Ranking is per topic and shared by every learner. For each candidate:

1. *Knowledge filters* (hard): duration inside ``[min, max]`` and a language the learner can
   follow. A video added by the instructor skips them (``trusted``): the instructor curates.
2. *Score* = cosine similarity with the topic (the base of the brief) + a language adjustment +
   a duration adjustment (the report of recommender systems, 4.2 of the plan). The weights are
   initial values, configurable (4.3: unvalidated parameters); they are small next to the
   similarity so the topic decides and language and duration break near ties.
3. The best candidate is selected and the next ones are backups (``backup_count``).

Pure functions, no I/O: tested without providers.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

MIN_DURATION_SECONDS = 240  # notebook v2: 4 minutes
MAX_DURATION_SECONDS = 1800  # notebook v2: 30 minutes (the report uses 40)
IDEAL_MIN_SECONDS = 480
IDEAL_MAX_SECONDS = 1200
UNKNOWN_SCORE = 0.5

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


@dataclass(frozen=True)
class RankingPreferences:
    language: str = "es"
    min_duration_seconds: int = MIN_DURATION_SECONDS
    max_duration_seconds: int = MAX_DURATION_SECONDS
    ideal_min_seconds: int = IDEAL_MIN_SECONDS
    ideal_max_seconds: int = IDEAL_MAX_SECONDS
    english_allowed: bool = False
    language_weight: float = 0.05
    duration_weight: float = 0.05
    backup_count: int = 2
    max_candidates: int = 10


@dataclass(frozen=True)
class Rankable:
    video_id: str
    similarity: float
    language: str | None
    duration_seconds: int | None
    trusted: bool = False  # added by the instructor


@dataclass(frozen=True)
class Ranked:
    video_id: str
    similarity: float
    language_score: float
    duration_score: float
    score: float


def parse_iso_duration(value: str) -> int | None:
    """Seconds of an ISO 8601 duration as YouTube returns it (``PT4M13S``); ``None`` if invalid."""
    match = _ISO_DURATION.match(value)
    if match is None or not any(match.groupdict().values()):
        return None
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    return (
        parts.get("days", 0) * 86400
        + parts.get("hours", 0) * 3600
        + parts.get("minutes", 0) * 60
        + parts.get("seconds", 0)
    )


def exclusion_reason(video: Rankable, prefs: RankingPreferences) -> str | None:
    """Why the knowledge filters drop a video (``None`` = it stays)."""
    if video.trusted:
        return None
    if video.duration_seconds is not None and not (
        prefs.min_duration_seconds <= video.duration_seconds <= prefs.max_duration_seconds
    ):
        return "duration_out_of_range"
    allowed = {prefs.language} | ({"en"} if prefs.english_allowed else set())
    if video.language is not None and video.language not in allowed:
        return "language_not_understood"
    return None


def language_score(language: str | None, prefs: RankingPreferences) -> float:
    """1 for the preferred language, 0.3 for English when allowed, 0.5 when unknown, else 0."""
    if language is None:
        return UNKNOWN_SCORE
    if language == prefs.language:
        return 1.0
    return 0.3 if prefs.english_allowed and language == "en" else 0.0


def duration_score(seconds: int | None, prefs: RankingPreferences) -> float:
    """1 inside the ideal band, falling linearly to 0 at the limits; 0.5 when unknown."""
    if seconds is None:
        return UNKNOWN_SCORE
    if prefs.ideal_min_seconds <= seconds <= prefs.ideal_max_seconds:
        return 1.0
    if seconds < prefs.ideal_min_seconds:
        span = prefs.ideal_min_seconds - prefs.min_duration_seconds
        return max(0.0, (seconds - prefs.min_duration_seconds) / span) if span > 0 else 0.0
    span = prefs.max_duration_seconds - prefs.ideal_max_seconds
    return max(0.0, (prefs.max_duration_seconds - seconds) / span) if span > 0 else 0.0


def score_video(video: Rankable, prefs: RankingPreferences) -> Ranked:
    lang = language_score(video.language, prefs)
    dur = duration_score(video.duration_seconds, prefs)
    total = video.similarity + prefs.language_weight * lang + prefs.duration_weight * dur
    return Ranked(video.video_id, video.similarity, lang, dur, round(total, 6))


def rank_videos(
    videos: Sequence[Rankable], prefs: RankingPreferences
) -> tuple[list[Ranked], dict[str, str]]:
    """Ranked candidates (best first, at most ``max_candidates``) and the excluded ones.

    Ties are broken by similarity and then by id, so the order is deterministic.
    """
    kept: list[Ranked] = []
    excluded: dict[str, str] = {}
    for video in videos:
        if reason := exclusion_reason(video, prefs):
            excluded[video.video_id] = reason
        else:
            kept.append(score_video(video, prefs))
    kept.sort(key=lambda r: (-r.score, -r.similarity, r.video_id))
    return kept[: prefs.max_candidates], excluded


def select_with_backups(
    ranked: Sequence[Ranked], backup_count: int
) -> tuple[str | None, list[str]]:
    """The first video and the next ``backup_count`` as backups (top 3 for the instructor)."""
    if not ranked:
        return None, []
    return ranked[0].video_id, [r.video_id for r in ranked[1 : 1 + backup_count]]
