"""Video del tema según el nivel de inglés del aprendiz (R-001)."""

from typing import Any

import pytest

from app.domains.ai_gateway.fake import FakeAiService
from app.domains.ai_gateway.fake_learning import fake_video_rank
from app.domains.assessments.video_choice import (
    english_allowed,
    language_code,
    pick_video,
    rank_input,
)


def video(n: int, language: str | None, status: str = "backup") -> dict[str, Any]:
    return {
        "video_candidate_id": n,
        "youtube_video_id": f"VIDEO{n:06d}",
        "title": f"Video {n}",
        "channel": "Canal",
        "duration_seconds": 600,
        "language": language,
        "has_captions": None,
        "characterization": "regresión",
        "characterization_source": "transcript",
        "similarity": 0.8,
        "origin": "youtube_api",
        "status": status,
    }


ENGLISH_FIRST = [video(1, "en", "in_use"), video(2, "es"), video(3, "en")]


def recording_ai() -> tuple[FakeAiService, list[dict[str, Any]]]:
    ai = FakeAiService()
    calls: list[dict[str, Any]] = []

    def rank(input_: dict[str, Any]) -> dict[str, Any]:
        calls.append(input_)
        return fake_video_rank(input_)

    ai.task_results["video.rank"] = rank
    return ai, calls


@pytest.mark.parametrize(
    ("languages", "expected"),
    [
        ([{"code": "en", "cefr_level": "B1"}], True),
        ([{"code": "es", "cefr_level": "C2"}, {"code": "en", "cefr_level": "C1"}], True),
        ([{"code": "EN-us", "cefr_level": "b2"}], True),
        ([{"code": "en", "cefr_level": "A2"}], False),
        ([{"code": "fr", "cefr_level": "C2"}], False),
        ([], False),
        (None, False),
        (["en"], False),
    ],
)
def test_english_needs_b1_or_more(languages: list[Any] | None, expected: bool) -> None:
    assert english_allowed(languages) is expected


def test_language_code_keeps_two_letters() -> None:
    assert language_code("es-419") == "es"
    assert language_code("EN") == "en"
    assert language_code(None) is None
    assert language_code("1") is None


async def test_b1_learner_gets_the_topic_video_without_calling_ai() -> None:
    ai, calls = recording_ai()
    chosen = await pick_video(ai, 12, ENGLISH_FIRST, allow_english=True)
    assert chosen is not None
    assert chosen["video_candidate_id"] == 1
    assert chosen["is_backup"] is False
    assert calls == []


async def test_learner_without_english_gets_the_spanish_video_from_video_rank() -> None:
    ai, calls = recording_ai()
    chosen = await pick_video(ai, 12, ENGLISH_FIRST, allow_english=False)
    assert chosen == {
        "video_candidate_id": 2,
        "youtube_video_id": "VIDEO000002",
        "title": "Video 2",
        "duration_seconds": 600,
        "is_backup": True,
    }
    assert len(calls) == 1
    assert calls[0]["topic_id"] == "12"
    assert calls[0]["preferences"] == {"language": "es", "english_allowed": False}
    assert [c["youtube_video_id"] for c in calls[0]["candidates"]] == [
        "VIDEO000001",
        "VIDEO000002",
        "VIDEO000003",
    ]


async def test_a_spanish_topic_video_needs_no_ranking() -> None:
    ai, calls = recording_ai()
    videos = [video(4, "es", "in_use"), video(5, "en")]
    chosen = await pick_video(ai, 12, videos, allow_english=False)
    assert chosen is not None
    assert chosen["video_candidate_id"] == 4
    assert calls == []


async def test_only_english_videos_keep_the_topic_video() -> None:
    ai, _ = recording_ai()
    videos = [video(1, "en", "in_use"), video(3, "en")]
    chosen = await pick_video(ai, 12, videos, allow_english=False)
    assert chosen is not None
    assert chosen["video_candidate_id"] == 1


async def test_ai_down_keeps_the_topic_video() -> None:
    ai = FakeAiService()
    ai.unavailable = True
    chosen = await pick_video(ai, 12, ENGLISH_FIRST, allow_english=False)
    assert chosen is not None
    assert chosen["video_candidate_id"] == 1


async def test_an_invalid_ai_result_keeps_the_topic_video() -> None:
    ai = FakeAiService()
    ai.task_results["video.rank"] = lambda _: {"unexpected": True}
    chosen = await pick_video(ai, 12, ENGLISH_FIRST, allow_english=False)
    assert chosen is not None
    assert chosen["video_candidate_id"] == 1


async def test_no_videos_means_no_video() -> None:
    ai, calls = recording_ai()
    assert await pick_video(ai, 12, [], allow_english=False) is None
    assert calls == []


def test_rank_input_follows_the_ai_contract() -> None:
    raw = video(1, "es-419") | {"characterization_source": "otro", "similarity": None}
    body = rank_input(7, [raw], allow_english=True)
    candidate = body["candidates"][0]
    assert candidate["language"] == "es"
    assert candidate["characterization_source"] is None
    assert candidate["similarity"] is None
    assert candidate["url"] == "https://www.youtube.com/watch?v=VIDEO000001"
    assert body["preferences"]["english_allowed"] is True
