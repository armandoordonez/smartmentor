"""D5b · La cola de anotación que manda la API se traduce al modelo de la pantalla."""

import json
from typing import Any

import httpx
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.api import ApiClient
from clients.evaluation_adapter import annotation_queue_from_api
from clients.models_staff import AnnotationQueue

OPENAPI = REPO_ROOT / "docs" / "contracts" / "openapi-api.json"


def _item(item_id: int, **extra: Any) -> dict[str, Any]:
    base = {
        "id": item_id,
        "topic_id": 103,
        "topic_name": "Regresión logística",
        "learning_outcome_id": None,
        "source": "topic_quiz",
        "item_type": "multiple_choice",
        "bloom_level": "apply",
        "difficulty": 2,
        "stem": "¿Qué harías con el umbral de decisión?",
        "options": ["Subirlo", "Bajarlo", "Dejarlo", "Quitar variables"],
        "correct_option": 0,
        "model_answer": None,
        "rubric": None,
        "review_status": "approved",
        "own_annotation": None,
        "evaluator_slot": 1,
    }
    return {**base, **extra}


# Una respuesta como la de `GET /evaluation/annotation-queue?course_id=3`.
API_QUEUE: dict[str, Any] = {
    "items": [
        _item(701),
        _item(702, evaluator_slot=2, options=[{"text": "Sí"}, {"text": "No"}]),
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
    "annotated": 3,
}


def test_the_sample_is_a_valid_api_response() -> None:
    """La muestra cumple el OpenAPI publicado: si la API cambia la cola, esto falla."""
    spec = json.loads(OPENAPI.read_text("utf-8"))
    schema = {"$ref": "#/components/schemas/AnnotationQueuePage", **spec}
    errors = sorted(Draft202012Validator(schema).iter_errors(API_QUEUE), key=str)
    assert not errors, [e.message for e in errors]


def test_api_queue_becomes_the_screen_model() -> None:
    queue = AnnotationQueue.model_validate(annotation_queue_from_api(API_QUEUE))

    assert (queue.annotated, queue.total) == (3, 5)  # 3 anotados + 2 pendientes
    first, second = queue.items
    assert (first.item_id, first.topic_name) == (701, "Regresión logística")
    assert first.bloom_level == "apply"
    # La opción 0 es una respuesta válida: no se pierde por ser «falsa».
    assert first.correct_option == 0
    assert (first.evaluator_slot, first.evaluator_slots_total) == (1, 2)
    assert second.options == ["Sí", "No"]
    assert second.evaluator_slot == 2


def test_items_without_a_free_slot_or_already_annotated_are_not_offered() -> None:
    data = json.loads(json.dumps(API_QUEUE))
    data["items"][0]["evaluator_slot"] = None
    data["items"][1]["own_annotation"] = {"id": 1}
    queue = AnnotationQueue.model_validate(annotation_queue_from_api(data))
    assert queue.items == []


def test_fixtures_pass_unchanged() -> None:
    fixture = json.loads(
        (REPO_ROOT / "app" / "tests" / "fixtures" / "staff" / "annotation_queue.json").read_text(
            "utf-8"
        )
    )
    assert annotation_queue_from_api(fixture) == fixture


@respx.mock
def test_the_http_client_reads_the_real_queue() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    route = respx.get(f"{base}/api/v1/evaluation/annotation-queue").mock(
        return_value=httpx.Response(200, json=API_QUEUE)
    )
    queue = client.get_annotation_queue(3)
    assert route.calls.last.request.url.params["course_id"] == "3"
    assert queue.items[0].topic_name == "Regresión logística"
