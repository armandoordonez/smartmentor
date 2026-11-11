"""Flujo completo del aprendiz con `FakeAiService` contra el esquema real (salida de la Fase 3).

inscripción → diagnóstico → objetivo → ruta → quiz (con generación bajo demanda, intentos agotados
e intentos extra) → final → badge → encuesta, más las reglas de cada paso.
"""

import json
import uuid
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    TWO_OF_THREE,
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

SCHEMAS = Path(__file__).resolve().parents[4] / "prompts" / "schemas"


@pytest.fixture
async def instructor(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    return await instructor_client(client_for, engine)


@pytest.fixture
async def path(instructor: httpx.AsyncClient, engine: AsyncEngine) -> PublishedPath:
    published = await publish_path(instructor)
    for topic_id in published.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=1, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
        await seed_items(engine, topic_id, "final", choices=4)
    return published


@pytest.fixture
async def learner(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    return await learner_client(client_for, engine)


def steps_by_topic(path_body: dict[str, object]) -> dict[int, dict[str, object]]:
    steps = path_body["steps"]
    assert isinstance(steps, list)
    return {int(s["topic_id"]): s for s in steps}


async def test_the_whole_learner_flow_from_enrollment_to_badge(
    instructor: httpx.AsyncClient,
    learner: httpx.AsyncClient,
    bare_client: httpx.AsyncClient,
    path: PublishedPath,
    engine: AsyncEngine,
) -> None:
    # Catálogo e inscripción
    catalog = (await learner.get(f"{API}/learning-paths")).json()
    card = next(c for c in catalog["items"] if c["id"] == path.path_id)
    assert card["topic_count"] == 3
    assert card["enrolled"] is False
    created = await learner.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    assert created.status_code == 201, created.text
    enrollment = created.json()
    enrollment_id = enrollment["id"]
    assert enrollment["status"] == "diagnosing"
    assert enrollment["next_action"]["type"] == "start_diagnostic"
    again = await learner.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    assert again.status_code == 409
    assert again.json()["code"] == "ENROLLMENT_ALREADY_EXISTS"

    # Diagnóstico: domina fundamentos y regresión lineal; no sabe regresión logística
    diagnostic = await learner.post(f"{API}/me/enrollments/{enrollment_id}/diagnostic")
    assert diagnostic.status_code == 201, diagnostic.text
    items = diagnostic.json()["items"]
    assert len(items) == 3
    assert all("correct_option" not in i for i in items)
    duplicated = await learner.post(f"{API}/me/enrollments/{enrollment_id}/diagnostic")
    assert duplicated.json()["code"] == "DIAGNOSTIC_ALREADY_EXISTS"
    answers = [
        {"item_id": i["item_id"], "selected_option": 1}
        if i["topic_id"] != path.logistic
        else {"item_id": i["item_id"], "dont_know": True}
        for i in items
    ]
    saved = await learner.put(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/answers", json={"answers": answers[:1]}
    )
    assert saved.json() == {"saved": 1}
    await learner.put(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/answers", json={"answers": answers}
    )
    stored = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/diagnostic")).json()
    assert stored["status"] == "in_progress"
    assert len(stored["answers"]) == 3
    not_ready = await learner.get(f"{API}/me/enrollments/{enrollment_id}/diagnostic/result")
    assert not_ready.json()["code"] == "DIAGNOSTIC_NOT_READY"

    submit_key = key()
    submitted = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/submit", headers=submit_key
    )
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["job_id"]
    replay = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/submit", headers=submit_key
    )
    assert replay.json()["job_id"] == job_id
    waiting = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert waiting["next_action"] == {
        "type": "wait_job",
        "step_id": None,
        "attempt_id": None,
        "job_id": job_id,
        "screen": "U1a",
    }
    polled = (await learner.get(f"{API}/jobs/{job_id}")).json()
    assert polled["ingested"] is True
    assert polled["status"] == "succeeded"
    result = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/diagnostic/result")).json()
    levels = {t["topic_id"]: t for t in result["level_by_topic"]}
    assert levels[path.linear]["classification"] == "mastered"
    assert levels[path.logistic]["classification"] == "to_learn"
    assert result["proposed_objective"]["origin"] == "llm_proposed"

    # Objetivo en tres partes
    incomplete = await learner.put(
        f"{API}/me/enrollments/{enrollment_id}/objective",
        json={"bloom_verb": "Aplicar", "content": "la regresión", "criterion": " "},
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["code"] == "OBJECTIVE_NOT_MEASURABLE"
    assert incomplete.json()["missing"] == ["criterion"]
    confirmed = await learner.put(
        f"{API}/me/enrollments/{enrollment_id}/objective",
        json={"bloom_verb": "Construir", "content": "un modelo", "criterion": "con 80 %"},
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["status"] == "in_path"
    assert body["objective"]["origin"] == "learner_edited"

    # Ruta: fundamentos es obligatorio (no se omite), lineal se omite, logística espera
    route = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    steps = steps_by_topic(route)
    assert steps[path.fundamentals]["status"] == "pending"
    assert steps[path.fundamentals]["inclusion_reason"] == "mandatory"
    assert steps[path.linear]["status"] == "skipped"
    assert steps[path.linear]["inclusion_reason"] == "skipped_mastered"
    assert steps[path.logistic]["status"] == "blocked"
    assert route["savings"] == {"skipped_topics": 1, "skipped_minutes": 90}
    assert route["final"]["locked"] is True
    assert body["next_action"]["step_id"] == steps[path.fundamentals]["step_id"]
    fundamentals = int(steps[path.fundamentals]["step_id"])
    logistic = int(steps[path.logistic]["step_id"])

    blocked = await learner.get(f"{API}/me/enrollments/{enrollment_id}/steps/{logistic}/content")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "STEP_NOT_AVAILABLE"
    locked = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/final-attempts", headers=key()
    )
    assert locked.status_code == 422
    assert locked.json()["code"] == "FINAL_ASSESSMENT_LOCKED"

    content = await learner.get(
        f"{API}/me/enrollments/{enrollment_id}/steps/{fundamentals}/content"
    )
    assert content.status_code == 200, content.text
    assert content.json()["status"] == "in_progress"
    assert content.json()["attempts"] == {"used": 0, "max": 3, "extra_granted": 0, "remaining": 3}

    # Quiz de fundamentos: 4 de opción múltiple + 1 respuesta corta con 2 de 3 criterios
    no_key = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/steps/{fundamentals}/attempts",
        json={"assessment_type": "topic"},
    )
    assert no_key.status_code == 428
    attempt = await start_attempt(learner, enrollment_id, fundamentals)
    assert len(attempt["items"]) == 5
    assert sum(1 for i in attempt["items"] if i["item_type"] == "short_answer") == 1
    open_again = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/steps/{fundamentals}/attempts",
        json={"assessment_type": "topic"},
        headers=key(),
    )
    assert open_again.json()["code"] == "ATTEMPT_IN_PROGRESS"
    first = (
        await answer_attempt(learner, engine, attempt, correct=True, short_text=TWO_OF_THREE)
    ).json()
    assert first["passed"] is True
    assert first["score"] == 94.0
    short = next(a for a in first["answers"] if a["grading"]["item_type"] == "short_answer")
    assert short["grading"]["criteria_met"] == 2
    assert short["grading"]["is_correct"] is True
    assert first["attempts"] == {"used": 1, "max": 3, "remaining": 2}
    assert first["next_action"]["type"] == "study_topic"
    assert first["next_action"]["step_id"] == logistic

    # Revisión humana: solo respuestas cortas calificadas por el LLM
    review = await learner.post(
        f"{API}/me/attempt-answers/{short['attempt_answer_id']}/review-request", json={}
    )
    assert review.status_code == 201
    assert review.json()["alert_id"] is not None
    repeated = await learner.post(
        f"{API}/me/attempt-answers/{short['attempt_answer_id']}/review-request", json={}
    )
    assert repeated.json()["code"] == "REVIEW_ALREADY_REQUESTED"
    choice = next(a for a in first["answers"] if a["grading"]["item_type"] == "multiple_choice")
    refused = await learner.post(
        f"{API}/me/attempt-answers/{choice['attempt_answer_id']}/review-request", json={}
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "REVIEW_NOT_ALLOWED"

    # Regresión logística: tres intentos fallidos (los dos últimos con ítems generados bajo
    # demanda, nunca repetidos), intentos agotados y alerta al instructor
    seen: set[int] = set()
    for number in range(1, 4):
        attempt = await start_attempt(learner, enrollment_id, logistic)
        ids = {i["item_id"] for i in attempt["items"]}
        assert not ids & seen, "un intento repitió preguntas"
        seen |= ids
        failed = (await answer_attempt(learner, engine, attempt, correct=False)).json()
        assert failed["passed"] is False
        assert failed["attempts"]["used"] == number
    exhausted = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert exhausted["next_action"]["type"] == "wait_instructor"
    assert exhausted["next_action"]["step_id"] == logistic
    no_more = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/steps/{logistic}/attempts",
        json={"assessment_type": "topic"},
        headers=key(),
    )
    assert no_more.status_code == 422
    assert no_more.json()["code"] == "MAX_ATTEMPTS_EXCEEDED"
    assert no_more.json()["attempts_used"] == 3
    assert no_more.json()["max_attempts"] == 3
    alerts = (await instructor.get(f"{API}/alerts", params={"unread": True})).json()
    assert {a["alert_type"] for a in alerts["items"]} == {
        "review_requested",
        "topic_attempts_exhausted",
    }

    # Intento extra (fuera del conteo de la regla) y aprobación
    grant = await instructor.post(
        f"{API}/path-steps/{logistic}/attempt-grants",
        json={"attempts": 1, "note": "Un intento más"},
    )
    assert grant.status_code == 201, grant.text
    extra = await start_attempt(learner, enrollment_id, logistic)
    passed = (await answer_attempt(learner, engine, extra, correct=True)).json()
    assert passed["passed"] is True
    assert passed["attempts"] == {"used": 4, "max": 4, "remaining": 0}
    detail = (
        await instructor.get(f"{API}/learning-paths/{path.path_id}/learners/{enrollment_id}")
    ).json()
    assert [a["uses_extra_grant"] for a in detail["attempts"] if a["step_id"] == logistic] == [
        False,
        False,
        False,
        True,
    ]
    ready = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert ready["status"] == "final_ready"
    assert ready["next_action"]["type"] == "take_final"
    assert ready["progress"] == {"steps_total": 3, "steps_done": 3, "percent": 100}

    # Evaluación final: una no aprobada (repaso) y otra aprobada (badge)
    final = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/final-attempts", headers=key()
    )
    assert final.status_code == 201, final.text
    assert len(final.json()["items"]) == 10
    failed_final = (await answer_attempt(learner, engine, final.json(), correct=False)).json()
    assert failed_final["passed"] is False
    assert failed_final["pass_threshold"] == 80
    assert failed_final["next_action"]["type"] == "review_final"
    plan = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/review-plan")).json()
    assert {w["topic_id"] for w in plan["weak_topics"]} == set(path.topics.values())
    final = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/final-attempts", headers=key()
    )
    final_ids = {i["item_id"] for i in final.json()["items"]}
    assert len(final_ids) == 2
    passed_final = (await answer_attempt(learner, engine, final.json(), correct=True)).json()
    assert passed_final["passed"] is True
    assert passed_final["next_action"]["type"] == "answer_survey"
    completed = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    # Badge: verificación «hosted» pública y solo con datos con hash
    mine = (await learner.get(f"{API}/me/badges")).json()
    assert len(mine) == 1
    badge = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/badge")).json()
    assertion = await bare_client.get(badge["assertion_url"])
    assert assertion.status_code == 200, assertion.text
    schema = json.loads((SCHEMAS / "badge.v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(assertion.json())
    assert assertion.json()["id"].startswith("http://test/api/v1/badges/")
    assert "ana@example.com" not in assertion.text
    image = await bare_client.get(badge["image_url"])
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")
    missing = await bare_client.get(f"{API}/badges/{uuid.uuid4()}/assertion.json")
    assert missing.status_code == 404
    assert missing.json()["code"] == "BADGE_NOT_FOUND"

    # Encuesta final con SUS
    survey = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/surveys/final",
        json={"likert": {"q1": 5}, "sus_items": [4, 2, 5, 1, 4, 2, 5, 1, 4, 2], "comment": "Útil"},
    )
    assert survey.status_code == 201
    assert survey.json()["sus_score"] == 85.0
    twice = await learner.post(
        f"{API}/me/enrollments/{enrollment_id}/surveys/final",
        json={"sus_items": [3] * 10},
    )
    assert twice.json()["code"] == "SURVEY_ALREADY_SUBMITTED"
    final_state = (await learner.get(f"{API}/me/enrollments/{enrollment_id}")).json()
    assert final_state["next_action"]["type"] == "view_badge"

    # Eventos de tiempo en tarea
    events = await learner.post(
        f"{API}/me/events",
        json={
            "events": [
                {
                    "enrollment_id": enrollment_id,
                    "event_type": "topic.open",
                    "topic_id": path.fundamentals,
                    "occurred_at": "2026-11-07T14:00:00Z",
                },
                {
                    "enrollment_id": enrollment_id,
                    "event_type": "topic.close",
                    "occurred_at": "2026-11-07T14:10:00Z",
                    "payload": {"seconds": 600},
                },
            ]
        },
    )
    assert events.status_code == 202
    assert events.json() == {"accepted": 2}
    async with engine.connect() as conn:
        stored_events = (
            await conn.execute(text("SELECT count(*) FROM interaction_events"))
        ).scalar_one()
    assert stored_events == 2


async def test_consent_is_required_to_enroll(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath
) -> None:
    http = await learner_client(client_for, engine, "sin", consent=False)
    refused = await http.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    assert refused.status_code == 403
    assert refused.json()["code"] == "CONSENT_REQUIRED"


async def test_only_published_paths_accept_enrollments(
    instructor: httpx.AsyncClient, learner: httpx.AsyncClient
) -> None:
    draft = (await instructor.post(f"{API}/courses", json={"name": "Borrador"})).json()
    refused = await learner.post(
        f"{API}/me/enrollments", json={"learning_path_id": draft["learning_path"]["id"]}
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "LEARNING_PATH_NOT_PUBLISHED"
    catalog = (await learner.get(f"{API}/learning-paths")).json()
    assert catalog["total"] == 0


async def test_an_archived_course_leaves_the_catalog_and_refuses_enrollments(
    instructor: httpx.AsyncClient, learner: httpx.AsyncClient, path: PublishedPath
) -> None:
    before = (await learner.get(f"{API}/learning-paths")).json()
    assert path.path_id in [c["id"] for c in before["items"]]

    archived = await instructor.post(f"{API}/courses/{path.course_id}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    after = (await learner.get(f"{API}/learning-paths")).json()
    assert path.path_id not in [c["id"] for c in after["items"]]
    assert after["total"] == before["total"] - 1
    refused = await learner.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    assert (refused.status_code, refused.json()["code"]) == (422, "LEARNING_PATH_NOT_PUBLISHED")


async def test_profile_completion_and_recalculation(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath
) -> None:
    """Sin descripción, `profiling`; al guardarla, `diagnosing`. En ruta, recalcula (E15)."""
    http = await learner_client(client_for, engine, "bea", description=None)
    created = (
        await http.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    assert created["status"] == "profiling"
    assert created["next_action"]["type"] == "complete_profile"
    early = await http.post(f"{API}/me/enrollments/{created['id']}/diagnostic")
    assert early.status_code == 422
    assert early.json()["code"] == "PROFILE_INCOMPLETE"
    saved = (await http.put(f"{API}/me/profile", json={"description": "Analista"})).json()
    assert saved["recalculated_enrollment_ids"] == [created["id"]]
    assert (await http.get(f"{API}/me/enrollments/{created['id']}")).json()[
        "status"
    ] == "diagnosing"

    other = await learner_client(client_for, engine, "cami")
    enrollment_id = await enrollment_in_path(
        other, path, diagnostic_correct={path.fundamentals: True}
    )
    changed = (
        await other.put(
            f"{API}/me/profile",
            json={"description": "Ahora soy científica de datos", "job_title": "Científica"},
        )
    ).json()
    assert changed["recalculated_enrollment_ids"] == [enrollment_id]


async def test_short_answer_below_two_of_three_criteria_is_not_correct(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath, ai: FakeAiService
) -> None:
    http = await learner_client(client_for, engine, "dani")
    enrollment_id = await enrollment_in_path(
        http, path, diagnostic_correct={path.fundamentals: True}
    )
    route = (await http.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = steps_by_topic(route)[path.fundamentals]["step_id"]
    attempt = await start_attempt(http, enrollment_id, int(step_id))
    result = (
        await answer_attempt(http, engine, attempt, correct=True, short_text="solo el concepto")
    ).json()
    short = next(a for a in result["answers"] if a["grading"]["item_type"] == "short_answer")
    assert short["grading"]["criteria_met"] == 1
    assert short["grading"]["is_correct"] is False
    assert any(s.job_type == "grading.short_answer" for s in ai.submitted)


async def test_a_grading_job_that_fails_leaves_the_attempt_in_grading_failed(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath, ai: FakeAiService
) -> None:
    http = await learner_client(client_for, engine, "eli")
    enrollment_id = await enrollment_in_path(http, path, diagnostic_correct={})
    route = (await http.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = int(steps_by_topic(route)[path.fundamentals]["step_id"])
    attempt = await start_attempt(http, enrollment_id, step_id)
    ai.fail_next("grading.short_answer")
    submitted = await http.post(f"{API}/me/attempts/{attempt['id']}/submit", headers=key())
    assert submitted.status_code == 202
    polled = await http.get(submitted.json()["poll_url"])
    assert polled.status_code == 502
    assert polled.json()["code"] == "AI_TASK_FAILED"
    stored = (await http.get(f"{API}/me/attempts/{attempt['id']}")).json()
    assert stored["status"] == "grading_failed"
    not_graded = await http.get(f"{API}/me/attempts/{attempt['id']}/result")
    assert not_graded.json()["code"] == "ATTEMPT_NOT_GRADED"


async def test_an_exhausted_bank_answers_202_until_the_new_items_are_ingested(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath, ai: FakeAiService
) -> None:
    http = await learner_client(client_for, engine, "fer")
    enrollment_id = await enrollment_in_path(http, path, diagnostic_correct={})
    route = (await http.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = int(steps_by_topic(route)[path.fundamentals]["step_id"])
    first = await start_attempt(http, enrollment_id, step_id)
    await answer_attempt(http, engine, first, correct=False)
    ai.auto_complete = False
    pending = await http.post(
        f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/attempts",
        json={"assessment_type": "topic"},
        headers=key(),
    )
    assert pending.status_code == 202, pending.text
    assert pending.headers["Location"] == pending.json()["poll_url"]
    running = (await http.get(pending.json()["poll_url"])).json()
    assert running["ingested"] is False
    ai.complete(pending.json()["job_id"])
    assert (await http.get(pending.json()["poll_url"])).json()["ingested"] is True
    ai.auto_complete = True
    second = await start_attempt(http, enrollment_id, step_id)
    assert not {i["item_id"] for i in second["items"]} & {i["item_id"] for i in first["items"]}


async def test_the_sweep_ingests_a_diagnostic_nobody_polled(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath, ai: FakeAiService
) -> None:
    from app.domains.ai_gateway.sweeper import sweep_once
    from app.main import app

    http = await learner_client(client_for, engine, "gil")
    enrollment = (
        await http.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    await http.post(f"{API}/me/enrollments/{enrollment['id']}/diagnostic")
    await http.post(f"{API}/me/enrollments/{enrollment['id']}/diagnostic/submit", headers=key())
    assert await sweep_once(app.state.session_factory, ai) >= 1
    state = (await http.get(f"{API}/me/enrollments/{enrollment['id']}")).json()
    assert state["status"] == "objective_pending"
    assert state["next_action"]["type"] == "confirm_objective"
