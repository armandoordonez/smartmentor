"""D3 · El tablero que manda la API se traduce al modelo de la pantalla (dashboard_adapter.py)."""

import json
from typing import Any

import httpx
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.api import ApiClient
from clients.dashboard_adapter import dashboard_from_api, is_api_dashboard
from clients.models_staff import Dashboard

OPENAPI = REPO_ROOT / "docs" / "contracts" / "openapi-api.json"

# Una respuesta como la de `GET /learning-paths/{id}/dashboard`: dos aprendices, tres temas.
API_DASHBOARD: dict[str, Any] = {
    "learning_path_id": 7,
    "course_id": 3,
    "learning_path": {"id": 7, "name": "Datos", "group_label": "Piloto", "status": "published"},
    "settings": {
        "learning_path_id": 7,
        "topic_pass_threshold": 70.0,
        "final_pass_threshold": 80.0,
        "mastery_skip_threshold": 80.0,
        "max_attempts": 3,
        "short_answer_min_ratio": 0.5,
        "level_weights": {"test": 0.6, "profile": 0.2, "resume": 0.2},
        "default_objective": {"bloom_verb": None, "content": None, "criterion": None},
    },
    "pilot_running": False,
    "kpi": {
        "learners": 2,
        "active": 1,
        "completed": 1,
        "withdrawn": 0,
        "completion_rate": 50.0,
        "average_progress": 66.7,
        "first_attempt_pass_rate": 75.0,
        "exhausted_steps": 1,
        "attempts_per_topic": 1.4,
    },
    "learners": [
        {
            "enrollment_id": 11,
            "user_id": 21,
            "full_name": "Ana Pérez",
            "status": "in_path",
            "progress_percent": 33,
            "steps_done": 1,
            "steps_total": 3,
            "analysis_included": True,
            "pilot_arm": None,
        },
        {
            "enrollment_id": 12,
            "user_id": 22,
            "full_name": "Luis Gómez",
            "status": "completed",
            "progress_percent": 100,
            "steps_done": 3,
            "steps_total": 3,
            "analysis_included": True,
            "pilot_arm": None,
        },
    ],
    "topics": [
        {"id": 101, "name": "Bases", "estimated_minutes": 30, "is_mandatory": True},
        {"id": 102, "name": "ETL", "estimated_minutes": 45, "is_mandatory": True},
        {"id": 103, "name": "Ética", "estimated_minutes": None, "is_mandatory": False},
    ],
    "mastery_matrix": [
        {
            "enrollment_id": 11,
            "cells": [
                {"topic_id": 101, "status": "passed", "diagnostic_level": 0.4, "best_score": 90.0},
                {
                    "topic_id": 102,
                    "status": "attempts_exhausted",
                    "diagnostic_level": None,
                    "best_score": 55.0,
                },
                {
                    "topic_id": 103,
                    "status": "blocked",
                    "diagnostic_level": None,
                    "best_score": None,
                },
            ],
        },
        {
            "enrollment_id": 12,
            "cells": [
                {"topic_id": 101, "status": "skipped", "diagnostic_level": 0.9, "best_score": None},
                {"topic_id": 102, "status": "passed", "diagnostic_level": None, "best_score": 85.0},
                {"topic_id": 103, "status": "passed", "diagnostic_level": None, "best_score": 95.0},
            ],
        },
    ],
    "critical_topics": [
        {
            "topic_id": 102,
            "name": "ETL",
            "attempts_exhausted": 1,
            "average_attempts": 2.0,
            "first_attempt_pass_rate": 50.0,
        }
    ],
    "topic_stats": [
        {
            "topic_id": 101,
            "name": "Bases",
            "attempts_exhausted": 0,
            "average_attempts": 1.0,
            "first_attempt_pass_rate": 100.0,
        },
        {
            "topic_id": 102,
            "name": "ETL",
            "attempts_exhausted": 1,
            "average_attempts": 2.0,
            "first_attempt_pass_rate": 50.0,
        },
        {
            "topic_id": 103,
            "name": "Ética",
            "attempts_exhausted": 0,
            "average_attempts": None,
            "first_attempt_pass_rate": None,
        },
    ],
}


def test_the_sample_is_a_valid_api_response() -> None:
    """La muestra cumple el OpenAPI publicado: si la API cambia el tablero, esto falla."""
    spec = json.loads(OPENAPI.read_text("utf-8"))
    schema = {"$ref": "#/components/schemas/DashboardResponse", **spec}
    errors = sorted(Draft202012Validator(schema).iter_errors(API_DASHBOARD), key=str)
    assert not errors, [e.message for e in errors]


def test_api_dashboard_becomes_the_screen_model() -> None:
    assert is_api_dashboard(API_DASHBOARD)
    board = Dashboard.model_validate(dashboard_from_api(API_DASHBOARD))

    assert (board.course_id, board.learning_path.name, board.published) == (3, "Datos", True)
    assert board.settings.topic_pass_threshold == 70
    assert board.settings.default_objective is None
    assert board.kpis.enrolled == 2
    assert board.kpis.completion_rate == 0.5  # 50 % -> fracción
    assert board.kpis.badges_issued == 1
    assert board.kpis.attempts_per_topic == 1.4
    assert [(t.position, t.name) for t in board.topics] == [(1, "Bases"), (2, "ETL"), (3, "Ética")]

    ana, luis = board.learners
    assert (ana.current_topic, ana.current_score, ana.badge_issued) == ("ETL", 55.0, False)
    assert (luis.current_topic, luis.badge_issued) == (None, True)
    assert board.mastery[0].full_name == "Ana Pérez"
    assert board.mastery[0].cells == ["passed", "attempts_exhausted", "blocked"]

    stats = {s.topic_id: s for s in board.topic_stats}
    assert stats[101].first_attempt_pass_rate == 1.0
    assert stats[103].avg_attempts is None
    assert board.critical_topic_ids == [102]


def test_unknown_cell_status_is_drawn_as_pending() -> None:
    data = json.loads(json.dumps(API_DASHBOARD))
    data["mastery_matrix"][0]["cells"][2]["status"] = "algo_nuevo"
    board = Dashboard.model_validate(dashboard_from_api(data))
    assert board.mastery[0].cells[2] == "pending"


def test_a_saved_default_objective_is_kept() -> None:
    data = json.loads(json.dumps(API_DASHBOARD))
    data["settings"]["default_objective"] = {"bloom_verb": "Aplicar", "content": "ETL"}
    board = Dashboard.model_validate(dashboard_from_api(data))
    assert board.settings.default_objective is not None
    assert board.settings.default_objective.bloom_verb == "Aplicar"


@respx.mock
def test_the_http_client_reads_the_real_dashboard() -> None:
    base = "http://api.test"
    client = ApiClient(base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base))
    respx.get(f"{base}/api/v1/learning-paths/7/dashboard").mock(
        return_value=httpx.Response(200, json=API_DASHBOARD)
    )
    board = client.get_dashboard(7)
    assert board.learning_path.id == 7
    assert board.learners[0].current_topic == "ETL"
