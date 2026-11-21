"""D5c y D6b · Videos y calificación humana de la API se traducen a los modelos de las pantallas."""

import json
from typing import Any

import httpx
import pytest
import respx
from jsonschema import Draft202012Validator
from support import FIXTURES_DIR, REPO_ROOT

from clients.api import ApiClient
from clients.evaluation_adapter import (
    grading_queue_from_api,
    grading_result_from_api,
    topic_videos_from_api,
)
from clients.models_staff import (
    GradingQueue,
    HumanCriterion,
    HumanGradingBody,
    HumanGradingResult,
    TopicVideos,
)

OPENAPI = json.loads((REPO_ROOT / "docs" / "contracts" / "openapi-api.json").read_text("utf-8"))
BASE = "http://api.test"

VIDEO: dict[str, Any] = {
    "id": 4,
    "topic_id": 101,
    "youtube_video_id": "abc123XYZ00",
    "url": "https://www.youtube.com/watch?v=abc123XYZ00",
    "title": "Esquema estrella en 10 minutos",
    "channel": "Datos Claros",
    "duration_seconds": 640,
    "language": "es",
    "has_captions": True,
    "characterization": "Explica tablas de hechos y dimensiones",
    "characterization_source": "metadata",
    "similarity": 0.81,
    "rank": 1,
    "search_position": 3,
    "status": "in_use",
    "origin": "youtube_api",
    "relevance_judgment": None,
}
VIDEOS: dict[str, Any] = {
    "topic_id": 101,
    "topic_name": "Arquitecturas y Modelos de Almacenamiento de Datos",
    "has_backup": False,
    "candidates": [VIDEO, {**VIDEO, "id": 5, "origin": "instructor", "duration_seconds": None}],
}
QUEUE: dict[str, Any] = {
    "items": [
        {
            "attempt_answer_id": 77,
            "item_id": 9,
            "topic_id": 102,
            "topic_name": "ETL",
            "stem": "Explica la diferencia entre ETL y ELT.",
            "model_answer": "En ETL se transforma antes de cargar.",
            "rubric": [
                {"criterion": "Define ETL", "points": 0.5},
                {"criterion": "Define ELT", "points": 0.5},
            ],
            "text_answer": "ETL transforma primero.",
            "review_requested_at": None,
        }
    ],
    "total": 3,
    "limit": 20,
    "offset": 0,
    "graded": 2,
}
GRADING_V1: dict[str, Any] = {
    "item_id": "q5",
    "item_type": "short_answer",
    "grader": "llm_judge",
    "approval_rule": "min_criteria_ratio",
    "min_criteria_ratio": 0.6667,
    "score": 50.0,
    "is_correct": False,
    "criteria_met": 1,
    "criteria_total": 2,
    "rubric_detail": [
        {
            "criterion": "Define ETL",
            "met": True,
            "points": 0.5,
            "points_awarded": 0.5,
            "reason": "Se cumple: define ETL.",
            "evidence": "ETL transforma primero",
        },
        {
            "criterion": "Define ELT",
            "met": False,
            "points": 0.5,
            "points_awarded": 0,
            "reason": "No se cumple: no menciona ELT.",
            "evidence": "",
        },
    ],
    "feedback": "Falta definir ELT.",
}
RESULT: dict[str, Any] = {
    "id": 1,
    "attempt_answer_id": 77,
    "sample_type": "random",
    "criteria": [
        {"criterion": "Define ETL", "met": True, "points_awarded": 1},
        {"criterion": "Define ELT", "met": False, "points_awarded": 0},
    ],
    "score": 50,
    "llm_grading": {
        "score": 50.0,
        "is_correct": False,
        "feedback": "Falta definir ELT.",
        # La API devuelve `grading.v1` sin `meta` como objeto, no como lista.
        "rubric_detail": GRADING_V1,
    },
    "created_at": "2026-11-11T18:40:00Z",
}


@pytest.mark.parametrize(
    ("sample", "schema"),
    [
        (VIDEOS, "VideoListResponse"),
        (VIDEO, "VideoResponse"),
        (QUEUE, "GradingQueuePage"),
        (RESULT, "HumanGradingResponse"),
    ],
)
def test_samples_follow_the_published_openapi(sample: dict[str, Any], schema: str) -> None:
    validator = Draft202012Validator({"$ref": f"#/components/schemas/{schema}", **OPENAPI})
    assert not [e.message for e in validator.iter_errors(sample)]


def test_api_videos_become_the_screen_model() -> None:
    videos = TopicVideos.model_validate(topic_videos_from_api(VIDEOS))
    assert videos.topic_name.startswith("Arquitecturas")
    first, added = videos.candidates
    assert (first.has_subtitles, first.relevance, first.origin) == (True, 0.81, "youtube")
    assert (added.origin, added.duration_seconds) == ("instructor", 0)


def test_grading_queue_counts_what_is_done_and_what_is_left() -> None:
    queue = GradingQueue.model_validate(grading_queue_from_api(QUEUE, "random"))
    assert (queue.sample_done, queue.sample_total, queue.learner_requests) == (2, 5, 0)
    answer = queue.items[0]
    assert (answer.code, answer.topic_name, answer.answer) == (
        "77",
        "ETL",
        "ETL transforma primero.",
    )
    assert answer.criteria == ["Define ETL", "Define ELT"]
    requests = GradingQueue.model_validate(grading_queue_from_api(QUEUE, "learner_request"))
    assert requests.learner_requests == 3


def test_grading_result_reads_the_grading_v1_object() -> None:
    result = HumanGradingResult.model_validate(grading_result_from_api(RESULT))
    assert (result.llm_criteria_met, result.llm_criteria_total) == (1, 2)
    assert result.llm_rationale == "Falta definir ELT."
    assert result.agrees is True
    # La API no entrega la versión del prompt en este endpoint: se muestra «—», no vacío.
    assert result.prompt_version == "—"


def test_grading_result_counts_come_from_the_object_when_present() -> None:
    llm = {**RESULT["llm_grading"], "rubric_detail": {**GRADING_V1, "criteria_met": 2}}
    result = HumanGradingResult.model_validate(
        grading_result_from_api({**RESULT, "llm_grading": llm})
    )
    assert (result.llm_criteria_met, result.llm_criteria_total) == (2, 2)


def test_grading_result_takes_the_prompt_version_from_meta_when_the_api_sends_it() -> None:
    meta = {"prompt_id": "short_answer_grading", "prompt_version": "v2"}
    llm = {**RESULT["llm_grading"], "rubric_detail": {**GRADING_V1, "meta": meta}}
    result = HumanGradingResult.model_validate(
        grading_result_from_api({**RESULT, "llm_grading": llm})
    )
    assert result.prompt_version == "short_answer_grading v2"


def test_grading_result_still_reads_the_old_list_shape() -> None:
    llm = {**RESULT["llm_grading"], "rubric_detail": GRADING_V1["rubric_detail"]}
    result = HumanGradingResult.model_validate(
        grading_result_from_api({**RESULT, "llm_grading": llm})
    )
    assert (result.llm_criteria_met, result.llm_criteria_total, result.agrees) == (1, 2, True)


def test_grading_result_differs_when_a_verdict_is_not_the_same() -> None:
    # Mismo total de criterios cumplidos (1 y 1), pero en criterios distintos: no coincide.
    swapped = {
        **RESULT,
        "criteria": [
            {"criterion": "Define ETL", "met": False, "points_awarded": 0},
            {"criterion": "Define ELT", "met": True, "points_awarded": 1},
        ],
    }
    assert HumanGradingResult.model_validate(grading_result_from_api(swapped)).agrees is False
    fewer = {
        **RESULT,
        "criteria": [{"criterion": "Define ETL", "met": False, "points_awarded": 0}],
    }
    assert HumanGradingResult.model_validate(grading_result_from_api(fewer)).agrees is False
    all_met = {
        **RESULT,
        "criteria": [
            {"criterion": "Define ETL", "met": True, "points_awarded": 1},
            {"criterion": "Define ELT", "met": True, "points_awarded": 1},
        ],
    }
    assert HumanGradingResult.model_validate(grading_result_from_api(all_met)).agrees is False


def test_staff_fixture_has_the_shape_of_the_api() -> None:
    sample = json.loads((FIXTURES_DIR / "staff" / "human_grading_result.json").read_text("utf-8"))
    validator = Draft202012Validator(
        {"$ref": "#/components/schemas/HumanGradingResponse", **OPENAPI}
    )
    assert not [e.message for e in validator.iter_errors(sample)]
    assert isinstance(sample["llm_grading"]["rubric_detail"], dict)
    result = HumanGradingResult.model_validate(grading_result_from_api(sample))
    assert (result.llm_criteria_met, result.llm_criteria_total) == (2, 3)
    assert result.agrees is True


@respx.mock
def test_the_http_client_reads_videos_and_grades() -> None:
    client = ApiClient(BASE, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=BASE))
    respx.get(f"{BASE}/api/v1/topics/101/video-candidates").mock(
        return_value=httpx.Response(200, json=VIDEOS)
    )
    respx.patch(f"{BASE}/api/v1/video-candidates/4").mock(
        return_value=httpx.Response(200, json={**VIDEO, "status": "backup"})
    )
    respx.get(f"{BASE}/api/v1/evaluation/grading-queue").mock(
        return_value=httpx.Response(200, json=QUEUE)
    )
    graded = respx.post(f"{BASE}/api/v1/attempt-answers/77/human-gradings").mock(
        return_value=httpx.Response(201, json=RESULT)
    )

    assert client.list_video_candidates(101).candidates[0].title.startswith("Esquema")
    assert client.update_video_candidate(4, status="backup", is_relevant=None).status == "backup"
    assert client.get_grading_queue("random").sample_total == 5
    body = HumanGradingBody(
        criteria=[HumanCriterion(criterion="Define ETL", met=True, points_awarded=1)],
        score=50,
        sample_type="random",
    )
    assert client.grade_answer(77, body).llm_criteria_total == 2
    assert json.loads(graded.calls.last.request.content)["sample_type"] == "random"
