"""D4 · El detalle del aprendiz que manda la API se traduce al modelo de la pantalla."""

import json
from typing import Any

import httpx
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.api import ApiClient
from clients.learner_detail_adapter import (
    FINAL_ASSESSMENT_NAME,
    is_api_learner_detail,
    learner_detail_from_api,
)
from clients.models_staff import LearnerDetail

OPENAPI = REPO_ROOT / "docs" / "contracts" / "openapi-api.json"


def _step(step_id: int, order: int, topic_id: int, name: str, status: str, **extra: Any) -> dict[str, Any]:
    base = {
        "step_id": step_id,
        "step_order": order,
        "topic_id": topic_id,
        "name": name,
        "status": status,
        "inclusion_reason": "required_by_path",
        "diagnostic_level": None,
        "estimated_minutes": 30,
        "attempts_used": 0,
        "max_attempts": 3,
        "extra_attempts_granted": 0,
        "best_score": None,
        "last_score": None,
    }
    return {**base, **extra}


def _attempt(attempt_id: int, step_id: int | None, number: int, **extra: Any) -> dict[str, Any]:
    base = {
        "id": attempt_id,
        "assessment_type": "topic_quiz" if step_id is not None else "final",
        "step_id": step_id,
        "attempt_number": number,
        "status": "graded",
        "score": 50.0,
        "passed": False,
        "uses_extra_grant": False,
        "submitted_at": "2026-11-10T15:00:00Z",
    }
    return {**base, **extra}


# Una respuesta como la de `GET /learning-paths/7/learners/11`: tres pasos, uno agotado.
API_DETAIL: dict[str, Any] = {
    "enrollment_id": 11,
    "learning_path": {"id": 7, "name": "Datos", "group_label": "Piloto", "status": "published"},
    "user_id": 21,
    "full_name": "Ana Pérez",
    "profile": {
        "education_level": "undergraduate",
        "experience_band": "1_3_years",
        "job_title": "Analista de datos",
    },
    "status": "in_path",
    "objective": {
        "statement": "Aplicar ETL en proyectos reales ≥ 80 % en la final",
        "bloom_verb": "Aplicar",
        "content": "ETL en proyectos reales",
        "criterion": "≥ 80 % en la final",
        "origin": None,
    },
    "level_by_topic": [
        {"topic_id": "103", "level": 0.2, "classification": "to_learn", "test_score": None},
        {"topic_id": "101", "level": 0.9, "classification": "mastered", "test_score": 90.0},
        {"topic_id": "102", "level": 0.5, "classification": "to_reinforce", "test_score": 50.0},
    ],
    "steps": [
        _step(502, 2, 102, "ETL", "attempts_exhausted", attempts_used=3, best_score=60.0),
        _step(501, 1, 101, "Bases", "skipped"),
        _step(503, 3, 103, "Ética", "on_hold"),
        _step(504, 4, 104, "Visualización", "pending"),
    ],
    "attempts": [
        _attempt(900, 502, 1, score=40.0),
        _attempt(901, 502, 2, score=60.0),
        _attempt(902, 502, 3, score=55.0),
        _attempt(903, None, 1, score=None, passed=None, status="created", submitted_at=None),
    ],
    "final_attempts_granted": 0,
}


def test_the_sample_is_a_valid_api_response() -> None:
    """La muestra cumple el OpenAPI publicado: si la API cambia la respuesta, esto falla."""
    spec = json.loads(OPENAPI.read_text("utf-8"))
    schema = {"$ref": "#/components/schemas/LearnerDetailResponse", **spec}
    errors = sorted(Draft202012Validator(schema).iter_errors(API_DETAIL), key=str)
    assert not errors, [e.message for e in errors]


def test_api_detail_becomes_the_screen_model() -> None:
    assert is_api_learner_detail(API_DETAIL)
    detail = LearnerDetail.model_validate(learner_detail_from_api(API_DETAIL, 7))

    assert (detail.user.id, detail.user.full_name) == (21, "Ana Pérez")
    assert (detail.learning_path.name, detail.learning_path.group_label) == ("Datos", "Piloto")
    assert (detail.education_level, detail.experience_band) == ("undergraduate", "1_3_years")
    assert detail.job_title == "Analista de datos"
    assert detail.profile_summary is None and detail.resume_summary is None
    assert detail.objective is not None and detail.objective.origin == "path_default"

    # Los niveles van en el orden de la ruta y con el nombre del tema.
    assert [(t.topic_id, t.name) for t in detail.topic_levels] == [
        (101, "Bases"),
        (102, "ETL"),
        (103, "Ética"),
    ]

    # Solo los intentos entregados, con el nombre del tema del paso.
    assert [(a.attempt_id, a.topic_name) for a in detail.attempts] == [
        (900, "ETL"),
        (901, "ETL"),
        (902, "ETL"),
    ]

    (exhausted,) = detail.exhausted_steps
    assert (exhausted.step_id, exhausted.topic_name) == (502, "ETL")
    assert (exhausted.attempts_used, exhausted.max_attempts, exhausted.best_score) == (3, 3, 60.0)
    assert exhausted.waiting_topic_names == ["Ética"]
    assert exhausted.continue_topic_names == ["Visualización"]


def test_extra_attempts_raise_the_limit_and_final_attempts_are_named() -> None:
    data = json.loads(json.dumps(API_DETAIL))
    data["steps"][0]["extra_attempts_granted"] = 1
    data["steps"][0]["attempts_used"] = 4
    data["attempts"][3] = _attempt(903, None, 1, score=70.0, passed=False)
    detail = LearnerDetail.model_validate(learner_detail_from_api(data, 7))

    assert detail.exhausted_steps[0].max_attempts == 4
    assert detail.attempts[-1].topic_name == FINAL_ASSESSMENT_NAME
    assert detail.attempts[-1].step_id is None


def test_unknown_codes_do_not_break_the_screen() -> None:
    data = json.loads(json.dumps(API_DETAIL))
    data["profile"] = {"education_level": "algo_nuevo", "experience_band": None, "job_title": ""}
    data["level_by_topic"][0]["classification"] = "otra"
    data["objective"] = None
    detail = LearnerDetail.model_validate(learner_detail_from_api(data, 7))

    assert (detail.education_level, detail.experience_band, detail.job_title) == (None, None, None)
    assert detail.objective is None
    assert {t.topic_id: t.classification for t in detail.topic_levels}[103] == "to_learn"


def test_without_the_path_in_the_response_the_requested_id_is_kept() -> None:
    data = json.loads(json.dumps(API_DETAIL))
    del data["learning_path"]
    detail = LearnerDetail.model_validate(learner_detail_from_api(data, 7))
    assert (detail.learning_path.id, detail.learning_path.name) == (7, "")


def test_fixtures_pass_unchanged() -> None:
    fixture = json.loads(
        (REPO_ROOT / "app" / "tests" / "fixtures" / "staff" / "learner_detail_204.json").read_text(
            "utf-8"
        )
    )
    assert not is_api_learner_detail(fixture)


@respx.mock
def test_the_http_client_reads_the_real_detail() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    respx.get(f"{base}/api/v1/learning-paths/7/learners/11").mock(
        return_value=httpx.Response(200, json=API_DETAIL)
    )
    detail = client.get_learner_detail(7, 11)
    assert detail.learning_path.id == 7
    assert detail.exhausted_steps[0].topic_name == "ETL"
