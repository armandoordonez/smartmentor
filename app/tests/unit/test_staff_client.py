"""Fixtures y cliente HTTP de las operaciones del instructor y del administrador."""

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel, ConfigDict
from support import FIXTURES_DIR

from clients.api import ApiClient
from clients.base import ApiError
from clients.evaluation_adapter import grading_result_from_api
from clients.fixtures import FixturesClient
from clients.models import Job, JobAccepted, Page
from clients.models_staff import (
    AdminEnrollment,
    AdminUser,
    AnnotationQueue,
    AttemptGrant,
    Course,
    CourseCreate,
    CourseEvaluator,
    CourseMaterial,
    CourseTopics,
    Dashboard,
    ExtractionMetrics,
    GradingQueue,
    LearnerDetail,
    LlmCallLog,
    LlmSummary,
    MetricsEvaluation,
    Resource,
    ReviewItem,
    TopicGraphDoc,
    TopicVideos,
    VideoQuality,
)
from clients.models_staff import CourseTopic as TopicModel

STAFF_DIR = FIXTURES_DIR / "staff"

MODELS: dict[str, Any] = {
    "courses": Page[Course],
    "admin_courses": Page[Course],
    "course": Course,
    "course_new": Course,
    "job_accepted": JobAccepted,
    "material": CourseMaterial,
    "job_running": Job,
    "job_succeeded": Job,
    "job_failed": Job,
    "topics": CourseTopics,
    "topic": TopicModel,
    "topic_graph": TopicGraphDoc,
    "extraction_metrics": ExtractionMetrics,
    "dashboard": Dashboard,
    "learner_detail": LearnerDetail,
    "video_candidates": TopicVideos,
    "video_quality": VideoQuality,
    "annotation_queue": AnnotationQueue,
    "grading_queue": GradingQueue,
    "items": Page[ReviewItem],
    "users": Page[AdminUser],
    "user_new": AdminUser,
    "llm_summary": LlmSummary,
    "llm_logs": Page[LlmCallLog],
    "metrics": MetricsEvaluation,
    "admin_enrollments": Page[AdminEnrollment],
    "attempt_grant": AttemptGrant,
}


def _strict(model: Any) -> Any:
    """Subclase con `extra="forbid"` para detectar campos sobrantes en los fixtures."""
    if model.__pydantic_generic_metadata__["origin"]:
        return model
    return type(model.__name__, (model,), {"model_config": ConfigDict(extra="forbid")})


def _base_name(stem: str) -> str:
    head = stem.split("__")[0]
    if head.startswith("learner_detail_"):
        return "learner_detail"
    return head


@pytest.mark.parametrize("path", sorted(STAFF_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_every_staff_fixture_validates_against_the_models(path: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = _base_name(path.stem)
    list_models: dict[str, Any] = {
        "resources": Resource,
        "course_evaluators": CourseEvaluator,
        "materials": CourseMaterial,
    }
    if name in list_models:
        assert isinstance(data, list)
        for item in data:
            _strict(list_models[name]).model_validate(item)
        return
    if name == "human_grading_result":
        # Tiene la forma de la API (`HumanGradingResponse`); la prueba del adaptador la valida
        # contra el OpenAPI y aquí solo se comprueba que el adaptador la entiende.
        assert grading_result_from_api(data)["llm_criteria_total"] == 3
        return
    model = MODELS[name]
    strict = _strict(model)
    result = strict.model_validate(data)
    assert isinstance(result, BaseModel)


def test_scenarios_forbidden_and_error() -> None:
    client = FixturesClient("instructor")
    client.staff_scenario = "forbidden"
    with pytest.raises(ApiError) as forbidden:
        client.list_courses()
    assert forbidden.value.status == 403
    client.staff_scenario = "error"
    with pytest.raises(ApiError) as down:
        client.list_courses()
    assert down.value.status == 503


def test_empty_scenario_and_default_courses() -> None:
    client = FixturesClient("instructor")
    assert client.list_courses().total == 7
    client.staff_scenario = "empty"
    assert client.list_courses().items == []


def test_no_text_scenario_raises_the_contract_error() -> None:
    client = FixturesClient("instructor")
    client.staff_scenario = "no_text"
    with pytest.raises(ApiError) as error:
        client.upload_syllabus(1, text=None, file=("a.pdf", b"x"), idempotency_key="k")
    assert error.value.code == "SYLLABUS_NO_TEXT"


def test_fixtures_echo_the_uploaded_materials_of_each_course() -> None:
    client = FixturesClient("instructor")
    first = client.upload_material(7, file=("u1.pdf", b"%PDF-1"), origin="own_notes")
    client.upload_material(8, file=("otro.md", b"# x"), origin="permitted")
    assert first.file_name == "u1.pdf"
    assert first.source_type == "pdf"
    assert [m.file_name for m in client.list_materials(7)] == ["u1.pdf"]
    assert client.list_materials(8)[0].source_type == "text"


def test_fixtures_deactivate_a_material_and_hide_it() -> None:
    client = FixturesClient("instructor")
    first, second = client.list_materials(1)
    removed = client.deactivate_material(1, first.id)
    assert not removed.active
    assert [m.id for m in client.list_materials(1)] == [second.id]
    with pytest.raises(ApiError) as error:
        client.deactivate_material(2, second.id)
    assert error.value.code == "MATERIAL_NOT_FOUND"


@respx.mock
def test_api_client_deactivates_a_material() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    material = json.loads((STAFF_DIR / "material.json").read_text("utf-8"))
    route = respx.patch(f"{base}/api/v1/courses/7/materials/1/deactivate").mock(
        return_value=httpx.Response(200, json={**material, "active": False})
    )
    assert not client.deactivate_material(7, 1).active
    assert route.called


@respx.mock
def test_api_client_uploads_a_material_with_its_origin_and_no_idempotency_key() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    material = json.loads((STAFF_DIR / "material.json").read_text("utf-8"))
    route = respx.post(f"{base}/api/v1/courses/7/materials").mock(
        return_value=httpx.Response(201, json=material)
    )
    result = client.upload_material(7, file=("apuntes.md", b"# Tema"), origin="open_license")
    assert (
        route.call_count == 1
    )  # una sola petición: con el indicador «Cargando…» (T-054) se duplicó
    request = route.calls.last.request
    assert result.origin == "own_notes"  # lo que responde la API
    assert "Idempotency-Key" not in request.headers
    assert b'name="origin"' in request.content
    assert b"open_license" in request.content
    assert b"text/markdown" in request.content
    respx.get(f"{base}/api/v1/courses/7/materials").mock(
        return_value=httpx.Response(200, json=[material])
    )
    assert [m.id for m in client.list_materials(7)] == [1]


API_COURSE = {
    "id": 7,
    "name": "Machine Learning",
    "description": None,
    "status": "in_review",
    "owner_user_id": 3,
    "extraction_error_code": None,
    "extraction_job_id": None,
    "learning_path": None,
    "topics_count": 4,
    "enrolled_count": 0,
    "syllabus": {"filename": "programa.pdf", "pages": 12, "characters": 3400},
    "created_at": None,
    "updated_at": None,
}


@respx.mock
def test_api_client_reads_the_syllabus_of_a_course_from_the_api_response() -> None:
    """B-065: `GET /courses/{id}` trae `syllabus`; la lista y los cursos sin él, `null`."""
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    respx.get(f"{base}/api/v1/courses/7").mock(return_value=httpx.Response(200, json=API_COURSE))
    course = client.get_course(7)
    assert course.syllabus is not None
    assert (course.syllabus.filename, course.syllabus.pages) == ("programa.pdf", 12)
    assert course.syllabus.characters == 3400
    respx.get(f"{base}/api/v1/courses").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{**API_COURSE, "syllabus": None}],
                "total": 1,
                "limit": 20,
                "offset": 0,
            },
        )
    )
    assert client.list_courses(mine=True).items[0].syllabus is None


def test_poll_job_runs_then_succeeds() -> None:
    client = FixturesClient("instructor")
    assert client.poll_job("j1").status == "running"
    assert client.poll_job("j1").status == "succeeded"


@respx.mock
def test_api_client_staff_operations() -> None:
    base = "http://api.test"
    http = httpx.Client(base_url=base)
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=http)
    course = json.loads((STAFF_DIR / "course.json").read_text("utf-8"))
    route = respx.post(f"{base}/api/v1/courses").mock(return_value=httpx.Response(201, json=course))
    created = client.create_course(CourseCreate(name="X", learning_path_name="X", group_label="G"))
    assert created.id == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent["learning_path"] == {"name": "X", "group_label": "G"}
    syl = respx.post(f"{base}/api/v1/courses/1/syllabus").mock(
        return_value=httpx.Response(
            202, json=json.loads((STAFF_DIR / "job_accepted.json").read_text("utf-8"))
        )
    )
    client.upload_syllabus(1, text=None, file=("s.pdf", b"%PDF"), idempotency_key="key-1")
    assert syl.calls.last.request.headers["Idempotency-Key"] == "key-1"
    assert b"multipart/form-data" in syl.calls.last.request.headers["content-type"].encode()
    graph = json.loads((STAFF_DIR / "topic_graph.json").read_text("utf-8"))
    respx.get(f"{base}/api/v1/courses/1/topic-graph").mock(
        return_value=httpx.Response(200, json=graph)
    )
    assert client.get_topic_graph(1).edges[0].source == 101
    respx.put(f"{base}/api/v1/users/1/roles").mock(
        return_value=httpx.Response(409, json={"code": "LAST_ADMIN", "detail": "x"})
    )
    with pytest.raises(ApiError) as error:
        client.set_user_roles(1, ["learner"])
    assert error.value.code == "LAST_ADMIN"
