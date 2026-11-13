"""Los fixtures del aprendiz (`tests/fixtures/learner/`) validan contra los modelos con `forbid`,
los escenarios apuntan a archivos que existen y las operaciones HTTP nuevas hablan con la API."""

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import TypeAdapter
from support import FIXTURES_DIR

from clients import models
from clients.api import ApiClient
from clients.fixtures import FixturesClient
from clients.models import Page
from clients.models_learner import AttemptSummary, BadgeAssertion, StudyGoals, StudyGoalsUpdate
from clients.ops_learner import DEFAULT_DOCS, LEARNER_SCENARIOS

LEARNER_DIR = FIXTURES_DIR / "learner"

# Prefijo del nombre del archivo -> modelo. El más largo gana.
MODELS: dict[str, Any] = {
    "enrollments_": Page[models.Enrollment],
    "enrollment_": models.Enrollment,
    "job_accepted": models.JobAccepted,
    "job-": models.Job,
    "diagnostic_result": models.DiagnosticResult,
    "diagnostic": models.Diagnostic,
    "path": models.PathDetail,
    "step_content": models.StepContent,
    "attempt_result": models.AttemptResult,
    "attempt_": models.Attempt,
    "history": list[AttemptSummary],
    "review_plan": models.ReviewPlan,
    "badge": models.BadgeSummary,
    "assertion": BadgeAssertion,
    "goals": StudyGoals,
    # `next_action` de la inscripción cuando termina un trabajo (la API no lo pone en el trabajo).
    "after-job": models.NextAction,
}
FILES = sorted(LEARNER_DIR.glob("*.json"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_learner_fixture_validates_with_forbid(path: Any) -> None:
    matches = [prefix for prefix in MODELS if path.stem.startswith(prefix)]
    assert matches, f"{path.stem} sin modelo"
    model = MODELS[max(matches, key=len)]
    data = json.loads(path.read_text(encoding="utf-8"))
    # `badge.v1` es de la IA: el modelo de la app es una vista que ignora lo que no muestra.
    extra = None if path.stem == "assertion" else "forbid"
    TypeAdapter(model).validate_python(data, extra=extra)


def test_default_documents_exist() -> None:
    for name in DEFAULT_DOCS.values():
        if name != "done":
            assert (FIXTURES_DIR / f"{name}.json").is_file(), name


def test_scenarios_point_to_existing_files() -> None:
    for spec in LEARNER_SCENARIOS:
        assert (FIXTURES_DIR / f"{spec.enrollments}.json").is_file(), spec.key
        for name in spec.script.docs.values():
            if name not in ("done", "failed"):
                assert (FIXTURES_DIR / f"{name}.json").is_file(), (spec.key, name)


def test_offline_scenario_fails_every_learner_operation() -> None:
    client = FixturesClient("learner_offline")
    for call in (
        lambda: client.get_enrollment(7),
        lambda: client.get_path(7),
        lambda: client.get_study_goals(),
    ):
        with pytest.raises(Exception, match="503"):
            call()


def test_job_runs_first_then_follows_the_scenario_outcome() -> None:
    done = FixturesClient("learner_calculating")
    assert done.get_job("job-diagnostic").status == "running"
    job = done.get_job("job-diagnostic")
    assert job.status == "succeeded"
    assert done.get_enrollment(7).next_action.type == "confirm_objective"
    failed = FixturesClient("learner_calculating_error")
    failed.get_job("job-diagnostic")
    assert failed.get_job("job-diagnostic").status == "failed"


# --- Operaciones HTTP nuevas ---------------------------------------------------------------------


def _client(http: httpx.Client) -> ApiClient:
    return ApiClient("http://api.test", lambda: "test-only-not-a-secret", http=http)


@respx.mock
def test_api_reads_the_public_assertion_and_image() -> None:
    data = json.loads((LEARNER_DIR / "assertion.json").read_text(encoding="utf-8"))
    respx.get("http://api.test/api/v1/badges/abc/assertion.json").respond(200, json=data)
    respx.get("http://api.test/api/v1/badges/abc/image.png").respond(200, content=b"png")
    client = _client(httpx.Client(base_url="http://api.test"))
    assert client.get_badge_assertion("abc").badge.name == "Fundamentos de Machine Learning"
    assert client.get_badge_image("abc") == b"png"


@respx.mock
def test_api_goals_404_means_no_goals_and_history_is_listed() -> None:
    respx.get("http://api.test/api/v1/me/study-goals").respond(404, json={"code": "NOT_FOUND"})
    respx.get("http://api.test/api/v1/me/enrollments/7/steps/813/attempts").respond(
        200, json=[{"number": 1, "score": 60.0, "correct": 3, "total": 5}]
    )
    respx.get("http://api.test/api/v1/me/enrollments/7/final/attempts").respond(200, json=[])
    respx.put("http://api.test/api/v1/me/study-goals").respond(
        200, json=json.loads((LEARNER_DIR / "goals.json").read_text(encoding="utf-8"))
    )
    client = _client(httpx.Client(base_url="http://api.test"))
    assert client.get_study_goals() is None
    assert client.list_attempt_history(7, 813)[0].score == 60.0
    assert client.list_attempt_history(7, None) == []
    assert client.set_study_goals(StudyGoalsUpdate(daily_minutes_goal=30, monthly_topics_goal=3))
