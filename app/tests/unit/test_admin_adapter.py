"""AD1 y AD2 · Usuarios con sus roles y log del LLM, armados desde las rutas reales de la API."""

import json
from typing import Any

import httpx
import respx
from jsonschema import Draft202012Validator
from support import REPO_ROOT

from clients.admin_adapter import (
    admin_enrollment_from_api,
    fixed_path_preview_from_api,
    llm_log_from_api,
    llm_summary_from_api,
    metrics_from_api,
    pilot_from_api,
    pilot_to_show,
)
from clients.api import ApiClient
from clients.models_staff import (
    AdminEnrollment,
    FixedPathPreview,
    LlmCallLog,
    LlmSummary,
    MetricsEvaluation,
    Pilot,
    UserCreate,
)
from services.staff_admin import metric_text

OPENAPI = REPO_ROOT / "docs" / "contracts" / "openapi-api.json"
BASE = "http://api.test"
CREATED = "2026-11-10T15:00:00Z"


def _valid(schema_name: str, sample: Any) -> list[str]:
    spec = json.loads(OPENAPI.read_text("utf-8"))
    schema = {"$ref": f"#/components/schemas/{schema_name}", **spec}
    return [e.message for e in Draft202012Validator(schema).iter_errors(sample)]


def _user(user_id: int, name: str, *, active: bool = True) -> dict[str, Any]:
    return {
        "id": user_id,
        "active": active,
        "created_at": CREATED,
        "full_name": name,
        "email": f"usuario{user_id}@example.test",
        "identity_provider": None,
        "identity_subject": None,
    }


def _page(items: list[dict[str, Any]], *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    return {"items": items, "total": len(items), "limit": limit, "offset": offset}


ACTIVE = _page([_user(1, "Ana Admin"), _user(2, "Iván Instructor")])
INACTIVE = _page([_user(3, "Lía Retirada", active=False)])
ROLES_PAGE = _page(
    [
        {"id": r, "active": True, "created_at": CREATED, "code": c, "name": c, "description": None}
        for r, c in ((10, "admin"), (11, "instructor"), (12, "learner"), (13, "otro"))
    ]
)
USER_ROLES_PAGE = _page(
    [
        {"id": 100 + i, "active": True, "created_at": CREATED, "user_id": u, "role_id": r}
        for i, (u, r) in enumerate(((1, 10), (1, 12), (2, 11), (3, 12), (2, 13)))
    ]
)

API_LOG: dict[str, Any] = {
    "id": 7,
    "ai_job_id": 3,
    "enrollment_id": None,
    "provider": "gemini",
    "task": "items.generate_quiz_bank",
    "model": "gemini-3.8-flash",
    "prompt_id": "topic_quiz",
    "prompt_version": "1.2.0",
    "input_sha256": None,
    "json_valid": True,
    "call_attempt": 1,
    "from_cache": False,
    "input_tokens": 1500,
    "output_tokens": 640,
    "cost_usd": 0.011,
    "latency_ms": 8200,
    "status": "succeeded",
    "error_message": None,
    "created_at": CREATED,
}
API_SUMMARY: dict[str, Any] = {
    "by_task": [
        {
            "task": "items.generate_quiz_bank",
            "calls": 4,
            "invalid_json_rate": 0.25,
            "latency_p50_ms": 812.5,
            "latency_p95_ms": None,
            "cost_usd": 0.04,
        }
    ],
    "by_course": [{"course_id": 1, "calls": 4, "cost_usd": 0.04}],
    "total_cost_usd": 0.04,
}


def _client() -> ApiClient:
    return ApiClient(BASE, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=BASE))


def _mock_roles() -> None:
    respx.get(f"{BASE}/api/v1/roles").mock(return_value=httpx.Response(200, json=ROLES_PAGE))
    respx.get(f"{BASE}/api/v1/user-roles").mock(
        return_value=httpx.Response(200, json=USER_ROLES_PAGE)
    )


def test_the_samples_are_valid_api_responses() -> None:
    assert _valid("Page_UserResponse_", ACTIVE) == []
    assert _valid("Page_RoleResponse_", ROLES_PAGE) == []
    assert _valid("Page_UserRoleResponse_", USER_ROLES_PAGE) == []
    assert _valid("LlmCallLogResponse", API_LOG) == []
    assert _valid("LogSummaryResponse", API_SUMMARY) == []


@respx.mock
def test_users_come_with_their_roles_active_first_and_inactive_after() -> None:
    def users(request: httpx.Request) -> httpx.Response:
        wanted = request.url.params["active"] == "true"
        return httpx.Response(200, json=ACTIVE if wanted else INACTIVE)

    respx.get(f"{BASE}/api/v1/users").mock(side_effect=users)
    _mock_roles()
    page = _client().list_users()

    assert page.total == 3
    assert [(u.id, u.active) for u in page.items] == [(1, True), (2, True), (3, False)]
    roles = {u.id: u.roles for u in page.items}
    # En el orden de la interfaz y sin roles que la interfaz no conoce.
    assert roles == {1: ["learner", "admin"], 2: ["instructor"], 3: ["learner"]}


@respx.mock
def test_creating_a_user_sends_only_its_data_and_then_its_roles() -> None:
    create = respx.post(f"{BASE}/api/v1/users").mock(
        return_value=httpx.Response(201, json=_user(9, "Nuevo"))
    )
    roles = respx.put(f"{BASE}/api/v1/users/9/roles").mock(
        return_value=httpx.Response(200, json={"roles": ["learner", "instructor"]})
    )
    user = _client().create_user(
        UserCreate(email="nuevo@example.test", full_name="Nuevo", roles=["learner", "instructor"])
    )

    # La API rechaza campos desconocidos: los roles no van en el alta.
    assert json.loads(create.calls.last.request.content) == {
        "email": "nuevo@example.test",
        "full_name": "Nuevo",
    }
    assert json.loads(roles.calls.last.request.content) == {"roles": ["learner", "instructor"]}
    assert (user.id, user.roles) == (9, ["learner", "instructor"])


@respx.mock
def test_activating_and_deactivating_use_their_own_routes() -> None:
    off = respx.patch(f"{BASE}/api/v1/users/3/deactivate").mock(
        return_value=httpx.Response(200, json=_user(3, "Lía", active=False))
    )
    on = respx.patch(f"{BASE}/api/v1/users/3/activate").mock(
        return_value=httpx.Response(200, json=_user(3, "Lía"))
    )
    respx.get(f"{BASE}/api/v1/users/3/roles").mock(
        return_value=httpx.Response(200, json={"roles": ["learner"]})
    )
    client = _client()

    assert client.set_user_active(3, False).active is False
    assert off.called and not on.called
    user = client.set_user_active(3, True)
    assert (user.active, user.roles) == (True, ["learner"])


def test_a_log_becomes_the_screen_row() -> None:
    log = LlmCallLog.model_validate(llm_log_from_api(API_LOG))
    assert (log.task, log.task_label) == ("items.generate_quiz_bank", "items.generate_quiz_bank")
    assert log.tokens == 2140
    assert (log.model, log.prompt_id, log.prompt_version) == (
        "gemini-3.8-flash",
        "topic_quiz",
        "1.2.0",
    )


def test_a_failed_call_without_model_or_cost_still_shows() -> None:
    failed = {
        **API_LOG,
        "model": None,
        "prompt_id": None,
        "prompt_version": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
        "latency_ms": None,
        "status": "failed",
    }
    log = LlmCallLog.model_validate(llm_log_from_api(failed))
    assert (log.model, log.tokens, log.cost_usd, log.latency_ms) == ("", 0, 0.0, 0)


def test_the_summary_latencies_become_whole_milliseconds() -> None:
    summary = LlmSummary.model_validate(llm_summary_from_api(API_SUMMARY))
    (task,) = summary.by_task
    assert (task.latency_p50_ms, task.latency_p95_ms) == (812, 0)
    assert summary.total_cost_usd == 0.04


@respx.mock
def test_the_http_client_reads_the_real_logs() -> None:
    undated = {**API_LOG, "id": 8, "created_at": None}
    respx.get(f"{BASE}/api/v1/llm-call-logs").mock(
        return_value=httpx.Response(200, json=_page([API_LOG, undated], limit=50))
    )
    respx.get(f"{BASE}/api/v1/llm-call-logs/summary").mock(
        return_value=httpx.Response(200, json=API_SUMMARY)
    )
    client = _client()
    logs = client.list_llm_logs()
    assert [log.id for log in logs.items] == [7]
    assert client.get_llm_summary().by_task[0].calls == 4


# --- AD4 y AD4b · Piloto ---------------------------------------------------------------------

API_PILOT: dict[str, Any] = {
    "id": 4,
    "learning_path_id": 7,
    "starts_on": "2026-12-01",
    "ends_on": "2026-12-20",
    "delayed_posttest_on": None,
    "random_seed": 2026,
    "status": "randomized",
    "arms": {"personalized": 12, "fixed": 11},
    "created_at": CREATED,
    "updated_at": None,
    "learning_path": {"id": 7, "name": "Datos", "group_label": "Piloto"},
}
API_READINESS: dict[str, Any] = {
    "ready": False,
    "missing": ["item_bank"],
    "consents_accepted": 23,
    "consents_total": 25,
    "topics_total": 5,
    "topics_with_items": 4,
    "topics_with_equivalent_items": 3,
}
API_PREVIEW: dict[str, Any] = {
    "algorithm": "topological_threshold v1",
    "mastery_skip_threshold": 80.0,
    "pilot_arm": "fixed",
    "final_pass_threshold": 80.0,
    "steps": [
        {"step_order": 1, "topic_id": "101", "name": "Bases", "status": "pending"},
        {"step_order": 2, "topic_id": "102", "name": "ETL", "status": "blocked"},
    ],
}


def test_the_pilot_samples_are_valid_api_responses() -> None:
    assert _valid("PilotResponse", API_PILOT) == []
    assert _valid("ReadinessResponse", API_READINESS) == []
    assert _valid("Page_PilotResponse_", _page([API_PILOT])) == []


def test_the_newest_open_pilot_is_shown() -> None:
    closed = {**API_PILOT, "id": 9, "status": "closed"}
    assert pilot_to_show([API_PILOT, closed, {**API_PILOT, "id": 2}]) == 4
    assert pilot_to_show([closed]) == 9
    assert pilot_to_show([]) is None


def test_a_pilot_becomes_the_screen_model() -> None:
    pilot = Pilot.model_validate(pilot_from_api(API_PILOT, API_READINESS))
    assert (pilot.learning_path.name, pilot.learning_path.group_label) == ("Datos", "Piloto")
    assert pilot.status == "randomized"
    assert pilot.groups is not None and (pilot.groups.personalized, pilot.groups.fixed) == (12, 11)
    assert (pilot.consents.accepted, pilot.consents.total) == (23, 25)
    # Ítems equivalentes = versiones paralelas (`equivalence_group`), no temas con preguntas.
    assert (pilot.equivalent_items_topics, pilot.topics_total) == (3, 5)


def test_a_draft_pilot_has_no_groups_yet() -> None:
    draft = {**API_PILOT, "status": "draft", "arms": {"personalized": 0, "fixed": 0}}
    assert Pilot.model_validate(pilot_from_api(draft, API_READINESS)).groups is None


def test_the_fixed_preview_becomes_the_screen_model() -> None:
    preview = FixedPathPreview.model_validate(fixed_path_preview_from_api(API_PREVIEW))
    assert [(s.step_order, s.topic_id, s.name) for s in preview.steps] == [
        (1, 101, "Bases"),
        (2, 102, "ETL"),
    ]
    assert (preview.final_pass_threshold, preview.mastery_skip_threshold) == (80, 80)


def test_the_pilot_fixtures_pass_unchanged() -> None:
    preview = json.loads(
        (REPO_ROOT / "app" / "tests" / "fixtures" / "staff" / "fixed_path_preview.json").read_text(
            "utf-8"
        )
    )
    assert fixed_path_preview_from_api(preview) == preview


@respx.mock
def test_the_http_client_finds_and_reads_the_real_pilot() -> None:
    respx.get(f"{BASE}/api/v1/pilots").mock(
        return_value=httpx.Response(200, json=_page([API_PILOT]))
    )
    respx.get(f"{BASE}/api/v1/pilots/4").mock(return_value=httpx.Response(200, json=API_PILOT))
    respx.get(f"{BASE}/api/v1/pilots/4/readiness").mock(
        return_value=httpx.Response(200, json=API_READINESS)
    )
    respx.get(f"{BASE}/api/v1/pilots/4/fixed-path-preview").mock(
        return_value=httpx.Response(200, json=API_PREVIEW)
    )
    client = _client()
    pilot_id = client.find_pilot_id()
    assert pilot_id == 4
    pilot = client.get_pilot(4)
    assert pilot.consents.accepted == 23
    assert client.get_pilot_readiness(4).missing == ["item_bank"]
    assert client.get_fixed_path_preview(4).steps[1].name == "ETL"


# --- AD5 · Inscripciones -------------------------------------------------------------------

API_ENROLLMENT: dict[str, Any] = {
    "id": 31,
    "learning_path": {"id": 7, "name": "Datos", "group_label": "Piloto"},
    "status": "in_path",
    "objective": None,
    "progress": {"steps_total": 4, "steps_done": 1, "percent": 25},
    "pilot_arm": "fixed",
    "analysis_included": True,
    "next_action": {"type": "open_path", "screen": "E5"},
    "created_at": CREATED,
    "completed_at": None,
    "user_id": 21,
    "full_name": "Ana Pérez",
    "pilot_consent": True,
}


def test_the_enrollment_sample_is_a_valid_api_response() -> None:
    assert _valid("AdminEnrollmentResponse", API_ENROLLMENT) == []
    assert _valid("Page_AdminEnrollmentResponse_", _page([API_ENROLLMENT])) == []


def test_an_enrollment_becomes_the_screen_row() -> None:
    item = AdminEnrollment.model_validate(admin_enrollment_from_api(API_ENROLLMENT))
    assert (item.user.id, item.user.full_name) == (21, "Ana Pérez")
    assert (item.learning_path.name, item.pilot_arm) == ("Datos", "fixed")
    assert item.consent_accepted is True
    unknown_arm = {**API_ENROLLMENT, "pilot_arm": "otro", "pilot_consent": False}
    other = AdminEnrollment.model_validate(admin_enrollment_from_api(unknown_arm))
    assert (other.pilot_arm, other.consent_accepted) == (None, False)


@respx.mock
def test_the_http_client_reads_and_changes_real_enrollments() -> None:
    respx.get(f"{BASE}/api/v1/enrollments").mock(
        return_value=httpx.Response(200, json=_page([API_ENROLLMENT]))
    )
    respx.patch(f"{BASE}/api/v1/enrollments/31/withdraw").mock(
        return_value=httpx.Response(200, json={**API_ENROLLMENT, "status": "withdrawn"})
    )
    client = _client()
    assert client.list_admin_enrollments().items[0].user.full_name == "Ana Pérez"
    assert client.withdraw_enrollment(31, "Cambio de horario").status == "withdrawn"


# --- AD3 · Métricas ----------------------------------------------------------------------


def _metric(code: str, status: str, value: float | None, unit: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": f"Métrica {code}",
        "priority": "P3",
        "status": status,
        "value": value,
        "value_text": None,
        "unit": unit,
        "goal": "≥ 0,6",
        "detail": "n = 4",
    }


# Una respuesta como la de `GET /metrics/evaluation`: los valores sueltos más el catálogo.
API_METRICS: dict[str, Any] = {
    "learning_path_ids": [7],
    "grading": {"graded_by_human": 2, "qwk": 1.0},
    "groups": [
        {
            "title": "Métricas del sistema",
            "metrics": [
                _metric("m7", "meets", 1.0, "ratio"),
                _metric("m10", "not_met", 0.012, "percent"),
                _metric("m9", "meets", 14.2, "seconds"),
                _metric("m4", "no_data", None, "ratio"),
            ],
        }
    ],
}


def test_the_metrics_catalog_becomes_the_screen_model() -> None:
    metrics = MetricsEvaluation.model_validate(metrics_from_api(API_METRICS))
    assert (metrics.cohort, metrics.is_sample_data) == ("", False)
    entries = metrics.groups[0].metrics
    assert [(e.code, e.status) for e in entries] == [
        ("m7", "meets"),
        ("m10", "not_met"),
        ("m9", "meets"),
        ("m4", "no_data"),
    ]
    # La página formatea el número de la API con su unidad.
    assert [metric_text(e) for e in entries] == ["1,00", "1,2 %", "14,2 s", "—"]


def test_the_metrics_fixture_passes_unchanged() -> None:
    fixture = json.loads(
        (REPO_ROOT / "app" / "tests" / "fixtures" / "staff" / "metrics.json").read_text("utf-8")
    )
    assert metrics_from_api(fixture) == fixture
    first = MetricsEvaluation.model_validate(fixture).groups[0].metrics[0]
    assert metric_text(first) == first.value_text


@respx.mock
def test_the_http_client_reads_the_real_metrics() -> None:
    route = respx.get(f"{BASE}/api/v1/metrics/evaluation").mock(
        return_value=httpx.Response(200, json=API_METRICS)
    )
    client = _client()
    assert client.get_evaluation_metrics().groups[0].metrics[0].code == "m7"
    client.get_evaluation_metrics(7)
    assert route.calls.last.request.url.params["learning_path_id"] == "7"
