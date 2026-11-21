"""End to end through HTTP and the worker with ``FakeLlmProvider`` and in-memory repositories.

Same flows as the PostgreSQL integration tests (``test_postgres.py``), which reuse these
helpers against the real tables.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.memory import InMemoryCallLogRepository
from app.container import Container
from app.worker.loop import JobWorker
from tests.conftest import (
    COURSE_ID,
    SYLLABUS_DOCUMENT_ID,
    contract_errors,
    example_llm,
    make_token,
)


def worker_for(container: Container) -> JobWorker:
    return JobWorker(
        jobs=container.jobs,
        service=container.job_service,
        config=container.worker_config,
        clock=container.clock,
    )


def syllabus_job(key: str = "syllabus.structure:document:7:v1") -> dict[str, Any]:
    return {
        "job_type": "syllabus.structure",
        "idempotency_key": key,
        "input": {"syllabus_document_id": SYLLABUS_DOCUMENT_ID},
        "refs": {"course_id": COURSE_ID},
    }


async def run_job(client: httpx.AsyncClient, container: Container, body: dict[str, Any]) -> Any:
    created = await client.post("/v1/jobs", json=body)
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    while await worker_for(container).run_once() is not None:
        pass
    response = await client.get(f"/v1/jobs/{job_id}")
    assert response.status_code == 200
    return response.json()


async def test_syllabus_job_succeeds_and_is_logged(
    client: httpx.AsyncClient, container: Container, call_logs: InMemoryCallLogRepository
) -> None:
    job = await run_job(client, container, syllabus_job())
    assert job["status"] == "succeeded"
    assert job["contract"] == "syllabus.v1"
    assert contract_errors("syllabus.v1", job["result"]) == []
    assert job["attempts"] == 1
    assert job["cost_usd"] > 0
    [log] = call_logs.rows
    assert log.json_valid is True
    assert str(log.ai_job_id) == job["job_id"]
    assert log.course_id == COURSE_ID


async def test_idempotency(client: httpx.AsyncClient) -> None:
    first = await client.post("/v1/jobs", json=syllabus_job())
    again = await client.post("/v1/jobs", json=syllabus_job())
    assert (first.status_code, again.status_code) == (202, 200)
    assert first.json()["job_id"] == again.json()["job_id"]
    other = syllabus_job()
    other["input"]["syllabus_document_id"] = 99
    reused = await client.post("/v1/jobs", json=other)
    assert reused.status_code == 422
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_job_validation_errors(client: httpx.AsyncClient) -> None:
    unknown = await client.post("/v1/jobs", json={**syllabus_job(), "job_type": "nope"})
    assert unknown.json()["code"] == "UNKNOWN_JOB_TYPE"
    bad = await client.post("/v1/jobs", json={**syllabus_job(), "input": {"x": 1}})
    assert bad.status_code == 422
    body = bad.json()
    assert body["code"] == "INVALID_JOB_INPUT"
    assert body["errors"]
    assert "x" not in json.dumps([e.get("input") for e in body["errors"]])
    missing = await client.get("/v1/jobs/0b8e3c1e-6a4f-4f51-9a39-7d2a1f0c9e11")
    assert (missing.status_code, missing.json()["code"]) == (404, "JOB_NOT_FOUND")


async def test_invalid_output_fails_and_can_be_retried(
    client: httpx.AsyncClient, container: Container, fake_llm: FakeLlmProvider
) -> None:
    fake_llm.script("syllabus_structuring", "{", "{", "{")
    job = await run_job(client, container, syllabus_job())
    assert job["status"] == "failed"
    assert job["error"]["code"] == "INVALID_OUTPUT"
    assert job["error"]["retryable"] is True
    assert job["result"] is None
    retried = await client.post(f"/v1/jobs/{job['job_id']}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    await worker_for(container).run_once()
    final = (await client.get(f"/v1/jobs/{job['job_id']}")).json()
    assert final["status"] == "succeeded"
    assert final["attempts"] == 2


async def test_budget_exceeded_is_not_retryable(
    client: httpx.AsyncClient, container: Container
) -> None:
    from decimal import Decimal

    from app.adapters.budget import BudgetLimits, CallLogBudgetGuard

    guard = container.budget
    assert isinstance(guard, CallLogBudgetGuard)
    guard._limits = BudgetLimits(course_usd=Decimal(0))
    job = await run_job(client, container, syllabus_job())
    assert job["status"] == "failed"
    assert job["error"] == {
        "code": "BUDGET_EXCEEDED",
        "message": job["error"]["message"],
        "retryable": False,
    }
    retry = await client.post(f"/v1/jobs/{job['job_id']}/retry")
    assert (retry.status_code, retry.json()["code"]) == (409, "JOB_NOT_RETRYABLE")


async def test_transient_provider_error_is_requeued_by_the_worker(
    client: httpx.AsyncClient, container: Container, fake_llm: FakeLlmProvider
) -> None:
    from app.ports.llm import LlmProviderError

    fake_llm.script("syllabus_structuring", *[LlmProviderError("503")] * 3)
    created = (await client.post("/v1/jobs", json=syllabus_job())).json()
    await worker_for(container).run_once()
    job = (await client.get(f"/v1/jobs/{created['job_id']}")).json()
    assert job["status"] == "queued"
    assert await worker_for(container).run_once() is None  # backoff: not yet
    container.clock.advance(60)  # type: ignore[attr-defined]
    await worker_for(container).run_once()
    job = (await client.get(f"/v1/jobs/{created['job_id']}")).json()
    assert (job["status"], job["attempts"]) == ("succeeded", 2)


async def test_crashed_worker_lease_is_reclaimed(
    client: httpx.AsyncClient, container: Container
) -> None:
    created = (await client.post("/v1/jobs", json=syllabus_job())).json()
    claimed = await container.jobs.claim_next(container.clock(), 60)
    assert claimed is not None
    assert await container.jobs.claim_next(container.clock(), 60) is None
    container.clock.advance(61)  # type: ignore[attr-defined]
    await worker_for(container).run_once()
    job = (await client.get(f"/v1/jobs/{created['job_id']}")).json()
    assert (job["status"], job["attempts"]) == ("succeeded", 2)


async def test_diagnostic_generation_reviews_every_item(
    client: httpx.AsyncClient, container: Container, fake_llm: FakeLlmProvider
) -> None:
    body = {
        "job_type": "diagnostic.generate_items",
        "idempotency_key": "diagnostic.generate_items:course:3:v1",
        "input": {"course_id": COURSE_ID},
        "refs": {"course_id": COURSE_ID},
    }
    job = await run_job(client, container, body)
    assert job["status"] == "succeeded", job["error"]
    assert contract_errors("assessment_item_bank.v1", job["result"]) == []
    items = job["result"]["items"]
    assert {i["source"] for i in items} == {"diagnostic"}
    assert len(job["result"]["item_reviews"]) == len(items)
    review = fake_llm.calls("item_review")[0]
    assert review.model == "fake-small"


async def test_items_review_job(client: httpx.AsyncClient, container: Container) -> None:
    item = {
        "item_id": "301",
        "item_type": "multiple_choice",
        "bloom_level": "apply",
        "stem": "¿Qué partición evita la fuga de datos?",
        "options": ["a", "b", "c", "d"],
        "correct_option": 1,
        "rubric": [],
        "outcome": "Aplicar la partición correcta",
    }
    body = {
        "job_type": "items.review",
        "idempotency_key": "items.review:item:301:v1",
        "input": {"items": [item]},
    }
    job = await run_job(client, container, body)
    assert job["status"] == "succeeded"
    assert contract_errors("item_review.v1", job["result"]) == []
    assert job["result"]["discarded_item_ids"] == []


def finalize_input(mode: str) -> dict[str, Any]:
    items = [
        {
            "item_id": f"d{n}",
            "topic_id": t,
            "item_type": "multiple_choice",
            "difficulty": d,
            "correct_option": 1,
        }
        for n, (t, d) in enumerate(
            [
                ("fundamentos_datos", 1),
                ("fundamentos_datos", 3),
                ("regresion_lineal", 2),
                ("regresion_logistica", 2),
            ]
        )
    ]
    answers = [
        {"item_id": "d0", "selected_option": 1},
        {"item_id": "d1", "selected_option": 1},
        {"item_id": "d2", "dont_know": True},
        {"item_id": "d3", "selected_option": 0},
    ]
    body: dict[str, Any] = {
        "topic_ids": ["fundamentos_datos", "regresion_lineal", "regresion_logistica"],
        "items": items,
        "answers": answers,
        "profile_text": "Analista de datos; escríbeme a nadie@example.com. Uso regresión lineal.",
        "resume_text": None,
        "weights": {"test": 0.8, "profile": 0.1, "resume": 0.1},
        "thresholds": {"mastery_skip_threshold": 80, "reinforce_cutoff": 50},
        "objective_mode": mode,
        "path_objective": "Construir y evaluar modelos supervisados básicos.",
    }
    if mode == "path_default":
        body["path_objective_parts"] = {
            "bloom_verb": "Construir",
            "content": "modelos supervisados",
            "criterion": "con al menos 80 %",
        }
    return body


async def test_diagnostic_finalize_with_llm_objective(
    client: httpx.AsyncClient, container: Container, fake_llm: FakeLlmProvider
) -> None:
    body = {
        "job_type": "diagnostic.finalize",
        "idempotency_key": "diagnostic.finalize:enrollment:5:v1",
        "input": finalize_input("llm"),
        "refs": {"course_id": COURSE_ID},
    }
    job = await run_job(client, container, body)
    assert job["status"] == "succeeded", job["error"]
    assert contract_errors("diagnostic_finalization.v1", job["result"]) == []
    result = job["result"]
    assert result["objective"]["origin"] == "llm_proposed"
    levels = {t["topic_id"]: t for t in result["diagnostic_result"]["level_by_topic"]}
    assert levels["fundamentos_datos"]["test_score"] == 100.0
    assert levels["regresion_lineal"]["test_score"] == 0.0
    assert levels["fundamentos_datos"]["resume_prior"] is None
    # The e-mail never reaches the provider.
    prompt = fake_llm.calls("learning_objective")[0].user
    assert "nadie@example.com" not in prompt
    assert "[correo]" in prompt


async def test_diagnostic_finalize_with_path_default(
    client: httpx.AsyncClient, container: Container, fake_llm: FakeLlmProvider
) -> None:
    body = {
        "job_type": "diagnostic.finalize",
        "idempotency_key": "diagnostic.finalize:enrollment:6:v1",
        "input": finalize_input("path_default"),
    }
    job = await run_job(client, container, body)
    assert job["status"] == "succeeded"
    assert job["result"]["objective"]["origin"] == "path_default"
    assert job["result"]["objective"]["meta"] is None
    assert fake_llm.calls("learning_objective") == []


async def test_levels_estimate_and_path_sequence(client: httpx.AsyncClient) -> None:
    body = finalize_input("llm")
    for key in ("objective_mode", "path_objective"):
        body.pop(key)
    levels = await client.post("/v1/tasks/levels.estimate", json=body)
    assert levels.status_code == 200, levels.text
    assert contract_errors("diagnostic_result.v1", levels.json()) == []
    assert levels.json()["level_by_topic"][0]["profile_similarity"] is not None

    path = await client.post(
        "/v1/tasks/path.sequence",
        json={
            "topics": [
                {"topic_id": "10", "position": 1, "prerequisites": []},
                {"topic_id": "11", "position": 2, "prerequisites": ["10"]},
                {"topic_id": "12", "position": 3, "prerequisites": ["10", "11"]},
            ],
            "level_by_topic": [
                {"topic_id": "10", "level": 95.5},
                {"topic_id": "11", "level": 64.4},
                {"topic_id": "12", "level": 4.4},
            ],
            "mastery_skip_threshold": 80,
            "focus_topic_ids": ["12"],
            "pilot_arm": "personalized",
        },
    )
    assert path.status_code == 200
    assert contract_errors("learning_path.v1", path.json()) == []
    assert [s["status"] for s in path.json()["steps"]] == ["skipped", "pending", "blocked"]


async def test_path_sequence_errors(client: httpx.AsyncClient) -> None:
    self_loop = await client.post(
        "/v1/tasks/path.sequence",
        json={
            "topics": [{"topic_id": "a", "position": 1, "prerequisites": ["a"]}],
            "mastery_skip_threshold": 80,
        },
    )
    assert (self_loop.status_code, self_loop.json()["code"]) == (422, "PREREQUISITE_SELF")
    cycle = await client.post(
        "/v1/tasks/path.sequence",
        json={
            "topics": [
                {"topic_id": "a", "position": 1, "prerequisites": ["b"]},
                {"topic_id": "b", "position": 2, "prerequisites": ["a"]},
            ],
            "mastery_skip_threshold": 80,
        },
    )
    assert cycle.json()["code"] == "VALIDATION_ERROR"
    assert cycle.json()["cycle"]
    unknown = await client.post("/v1/tasks/no.such.task", json={})
    assert (unknown.status_code, unknown.json()["code"]) == (404, "UNKNOWN_TASK")


async def test_levels_estimate_unknown_topic(client: httpx.AsyncClient) -> None:
    body = finalize_input("llm")
    for key in ("objective_mode", "path_objective"):
        body.pop(key)
    body["topic_ids"] = ["fundamentos_datos", "no_existe"]
    response = await client.post("/v1/tasks/levels.estimate", json=body)
    assert (response.status_code, response.json()["code"]) == (422, "INPUT_REFERENCE_NOT_FOUND")


async def test_authentication(client: httpx.AsyncClient) -> None:
    no_token = await client.get("/v1/prompts", headers={"Authorization": ""})
    assert (no_token.status_code, no_token.json()["code"]) == (401, "MISSING_TOKEN")
    wrong = await client.get(
        "/v1/prompts", headers={"Authorization": f"Bearer {make_token(audience='smartmentor-api')}"}
    )
    assert (wrong.status_code, wrong.json()["code"]) == (401, "INVALID_TOKEN")
    expired = await client.get(
        "/v1/prompts", headers={"Authorization": f"Bearer {make_token(ttl=-60)}"}
    )
    assert expired.status_code == 401
    health = await client.get("/health", headers={"Authorization": ""})
    assert health.json() == {"status": "ok"}


async def test_ready_prompts_and_request_id(
    client: httpx.AsyncClient, container: Container
) -> None:
    ready = await client.get("/ready", headers={"X-Request-ID": "req-123"})
    assert ready.status_code == 200
    assert ready.headers["X-Request-ID"] == "req-123"
    await run_job(client, container, syllabus_job())
    catalog = (await client.get("/v1/prompts")).json()
    assert len(catalog["prompts"]) == 13
    syllabus = next(p for p in catalog["prompts"] if p["id"] == "syllabus_structuring")
    assert syllabus["versions"][0]["calls"] == 1
    one = await client.get("/v1/prompts/item_review")
    assert one.json()["versions"][0]["system"]
    missing = await client.get("/v1/prompts/nope")
    assert (missing.status_code, missing.json()["code"]) == (404, "PROMPT_NOT_FOUND")
    listed = (await client.get("/v1/jobs", params={"status": "succeeded"})).json()
    assert listed["total"] == 1


async def test_not_ready_is_problem_json() -> None:
    from app.main import create_app
    from tests.conftest import make_container, make_settings

    container = make_container(make_settings(ai_llm_model_default=None))
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://ai.test") as http:
        response = await http.get("/ready")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert "env:AI_LLM_MODEL_DEFAULT" in response.json()["missing"]


def test_example_answers_cover_the_test_catalog() -> None:
    topics = {i["topic_id"] for i in example_llm("diagnostic_generation")["items"]}
    assert topics == {"fundamentos_datos", "regresion_lineal", "regresion_logistica"}
