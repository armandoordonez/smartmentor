"""Instructor y administrador (tablero, ajustes, intentos extra, alertas, AD5) y propiedad.

Un objeto ajeno responde 404 con el código del recurso, nunca 403 (plan 18.2).
"""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    PublishedPath,
    answer_attempt,
    enrollment_in_path,
    instructor_client,
    key,
    learner_client,
    publish_path,
    seed_items,
    start_attempt,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def instructor(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    return await instructor_client(client_for, engine)


@pytest.fixture
async def stranger(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    return await instructor_client(client_for, engine, "otro")


@pytest.fixture
async def path(instructor: httpx.AsyncClient, engine: AsyncEngine) -> PublishedPath:
    published = await publish_path(instructor)
    for topic_id in published.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=1, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
        await seed_items(engine, topic_id, "final", choices=2)
    return published


@pytest.fixture
async def progressed(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath
) -> dict[str, Any]:
    """Una aprendiz en ruta con un quiz no aprobado y uno abierto."""
    learner = await learner_client(client_for, engine)
    enrollment_id = await enrollment_in_path(learner, path, diagnostic_correct={})
    route = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = next(s["step_id"] for s in route["steps"] if s["topic_id"] == path.fundamentals)
    failed = await start_attempt(learner, enrollment_id, step_id)
    result = (await answer_attempt(learner, engine, failed, correct=False)).json()
    graded_answer = result["answers"][0]["attempt_answer_id"]
    opened = await start_attempt(learner, enrollment_id, step_id)
    diagnostic_job = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/diagnostic")).json()
    return {
        "learner": learner,
        "enrollment": enrollment_id,
        "step": step_id,
        "attempt": opened["id"],
        "graded_attempt": failed["id"],
        "answer": graded_answer,
        "diagnostic_id": diagnostic_job["id"],
    }


async def test_dashboard_and_learner_detail(
    instructor: httpx.AsyncClient, path: PublishedPath, progressed: dict[str, Any]
) -> None:
    board = await instructor.get(f"{API}/learning-paths/{path.path_id}/dashboard")
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["kpi"]["learners"] == 1
    assert body["kpi"]["first_attempt_pass_rate"] == 0.0
    assert body["learners"][0]["full_name"]
    assert len(body["mastery_matrix"][0]["cells"]) == 3
    assert body["critical_topics"][0]["topic_id"] == path.fundamentals
    detail = await instructor.get(
        f"{API}/learning-paths/{path.path_id}/learners/{progressed['enrollment']}"
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert "email" not in data
    assert "description" not in data["profile"]
    assert len(data["level_by_topic"]) == 3
    assert [a["status"] for a in data["attempts"]] == ["graded", "created"]


async def test_settings_and_the_running_pilot_rule(
    instructor: httpx.AsyncClient, path: PublishedPath, engine: AsyncEngine
) -> None:
    url = f"{API}/learning-paths/{path.path_id}/settings"
    changed = await instructor.patch(
        url,
        json={
            "topic_pass_threshold": 75,
            "max_attempts": 4,
            "level_weights": {"test": 0.7, "profile": 0.2, "resume": 0.1},
            "default_objective": {"bloom_verb": "Aplicar", "content": "x", "criterion": "80 %"},
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["topic_pass_threshold"] == 75
    assert changed.json()["level_weights"] == {"test": 0.7, "profile": 0.2, "resume": 0.1}
    wrong = await instructor.patch(
        url, json={"level_weights": {"test": 0.7, "profile": 0.7, "resume": 0.1}}
    )
    assert wrong.status_code == 422
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO pilots (learning_path_id, starts_on, ends_on, status) "
                "VALUES (:path, DATE '2026-11-01', DATE '2026-12-01', 'running')"
            ),
            {"path": path.path_id},
        )
    blocked = await instructor.patch(url, json={"topic_pass_threshold": 60})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "PILOT_RUNNING"
    confirmed = await instructor.patch(
        url, json={"topic_pass_threshold": 60, "confirm_pilot_change": True}
    )
    assert confirmed.json()["topic_pass_threshold"] == 60


async def test_alerts_are_listed_and_marked_as_read(
    instructor: httpx.AsyncClient,
    stranger: httpx.AsyncClient,
    progressed: dict[str, Any],
) -> None:
    learner = progressed["learner"]
    # La primera respuesta del intento calificado es de opción múltiple: no admite revisión.
    refused = await learner.post(
        f"{API}/me/attempt-answers/{progressed['answer']}/review-request", json={}
    )
    assert refused.json()["code"] == "REVIEW_NOT_ALLOWED"
    result = (await learner.get(f"{API}/me/attempts/{progressed['graded_attempt']}/result")).json()
    short = next(a for a in result["answers"] if a["grading"]["grader"] == "llm_judge")
    created = await learner.post(
        f"{API}/me/attempt-answers/{short['attempt_answer_id']}/review-request", json={}
    )
    alert_id = created.json()["alert_id"]
    unread = (await instructor.get(f"{API}/alerts", params={"unread": True})).json()
    assert [a["id"] for a in unread["items"]] == [alert_id]
    assert (await stranger.patch(f"{API}/alerts/{alert_id}/read")).status_code == 404
    read = await instructor.patch(f"{API}/alerts/{alert_id}/read")
    assert read.json()["read_at"] is not None
    assert (await instructor.get(f"{API}/alerts", params={"unread": True})).json()["total"] == 0


async def test_admin_enrollments_list_withdraw_and_move(
    client: httpx.AsyncClient,
    instructor: httpx.AsyncClient,
    client_for: ClientFactory,
    engine: AsyncEngine,
    path: PublishedPath,
) -> None:
    second = await publish_path(instructor, "Estadística")
    learner = await learner_client(client_for, engine, "hugo")
    me = (await learner.get(f"{API}/me")).json()
    no_consent = await learner_client(client_for, engine, "ivan", consent=False)
    other = (await no_consent.get(f"{API}/me")).json()

    refused = await client.post(
        f"{API}/enrollments", json={"user_id": other["id"], "learning_path_id": path.path_id}
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "CONSENT_REQUIRED"
    created = await client.post(
        f"{API}/enrollments", json={"user_id": me["id"], "learning_path_id": path.path_id}
    )
    assert created.status_code == 201, created.text
    enrollment_id = created.json()["id"]
    listed = (
        await client.get(f"{API}/enrollments", params={"learning_path_id": path.path_id})
    ).json()
    assert [e["id"] for e in listed["items"]] == [enrollment_id]

    moved = await client.patch(
        f"{API}/enrollments/{enrollment_id}/move", json={"learning_path_id": second.path_id}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["learning_path"]["id"] == second.path_id
    assert moved.json()["analysis_included"] is False
    old = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert old["status"] == "withdrawn"
    assert old["next_action"]["type"] == "none"
    again = await client.patch(f"{API}/enrollments/{enrollment_id}/withdraw", json={})
    assert again.json()["code"] == "ENROLLMENT_CLOSED"
    withdrawn = await client.patch(f"{API}/enrollments/{moved.json()['id']}/withdraw", json={})
    assert withdrawn.json()["status"] == "withdrawn"
    assert (await learner.get(f"{API}/enrollments")).json()["code"] == "INSUFFICIENT_ROLE"


async def test_grants_need_an_owned_step_and_reactivate_an_exhausted_one(
    instructor: httpx.AsyncClient, stranger: httpx.AsyncClient, progressed: dict[str, Any]
) -> None:
    step, enrollment = progressed["step"], progressed["enrollment"]
    foreign = await stranger.post(f"{API}/path-steps/{step}/attempt-grants", json={"attempts": 1})
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "STEP_NOT_FOUND"
    foreign_final = await stranger.post(
        f"{API}/enrollments/{enrollment}/final-attempt-grants", json={"attempts": 1}
    )
    assert foreign_final.json()["code"] == "ENROLLMENT_NOT_FOUND"
    granted = await instructor.post(
        f"{API}/enrollments/{enrollment}/final-attempt-grants", json={"attempts": 2, "note": "x"}
    )
    assert granted.status_code == 201
    assert granted.json()["enrollment_id"] == enrollment
    step_grant = await instructor.post(f"{API}/path-steps/{step}/attempt-grants", json={})
    assert step_grant.status_code == 201
    assert step_grant.json()["path_step_id"] == step
    assert step_grant.json()["attempts"] == 1
    learner = progressed["learner"]
    route = (await learner.get(f"{API}/me/enrollments/{enrollment}/path")).json()
    granted_step = next(s for s in route["steps"] if s["step_id"] == step)
    assert granted_step["extra_attempts_granted"] == 1


# --- matriz de propiedad -------------------------------------------------------------------------

LEARNER_ROUTES: list[tuple[str, str, dict[str, Any] | None, str]] = [
    ("GET", "/me/enrollments/{enrollment}", None, "ENROLLMENT_NOT_FOUND"),
    ("POST", "/me/enrollments/{enrollment}/diagnostic", None, "ENROLLMENT_NOT_FOUND"),
    ("GET", "/me/enrollments/{enrollment}/diagnostic", None, "ENROLLMENT_NOT_FOUND"),
    (
        "PUT",
        "/me/enrollments/{enrollment}/diagnostic/answers",
        {"answers": []},
        "ENROLLMENT_NOT_FOUND",
    ),
    ("POST", "/me/enrollments/{enrollment}/diagnostic/submit", None, "ENROLLMENT_NOT_FOUND"),
    ("GET", "/me/enrollments/{enrollment}/diagnostic/result", None, "ENROLLMENT_NOT_FOUND"),
    (
        "PUT",
        "/me/enrollments/{enrollment}/objective",
        {"bloom_verb": "a", "content": "b", "criterion": "c"},
        "ENROLLMENT_NOT_FOUND",
    ),
    ("GET", "/me/enrollments/{enrollment}/path", None, "ENROLLMENT_NOT_FOUND"),
    ("GET", "/me/enrollments/{enrollment}/steps/{step}/content", None, "ENROLLMENT_NOT_FOUND"),
    (
        "POST",
        "/me/enrollments/{enrollment}/steps/{step}/attempts",
        {"assessment_type": "topic"},
        "ENROLLMENT_NOT_FOUND",
    ),
    ("GET", "/me/attempts/{attempt}", None, "ATTEMPT_NOT_FOUND"),
    ("PUT", "/me/attempts/{attempt}/answers", {"answers": []}, "ATTEMPT_NOT_FOUND"),
    ("POST", "/me/attempts/{attempt}/submit", None, "ATTEMPT_NOT_FOUND"),
    ("GET", "/me/attempts/{graded_attempt}/result", None, "ATTEMPT_NOT_FOUND"),
    ("POST", "/me/attempt-answers/{answer}/review-request", {}, "NOT_FOUND"),
    ("POST", "/me/enrollments/{enrollment}/final-attempts", None, "ENROLLMENT_NOT_FOUND"),
    ("GET", "/me/enrollments/{enrollment}/review-plan", None, "ENROLLMENT_NOT_FOUND"),
    ("GET", "/me/enrollments/{enrollment}/badge", None, "ENROLLMENT_NOT_FOUND"),
    (
        "POST",
        "/me/enrollments/{enrollment}/surveys/final",
        {"sus_items": [3] * 10},
        "ENROLLMENT_NOT_FOUND",
    ),
]


@pytest.mark.parametrize(("method", "template", "body", "code"), LEARNER_ROUTES)
async def test_another_learner_gets_404_on_every_learner_route(
    client_for: ClientFactory,
    engine: AsyncEngine,
    progressed: dict[str, Any],
    method: str,
    template: str,
    body: dict[str, Any] | None,
    code: str,
) -> None:
    intruder = await learner_client(client_for, engine, "intrusa")
    response = await intruder.request(
        method, API + template.format(**progressed), json=body, headers=key()
    )
    assert response.status_code == 404, f"{method} {template}: {response.text}"
    assert response.json()["code"] == code


async def test_foreign_events_and_jobs_are_404(
    client_for: ClientFactory, engine: AsyncEngine, progressed: dict[str, Any]
) -> None:
    intruder = await learner_client(client_for, engine, "intruso")
    events = await intruder.post(
        f"{API}/me/events",
        json={
            "events": [
                {
                    "enrollment_id": progressed["enrollment"],
                    "event_type": "topic.open",
                    "occurred_at": "2026-11-07T14:00:00Z",
                }
            ]
        },
    )
    assert events.status_code == 404
    assert events.json()["code"] == "ENROLLMENT_NOT_FOUND"


STAFF_ROUTES: list[tuple[str, str, dict[str, Any] | None, str]] = [
    ("PATCH", "/learning-paths/{path}/settings", {"max_attempts": 5}, "NOT_FOUND"),
    ("GET", "/learning-paths/{path}/dashboard", None, "NOT_FOUND"),
    ("GET", "/learning-paths/{path}/learners/{enrollment}", None, "NOT_FOUND"),
    ("POST", "/path-steps/{step}/attempt-grants", {"attempts": 1}, "STEP_NOT_FOUND"),
    (
        "POST",
        "/enrollments/{enrollment}/final-attempt-grants",
        {"attempts": 1},
        "ENROLLMENT_NOT_FOUND",
    ),
]


@pytest.mark.parametrize(("method", "template", "body", "code"), STAFF_ROUTES)
async def test_another_instructor_gets_404_on_every_path_route(
    stranger: httpx.AsyncClient,
    path: PublishedPath,
    progressed: dict[str, Any],
    method: str,
    template: str,
    body: dict[str, Any] | None,
    code: str,
) -> None:
    ids = {**progressed, "path": path.path_id}
    response = await stranger.request(method, API + template.format(**ids), json=body)
    assert response.status_code == 404, f"{method} {template}: {response.text}"
    assert response.json()["code"] == code


async def test_a_learner_cannot_use_staff_routes(
    progressed: dict[str, Any], path: PublishedPath
) -> None:
    learner = progressed["learner"]
    response = await learner.get(f"{API}/learning-paths/{path.path_id}/dashboard")
    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"
