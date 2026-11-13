"""D5f · La calidad de los videos que manda la API se traduce al modelo de la pantalla."""

import json
from typing import Any

import httpx
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.api import ApiClient
from clients.evaluation_adapter import video_quality_from_api
from clients.models_staff import VideoQuality

OPENAPI = REPO_ROOT / "docs" / "contracts" / "openapi-api.json"


def _video(video_id: int, topic_id: int, title: str) -> dict[str, Any]:
    return {
        "id": video_id,
        "topic_id": topic_id,
        "youtube_video_id": f"EXAMPLE000{video_id}",
        "url": f"https://www.youtube.com/watch?v=EXAMPLE000{video_id}",
        "title": title,
        "channel": None,
        "duration_seconds": 600,
        "language": "es",
        "has_captions": True,
        "characterization": None,
        "characterization_source": None,
        "similarity": 0.8,
        "rank": 1,
        "status": "in_use",
        "origin": "youtube_api",
        "relevance_judgment": True,
    }


# Una respuesta como la de `GET /learning-paths/7/video-quality`: uno medido y uno midiéndose.
API_QUALITY: dict[str, Any] = {
    "learning_path_id": 7,
    "min_ratings": 5,
    "items": [
        {
            "video": _video(1, 101, "Bases en 10 minutos"),
            "topic_name": "Bases",
            "ratings": 8,
            "by_rating": {"useful": 4, "audio_issue": 3, "too_long": 1},
            "watched_fully": 6,
            "useful_rate": 0.5,
            "quality_index": 0.5,
            "measuring": False,
            "status": "under_review",
        },
        {
            "video": _video(2, 102, "ETL paso a paso"),
            "topic_name": "ETL",
            "ratings": 2,
            "by_rating": {"useful": 2},
            "watched_fully": 1,
            "useful_rate": 1.0,
            "quality_index": None,
            "measuring": True,
            "status": "measuring",
        },
    ],
}


def test_the_sample_is_a_valid_api_response() -> None:
    """La muestra cumple el OpenAPI publicado: si la API cambia la respuesta, esto falla."""
    spec = json.loads(OPENAPI.read_text("utf-8"))
    schema = {"$ref": "#/components/schemas/VideoQualityResponse", **spec}
    errors = sorted(Draft202012Validator(schema).iter_errors(API_QUALITY), key=str)
    assert not errors, [e.message for e in errors]


def test_api_quality_becomes_the_screen_model() -> None:
    quality = VideoQuality.model_validate(video_quality_from_api(API_QUALITY))

    measured, measuring = quality.rows
    assert measured.topic_label == "Bases · Bases en 10 minutos"
    assert (measured.index, measured.status) == (50, "under_review")
    assert (measured.ratings_count, measured.ratings_needed) == (8, 5)
    assert measured.useful_rate == 0.5
    assert measured.rating_average is None and measured.quiz_effect_points is None
    assert measured.watched_fully_rate == 0.75  # 6 de 8
    assert measured.reports == 4  # las que no dicen «útil»

    assert (measuring.index, measuring.status) == (None, "measuring")

    # Solo el video con quejas trae etiquetas, de la más a la menos repetida.
    (feedback,) = quality.feedback
    assert feedback.video_candidate_id == 1
    assert [(lb.label, lb.count) for lb in feedback.labels] == [("audio_issue", 3), ("too_long", 1)]
    assert (feedback.comments, feedback.comments_total) == ([], 0)


def test_an_unknown_status_is_shown_as_measuring() -> None:
    data = json.loads(json.dumps(API_QUALITY))
    data["items"][0]["status"] = "algo_nuevo"
    quality = VideoQuality.model_validate(video_quality_from_api(data))
    assert quality.rows[0].status == "measuring"


def test_fixtures_pass_unchanged() -> None:
    fixture = json.loads(
        (REPO_ROOT / "app" / "tests" / "fixtures" / "staff" / "video_quality.json").read_text(
            "utf-8"
        )
    )
    assert video_quality_from_api(fixture) == fixture


@respx.mock
def test_the_http_client_reads_the_real_quality() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    respx.get(f"{base}/api/v1/learning-paths/7/video-quality").mock(
        return_value=httpx.Response(200, json=API_QUALITY)
    )
    quality = client.get_video_quality(7)
    assert quality.rows[0].status == "under_review"
