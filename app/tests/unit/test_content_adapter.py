"""D5 · Los recursos y los ítems de la API se traducen a los modelos de la pantalla."""

import json
from typing import Any

import httpx
import pytest
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.api import ApiClient
from clients.content_adapter import item_from_api, item_patch_for_api, resource_from_api
from clients.models_staff import ItemPatch, Resource, ReviewItem

OPENAPI = json.loads((REPO_ROOT / "docs" / "contracts" / "openapi-api.json").read_text("utf-8"))
BASE = "http://api.test"

EXPLANATION: dict[str, Any] = {
    "id": 5,
    "topic_id": 101,
    "resource_type": "text",
    "kind": "main",
    "audience": "all_learners",
    "version": 1,
    "version_label": "1.0",
    "review_status": "pending_review",
    "url": None,
    "content": {
        "title": "Arquitecturas de almacenamiento",
        "sections": [{"heading": "Idea", "body": "Un data warehouse integra datos [1]."}],
        "worked_example": "Ejemplo",
        "summary": "Resumen",
        "reflection_questions": [],
        "gaps_detected": [],
        "sources": [
            {
                "n": 1,
                "source_id": "12",
                "title": "Syllabus del curso (s.pdf)",
                "url": "",
                "license": None,
            }
        ],
    },
    "faithfulness": 0.82,
    "unsupported_claims": [],
    "sources": [
        {
            "n": 1,
            "source_id": "12",
            "title": "Syllabus del curso (s.pdf)",
            "url": "",
            "license": None,
        }
    ],
    "prompt_version": "topic_explanation 1",
    "edited_by_user_id": None,
    "video_candidate_id": None,
    "created_at": "2026-11-11T18:17:16Z",
    "updated_at": "2026-11-11T18:17:16Z",
}

ITEM: dict[str, Any] = {
    "id": 9,
    "topic_id": 101,
    "learning_outcome_id": 3,
    "source": "topic_quiz",
    "item_type": "short_answer",
    "bloom_level": "apply",
    "difficulty": 2,
    "stem": "Explica la diferencia entre ETL y ELT.",
    "options": None,
    "correct_option": None,
    "model_answer": "En ETL se transforma antes de cargar.",
    "rubric": [
        {"criterion": "Define ETL", "points": 0.5},
        {"criterion": "Define ELT", "points": 0.5},
    ],
    "equivalence_group": None,
    "review_status": "pending_review",
    "auto_review": {
        "item_id": "i-1",
        "single_correct_answer": True,
        "clear_stem": False,
        "bloom_matches": True,
        "aligned_with_outcome": True,
        "issues": ["El enunciado es ambiguo"],
    },
    "prompt_version": "topic_quiz 1",
    "created_at": "2026-11-11T18:15:18Z",
    "updated_at": "2026-11-11T18:15:18Z",
}


@pytest.mark.parametrize(
    ("sample", "schema"), [(EXPLANATION, "ResourceResponse"), (ITEM, "ItemResponse")]
)
def test_samples_follow_the_published_openapi(sample: dict[str, Any], schema: str) -> None:
    """Si la API cambia estas respuestas, la muestra deja de validar y la prueba avisa."""
    validator = Draft202012Validator({"$ref": f"#/components/schemas/{schema}", **OPENAPI})
    assert not [e.message for e in validator.iter_errors(sample)]


def test_api_explanation_becomes_a_screen_resource() -> None:
    resource = Resource.model_validate(resource_from_api(EXPLANATION))
    assert (resource.kind, resource.title, resource.version) == (
        "explanation",
        "Arquitecturas de almacenamiento",
        "1.0",
    )
    assert resource.sources == ["Syllabus del curso (s.pdf)"]
    assert resource.content is not None
    assert resource.content["sections"][0]["heading"] == "Idea"


def test_remedial_and_video_kinds() -> None:
    remedial = Resource.model_validate(resource_from_api({**EXPLANATION, "kind": "remedial"}))
    assert remedial.kind == "alternate_explanation"
    video = Resource.model_validate(
        resource_from_api({**EXPLANATION, "resource_type": "video", "content": None})
    )
    assert (video.kind, video.title, video.content) == ("video", "Video del tema", None)


def test_api_item_becomes_a_screen_item() -> None:
    item = ReviewItem.model_validate(item_from_api(ITEM))
    assert item.source == "llm"
    assert item.rubric == ["Define ETL", "Define ELT"]
    assert item.options == []
    assert item.auto_review is not None
    assert item.auto_review.issues == ["El enunciado es ambiguo"]
    written = ReviewItem.model_validate(item_from_api({**ITEM, "prompt_version": None}))
    assert written.source == "instructor"


def test_rubric_edits_travel_as_criteria() -> None:
    body = item_patch_for_api({"rubric": ["Define ETL", "Define ELT"]})
    assert body["rubric"] == [
        {"criterion": "Define ETL", "points": 0.5},
        {"criterion": "Define ELT", "points": 0.5},
    ]
    assert item_patch_for_api({"stem": "x"}) == {"stem": "x"}


@respx.mock
def test_the_http_client_reads_and_updates_real_content() -> None:
    client = ApiClient(BASE, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=BASE))
    respx.get(f"{BASE}/api/v1/topics/101/resources").mock(
        return_value=httpx.Response(200, json=[EXPLANATION])
    )
    page = {"items": [ITEM], "total": 1, "limit": 100, "offset": 0}
    respx.get(f"{BASE}/api/v1/topics/101/items").mock(return_value=httpx.Response(200, json=page))
    approved = {**EXPLANATION, "review_status": "approved"}
    respx.patch(f"{BASE}/api/v1/resources/5/review").mock(
        return_value=httpx.Response(200, json=approved)
    )
    patch_route = respx.patch(f"{BASE}/api/v1/items/9").mock(
        return_value=httpx.Response(200, json={**ITEM, "review_status": "approved"})
    )

    assert client.list_topic_resources(101)[0].title == "Arquitecturas de almacenamiento"
    assert client.list_topic_items(101).items[0].rubric == ["Define ETL", "Define ELT"]
    assert client.review_resource(5, "approved").review_status == "approved"
    updated = client.update_item(9, ItemPatch(review_status="approved", rubric=["Solo uno"]))
    assert updated.review_status == "approved"
    sent = json.loads(patch_route.calls.last.request.content)
    assert sent["rubric"] == [{"criterion": "Solo uno", "points": 1.0}]
