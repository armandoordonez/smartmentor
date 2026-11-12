"""Observabilidad contra el esquema real: registro del LLM, vistas y métricas de evaluación."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory
from tests.integration.world_content import (
    API,
    Course,
    assign_evaluator,
    ingest_quiz_bank,
    ingest_videos,
    insert_enrollment,
    insert_short_answer,
    make_course,
    make_instructor,
    make_learner,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def course(engine: AsyncEngine, client_for: ClientFactory) -> Course:
    owner, owner_id = await make_instructor(engine, client_for, "duena")
    return await make_course(owner, owner_id)


async def insert_logs(engine: AsyncEngine, course_id: int | None) -> None:
    async with engine.begin() as conn:
        job = None
        if course_id is not None:
            job = (
                await conn.execute(
                    text(
                        "INSERT INTO ai_jobs (job_type, status, idempotency_key, input, attempts, "
                        "course_id) VALUES ('items.generate_quiz_bank', 'succeeded', 'k-obs', "
                        "CAST('{}' AS jsonb), 1, :c) RETURNING id"
                    ),
                    {"c": course_id},
                )
            ).scalar_one()
        rows = [
            ("items.generate_quiz_bank", "m-a", "topic_quiz", True, 100, 0.01, "success", job),
            (
                "items.generate_quiz_bank",
                "m-a",
                "topic_quiz",
                False,
                300,
                0.02,
                "invalid_output",
                job,
            ),
            ("content.explain_topic", "m-b", "topic_explanation", True, 500, 0.05, "success", None),
        ]
        for task, model, prompt, valid, latency, cost, status, job_id in rows:
            await conn.execute(
                text(
                    "INSERT INTO llm_call_logs (ai_job_id, provider, task, model, prompt_id, "
                    "prompt_version, input_sha256, json_valid, latency_ms, cost_usd, status) "
                    "VALUES (:j, 'fake', :t, :m, :p, 'v1', :h, :v, :l, :c, :s)"
                ),
                {
                    "j": job_id,
                    "t": task,
                    "m": model,
                    "p": prompt,
                    "h": "a" * 64,
                    "v": valid,
                    "l": latency,
                    "c": cost,
                    "s": status,
                },
            )


async def test_the_admin_filters_the_llm_call_log_and_reads_the_summary(
    client: httpx.AsyncClient, engine: AsyncEngine, course: Course
) -> None:
    await insert_logs(engine, course.id)
    everything = await client.get(f"{API}/llm-call-logs")
    assert everything.status_code == 200
    assert everything.json()["total"] == 3
    assert everything.json()["items"][0]["input_sha256"] == "a" * 64
    assert "input" not in everything.json()["items"][0]
    for params, expected in (
        ({"task": "content.explain_topic"}, 1),
        ({"model": "m-a"}, 2),
        ({"prompt_id": "topic_quiz", "status": "invalid_output"}, 1),
        ({"model": "inexistente"}, 0),
    ):
        filtered = await client.get(f"{API}/llm-call-logs", params=params)
        assert filtered.json()["total"] == expected, params
    page = await client.get(f"{API}/llm-call-logs", params={"limit": 1, "offset": 2})
    assert len(page.json()["items"]) == 1
    assert (await client.get(f"{API}/llm-call-logs", params={"status": "raro"})).status_code == 422

    summary = (await client.get(f"{API}/llm-call-logs/summary")).json()
    by_task = {t["task"]: t for t in summary["by_task"]}
    quiz = by_task["items.generate_quiz_bank"]
    assert quiz["calls"] == 2
    assert quiz["invalid_json_rate"] == 0.5
    assert quiz["latency_p50_ms"] == 200
    assert quiz["cost_usd"] == pytest.approx(0.03)
    assert summary["total_cost_usd"] == pytest.approx(0.08)
    assert {c["course_id"] for c in summary["by_course"]} == {course.id, None}
    only = (await client.get(f"{API}/llm-call-logs/summary", params={"model": "m-b"})).json()
    assert [t["task"] for t in only["by_task"]] == ["content.explain_topic"]


async def test_the_log_is_for_the_admin_only(
    course: Course,
    bare_client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    learner, _ = await make_learner(engine, client_for, "curioso")
    for path in ("/llm-call-logs", "/llm-call-logs/summary"):
        for who in (course.owner, learner):
            denied = await who.get(API + path)
            assert denied.status_code == 403
            assert denied.json()["code"] == "INSUFFICIENT_ROLE"
        assert (await bare_client.get(API + path)).status_code == 401
    assert (await learner.get(f"{API}/metrics/evaluation")).status_code == 403
    assert (await bare_client.get(f"{API}/metrics/evaluation")).status_code == 401


async def test_the_metrics_come_out_of_the_views_and_respect_ownership(
    course: Course,
    ai: FakeAiService,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    client_for: ClientFactory,
) -> None:
    topic = course.topic_ids[0]
    await ingest_quiz_bank(ai, course, topic)
    await ingest_videos(ai, course, topic)
    await insert_logs(engine, course.id)
    items = (await course.owner.get(f"{API}/topics/{topic}/items")).json()["items"]

    first, first_id = await make_instructor(engine, client_for, "eval-uno")
    second, second_id = await make_instructor(engine, client_for, "eval-dos")
    for evaluator_id in (first_id, second_id):
        await assign_evaluator(client, course, evaluator_id)
    verdicts = [
        ("valid", "valid"),
        ("invalid", "invalid"),
        ("valid", "invalid"),
        ("invalid", "invalid"),
    ]
    for item, (one, two) in zip(items, verdicts, strict=False):
        await first.post(f"{API}/items/{item['id']}/annotations", json={"verdict": one})
        await second.post(f"{API}/items/{item['id']}/annotations", json={"verdict": two})

    shorts = [i for i in items if i["item_type"] == "short_answer"]
    _, learner_id = await make_learner(engine, client_for, "aprendiz")
    enrollment = await insert_enrollment(engine, learner_id, course.path_id)
    perfect = await insert_short_answer(engine, enrollment, shorts[0]["id"], score=100)
    zero = await insert_short_answer(engine, enrollment, shorts[1]["id"], score=0)
    for answer, grade in ((perfect, 100), (zero, 0)):
        body = {
            "criteria": [{"criterion": "x", "met": grade > 0, "points_awarded": 1}],
            "score": grade,
            "sample_type": "random",
        }
        assert (
            await first.post(f"{API}/attempt-answers/{answer}/human-gradings", json=body)
        ).status_code == 201

    videos = (await course.owner.get(f"{API}/topics/{topic}/video-candidates")).json()["candidates"]
    for video, relevant in zip(videos, (True, True, False), strict=True):
        await course.owner.patch(
            f"{API}/video-candidates/{video['id']}", json={"is_relevant": relevant}
        )

    metrics = (await course.owner.get(f"{API}/metrics/evaluation")).json()
    assert metrics["learning_path_ids"] == [course.path_id]
    assert metrics["extraction"][0]["course_id"] == course.id
    validity = metrics["item_validity"]
    assert validity["items_with_two_evaluators"] == 4
    assert validity["valid_votes"] == 3
    assert validity["invalid_votes"] == 5
    assert validity["cohen_kappa"] == 0.5
    assert metrics["grading"] == {"graded_by_human": 2, "qwk": 1.0}
    assert metrics["videos"]["topics_judged"] == 1
    assert metrics["videos"]["precision_at_3"] == pytest.approx(2 / 3, abs=1e-3)
    assert metrics["videos"]["ndcg_at_3"] == pytest.approx(1.0)
    assert metrics["faithfulness"] == {"versions_measured": 0, "mean": None}
    assert metrics["llm"]["calls"] == 2
    assert metrics["llm"]["invalid_json_rate"] == 0.5
    assert metrics["steps"]["steps_passed"] == 0
    # Catálogo de AD3 (aditivo): la meta y el estado los decide la API.
    catalog = {e["code"]: e for g in metrics["groups"] for e in g["metrics"]}
    assert (catalog["m3"]["value"], catalog["m3"]["status"]) == (0.5, "not_met")  # κ < 0,6
    assert catalog["m7"]["status"] == "meets"  # QWK 1,0
    assert catalog["m10"]["status"] == "not_met"  # JSON inválido 50 %
    assert catalog["m4"]["status"] == "no_data"  # lo calcula el notebook

    assert (await client.get(f"{API}/metrics/evaluation")).json()["item_validity"]["items"] == 5
    by_path = await client.get(
        f"{API}/metrics/evaluation", params={"learning_path_id": course.path_id}
    )
    assert by_path.json()["learning_path_ids"] == [course.path_id]

    stranger, _ = await make_instructor(engine, client_for, "extrano")
    nothing = (await stranger.get(f"{API}/metrics/evaluation")).json()
    assert nothing["learning_path_ids"] == []
    assert nothing["item_validity"]["items"] == 0
    hidden = await stranger.get(
        f"{API}/metrics/evaluation", params={"learning_path_id": course.path_id}
    )
    assert hidden.status_code == 404
    assert (
        await client.get(f"{API}/metrics/evaluation", params={"learning_path_id": 9999})
    ).status_code == 404
