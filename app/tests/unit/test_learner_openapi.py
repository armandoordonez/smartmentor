"""Los fixtures del aprendiz tienen la forma de la API real (`docs/contracts/openapi-api.json`).

`test_learner_fixtures.py` valida los fixtures contra los modelos de la interfaz; esta prueba los
valida contra el OpenAPI de la API. Si un fixture tiene la forma que espera la pantalla pero no la
que manda la API (como pasó con el catálogo: `topics_count` contra `topic_count`), falla aquí.

Además, respuestas reales de la API (capturadas en local el 11-nov-2026, recortadas) validan contra
los modelos de la interfaz: lo que manda la API de verdad se tiene que poder leer.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter
from support import FIXTURES_DIR, REPO_ROOT

from clients import models
from clients.models import Page

OPENAPI = json.loads((REPO_ROOT / "docs" / "contracts" / "openapi-api.json").read_text("utf-8"))

# Prefijo del nombre del archivo -> (esquema del OpenAPI, es lista). El prefijo más largo gana.
SCHEMAS: dict[str, tuple[str, bool]] = {
    "me_": ("MeResponse", False),
    "profile": ("ProfileResponse", False),
    "consents": ("ConsentResponse", True),
    "learning_paths": ("Page_LearningPathCard_", False),
    "enrollments_": ("Page_EnrollmentResponse_", False),
    "enrollment_": ("EnrollmentResponse", False),
    "job_accepted": ("JobAccepted", False),
    "job_": ("JobResponse", False),
    "job-": ("JobResponse", False),
    "diagnostic_result": ("DiagnosticResultResponse", False),
    "diagnostic": ("DiagnosticResponse", False),
    "path": ("PathResponse", False),
    "step_content": ("StepContentResponse", False),
    "attempt_result": ("AttemptResultResponse", False),
    "attempt": ("AttemptResponse", False),
    "history": ("AttemptHistoryItem", True),
    "review_plan": ("ReviewPlanResponse", False),
    "badge": ("BadgeSummary", False),
    "goals": ("StudyGoalsResponse", False),
    "after-job": ("NextActionResponse", False),
}
# `badge.v1` (Open Badges) lo arma la IA: la API lo sirve como objeto libre.
WITHOUT_SCHEMA = {"assertion"}
FILES = sorted([*FIXTURES_DIR.glob("*.json"), *(FIXTURES_DIR / "learner").glob("*.json")])


def _validator(name: str, *, is_list: bool) -> Draft202012Validator:
    ref: dict[str, Any] = {"$ref": f"#/components/schemas/{name}"}
    schema = {"type": "array", "items": ref} if is_list else ref
    return Draft202012Validator({**schema, "components": OPENAPI["components"]})


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_fixture_has_the_shape_of_the_api(path: Path) -> None:
    if path.stem in WITHOUT_SCHEMA:
        return
    prefixes = [prefix for prefix in SCHEMAS if path.stem.startswith(prefix)]
    assert prefixes, f"{path.name}: sin esquema del OpenAPI"
    name, is_list = SCHEMAS[max(prefixes, key=len)]
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = [
        f"{'/'.join(map(str, e.path))}: {e.message}"
        for e in _validator(name, is_list=is_list).iter_errors(data)
    ]
    assert not errors, errors


# --- Respuestas reales de la API --------------------------------------------------------------

REAL_PROFILE: dict[str, Any] = {
    "description": "Analista de datos.",
    "education_level": None,
    "qualification_title": None,
    "job_title": None,
    "experience_band": None,
    "tools": [],
    "languages": [],
    "resume_completed_at": None,
    "recalculated_enrollment_ids": None,
}
REAL_CATALOG: dict[str, Any] = {
    "items": [
        {
            "id": 2,
            "name": "Extraccion Y Almacenamiento De Datos",
            "group_label": "2026-2",
            "course": {"id": 2, "name": "Extraccion Y Almacenamiento De Datos", "description": "…"},
            "topics": [
                {"id": 4, "name": "Arquitecturas", "estimated_minutes": None, "is_mandatory": False}
            ],
            "topic_count": 1,
            "estimated_minutes": 0,
            "enrolled": True,
        }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0,
}
REAL_DIAGNOSTIC_RESULT: dict[str, Any] = {
    "status": "scored",
    "level_by_topic": [
        {
            "topic_id": 4,
            "name": "Arquitecturas",
            "test_score": 0.0,
            "profile_prior": 60.1,
            "resume_prior": None,
            "weights": {"test": 0.89, "resume": 0.0, "profile": 0.11},
            "level": 6.7,
            "classification": "to_learn",
        }
    ],
    "overall_score": 0.0,
    "proposed_objective": None,
}
REAL_STEP_CONTENT: dict[str, Any] = {
    "step_id": 3,
    "status": "in_progress",
    "topic": {
        "id": 6,
        "name": "Extracción ética y legal de datos desde la Web",
        "learning_outcomes": [{"id": 16, "statement": "Evaluar…", "bloom_level": None}],
    },
    "explanation": None,
    "personal_example": None,
    "video": None,
    "quiz_rules": {
        "pass_threshold": 70.0,
        "items_per_attempt": 5,
        "short_answer_min_criteria_ratio": 0.667,
    },
    "attempts": {"used": 0, "max": 3, "extra_granted": 0, "remaining": 3},
}
REAL_JOB: dict[str, Any] = {
    "job_id": "3dd19062-70c2-4e45-a388-c562503d0199",
    "job_type": "items.generate_quiz_bank",
    "status": "succeeded",
    "progress_label": "Preparando preguntas nuevas",
    "ingested": True,
    "next_action": None,
    "error": None,
}

REAL_RESPONSES: list[tuple[str, Any, dict[str, Any] | list[Any]]] = [
    ("ProfileResponse", models.Profile, REAL_PROFILE),
    ("Page_LearningPathCard_", Page[models.LearningPathCard], REAL_CATALOG),
    ("DiagnosticResultResponse", models.DiagnosticResult, REAL_DIAGNOSTIC_RESULT),
    ("StepContentResponse", models.StepContent, REAL_STEP_CONTENT),
    ("JobResponse", models.Job, REAL_JOB),
]


@pytest.mark.parametrize(("schema", "model", "data"), REAL_RESPONSES, ids=lambda v: str(v)[:30])
def test_real_api_response_is_readable_by_the_interface(
    schema: str, model: Any, data: dict[str, Any]
) -> None:
    assert not list(_validator(schema, is_list=False).iter_errors(data))
    TypeAdapter(model).validate_python(data)


def test_null_recalculated_ids_read_as_empty() -> None:
    assert models.Profile.model_validate(REAL_PROFILE).recalculated_enrollment_ids == []
