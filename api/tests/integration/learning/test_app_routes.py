"""Rutas que pidió la app (historial, metas, campos de los ítems) y reglas pendientes de F03c."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    PublishedPath,
    answer_attempt,
    enrollment_in_path,
    instructor_client,
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
async def path(instructor: httpx.AsyncClient, engine: AsyncEngine) -> PublishedPath:
    published = await publish_path(instructor)
    for topic_id in published.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=1, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
    return published


async def test_publishing_queues_the_diagnostic_bank(
    path: PublishedPath, ai: FakeAiService
) -> None:
    queued = [s for s in ai.submitted if s.job_type == "diagnostic.generate_items"]
    assert [s.input for s in queued] == [{"course_id": path.course_id}]


async def test_attempt_items_history_and_study_goals(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath
) -> None:
    learner = await learner_client(client_for, engine)
    enrollment_id = await enrollment_in_path(learner, path, diagnostic_correct={})
    route = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = next(s["step_id"] for s in route["steps"] if s["topic_id"] == path.fundamentals)
    attempt = await start_attempt(learner, enrollment_id, step_id)
    short = next(i for i in attempt["items"] if i["item_type"] == "short_answer")
    choice = next(i for i in attempt["items"] if i["item_type"] == "multiple_choice")
    assert short["topic_name"] == "Fundamentos"
    assert short["bloom_level"] == "apply"
    assert short["rubric_summary"] == (
        "concepto clave (40 %) · ejemplo aplicado (30 %) · conclusión clara (30 %)"
    )
    assert choice["rubric_summary"] is None
    assert "model_answer" not in short

    empty = await learner.get(f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/attempts")
    assert empty.json() == []
    await answer_attempt(learner, engine, attempt, correct=False)
    history = (
        await learner.get(f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/attempts")
    ).json()
    assert len(history) == 1
    assert history[0]["number"] == 1
    assert history[0]["total"] == 5
    assert history[0]["correct"] == 0
    assert history[0]["extra_grant"] is False
    assert (await learner.get(f"{API}/me/enrollments/{enrollment_id}/final/attempts")).json() == []
    foreign_step = await learner.get(f"{API}/me/enrollments/{enrollment_id}/steps/999999/attempts")
    assert foreign_step.json()["code"] == "STEP_NOT_FOUND"

    missing = await learner.get(f"{API}/me/study-goals")
    assert missing.status_code == 404
    saved = await learner.put(
        f"{API}/me/study-goals", json={"daily_minutes_goal": 30, "monthly_topics_goal": 3}
    )
    assert saved.status_code == 200, saved.text
    await learner.post(
        f"{API}/me/events",
        json={
            "events": [
                {
                    "enrollment_id": enrollment_id,
                    "event_type": "topic.close",
                    "occurred_at": "2099-01-01T00:00:00Z",
                    "payload": {"seconds": 1},
                }
            ]
        },
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO interaction_events (enrollment_id, event_type, occurred_at, payload) "
                "VALUES (:e, 'topic.close', now(), '{\"seconds\": 600}'::jsonb)"
            ),
            {"e": enrollment_id},
        )
    goals = (await learner.get(f"{API}/me/study-goals")).json()
    assert goals["daily_minutes_goal"] == 30
    assert goals["daily_minutes_done"] == 10
    assert goals["monthly_topics_goal"] == 3
    assert goals["monthly_topics_done"] == 0
    assert goals["streak_days"] == 1
    assert goals["daily_options"] == [15, 30, 45]
    wrong = await learner.put(
        f"{API}/me/study-goals", json={"daily_minutes_goal": 0, "monthly_topics_goal": 3}
    )
    assert wrong.status_code == 422


async def test_an_enrollment_after_the_draw_gets_a_pilot_arm(
    client_for: ClientFactory, engine: AsyncEngine, path: PublishedPath
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO pilots (learning_path_id, starts_on, ends_on, status) "
                "VALUES (:p, DATE '2026-11-01', DATE '2026-12-01', 'randomized')"
            ),
            {"p": path.path_id},
        )
    volunteer = await learner_client(client_for, engine, "vale")
    await volunteer.post(
        f"{API}/me/consents", json={"consent_type": "pilot_research", "document_version": "1.0"}
    )
    joined = (
        await volunteer.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    assert joined["pilot_arm"] == "personalized"
    assert joined["analysis_included"] is True
    other = await learner_client(client_for, engine, "wil")
    await other.post(
        f"{API}/me/consents", json={"consent_type": "pilot_research", "document_version": "1.0"}
    )
    second = (
        await other.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    assert second["pilot_arm"] == "fixed"  # equilibra los grupos
    outsider = await learner_client(client_for, engine, "xio")
    third = (
        await outsider.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    assert third["pilot_arm"] is None
    assert third["analysis_included"] is False


async def test_grading_a_requested_review_marks_the_alert_as_read(
    client: httpx.AsyncClient,
    instructor: httpx.AsyncClient,
    client_for: ClientFactory,
    engine: AsyncEngine,
    path: PublishedPath,
) -> None:
    learner = await learner_client(client_for, engine)
    enrollment_id = await enrollment_in_path(learner, path, diagnostic_correct={})
    route = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step_id = next(s["step_id"] for s in route["steps"] if s["topic_id"] == path.fundamentals)
    attempt = await start_attempt(learner, enrollment_id, step_id)
    result = (await answer_attempt(learner, engine, attempt, correct=True)).json()
    short = next(a for a in result["answers"] if a["grading"]["grader"] == "llm_judge")
    requested = await learner.post(
        f"{API}/me/attempt-answers/{short['attempt_answer_id']}/review-request", json={}
    )
    assert requested.status_code == 201

    evaluator = await instructor_client(client_for, engine, "evaluadora")
    me = (await evaluator.get(f"{API}/me")).json()
    assigned = await client.post(
        f"{API}/courses/{path.course_id}/evaluators", json={"user_id": me["id"]}
    )
    assert assigned.status_code == 201, assigned.text
    graded = await evaluator.post(
        f"{API}/attempt-answers/{short['attempt_answer_id']}/human-gradings",
        json={
            "criteria": [{"criterion": "concepto clave", "met": True, "points_awarded": 0.4}],
            "score": 80,
            "sample_type": "learner_request",
        },
    )
    assert graded.status_code == 201, graded.text
    unread = (await instructor.get(f"{API}/alerts", params={"unread": True})).json()
    assert unread["total"] == 0
