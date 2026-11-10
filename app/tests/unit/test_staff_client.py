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
from clients.fixtures import FixturesClient
from clients.models import Job, JobAccepted, Page
from clients.models_staff import (
    AdminEnrollment,
    AdminUser,
    AnnotationQueue,
    AttemptGrant,
    Course,
    CourseCreate,
    CourseTopics,
    Dashboard,
    ExtractionMetrics,
    FixedPathPreview,
    GradingQueue,
    HumanGradingResult,
    LearnerDetail,
    LlmCallLog,
    LlmSummary,
    MetricsEvaluation,
    Pilot,
    PilotReadiness,
    RandomizeResult,
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
    "human_grading_result": HumanGradingResult,
    "items": Page[ReviewItem],
    "users": Page[AdminUser],
    "user_new": AdminUser,
    "llm_summary": LlmSummary,
    "llm_logs": Page[LlmCallLog],
    "metrics": MetricsEvaluation,
    "pilot": Pilot,
    "pilot_readiness": PilotReadiness,
    "randomize_result": RandomizeResult,
    "fixed_path_preview": FixedPathPreview,
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
    if name in {"resources"}:
        assert isinstance(data, list)
        for item in data:
            Resource.model_validate(item)
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
    assert client.list_courses().total == 6
    client.staff_scenario = "empty"
    assert client.list_courses().items == []


def test_no_text_scenario_raises_the_contract_error() -> None:
    client = FixturesClient("instructor")
    client.staff_scenario = "no_text"
    with pytest.raises(ApiError) as error:
        client.upload_syllabus(1, text=None, file=("a.pdf", b"x"), idempotency_key="k")
    assert error.value.code == "SYLLABUS_NO_TEXT"


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
