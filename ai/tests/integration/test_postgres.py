"""Integration against PostgreSQL (schema v2.0.0 by Liquibase) with the ``smartmentor_ai`` user.

Needs two URLs (skipped without them):

* ``AI_TEST_DATABASE_URL``: ``postgresql+asyncpg://smartmentor_ai:...@host:port/db`` (the service).
* ``AI_TEST_OWNER_DATABASE_URL``: an owner of the schema, only to seed business rows (courses,
  syllabus documents, topics) and to clean up between tests.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.adapters.budget import BudgetLimits, CallLogBudgetGuard
from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.postgres.cache import PostgresGenerationCache
from app.adapters.postgres.call_logs import PostgresCallLogRepository
from app.adapters.postgres.catalog import PostgresCatalogReader, ping
from app.adapters.postgres.jobs import PostgresJobRepository
from app.container import Container
from app.main import create_app
from app.ports.jobs import JobRefs, NewJob
from tests.conftest import make_container, make_token
from tests.integration.test_jobs_http import worker_for

AI_URL = os.environ.get("AI_TEST_DATABASE_URL")
OWNER_URL = os.environ.get("AI_TEST_OWNER_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (AI_URL and OWNER_URL),
        reason="AI_TEST_DATABASE_URL and AI_TEST_OWNER_DATABASE_URL are not set",
    ),
]

SYLLABUS_TEXT = "Unidad 1. Fundamentos de datos. Unidad 2. Regresión lineal. Unidad 3. Logística."


@pytest.fixture
async def engines() -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    assert AI_URL
    assert OWNER_URL
    ai = create_async_engine(AI_URL)
    owner = create_async_engine(OWNER_URL)
    async with owner.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE llm_call_logs, ai_generation_cache, ai_jobs, learning_outcomes, "
                "topics, syllabus_documents, courses RESTART IDENTITY CASCADE"
            )
        )
    yield ai, owner
    await ai.dispose()
    await owner.dispose()


async def seed(owner: AsyncEngine) -> dict[str, int]:
    async with owner.begin() as conn:
        course_id = (
            await conn.execute(
                text("INSERT INTO courses (name) VALUES ('Fundamentos de ML') RETURNING id")
            )
        ).scalar_one()
        document_id = (
            await conn.execute(
                text(
                    "INSERT INTO syllabus_documents (course_id, source_type, file_sha256, "
                    "extracted_text) VALUES (:c, 'text', repeat('a', 64), :t) RETURNING id"
                ),
                {"c": course_id, "t": SYLLABUS_TEXT},
            )
        ).scalar_one()
        topic_id = (
            await conn.execute(
                text(
                    "INSERT INTO topics (course_id, name, description, subtopics, position) "
                    "VALUES (:c, 'Regresión lineal', 'Modelos lineales', "
                    "'[\"Mínimos cuadrados\"]'::jsonb, 1) RETURNING id"
                ),
                {"c": course_id},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO learning_outcomes (topic_id, code, statement, bloom_level) "
                "VALUES (:t, 'lo_1', 'Aplicar mínimos cuadrados', 'apply')"
            ),
            {"t": topic_id},
        )
    return {"course_id": course_id, "document_id": document_id, "topic_id": topic_id}


def pg_container(ai: AsyncEngine, **overrides: Any) -> Container:
    async def _ping() -> None:
        await ping(ai)

    return make_container(
        jobs=PostgresJobRepository(ai),
        call_logs=PostgresCallLogRepository(ai),
        cache=PostgresGenerationCache(ai),
        catalog=PostgresCatalogReader(ai),
        database_ping=_ping,
        **overrides,
    )


async def http(container: Container) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(container)),
        base_url="http://ai.test",
        headers={"Authorization": f"Bearer {make_token()}"},
    )


def body(ids: dict[str, int], key: str = "syllabus.structure:document:1:v1") -> dict[str, Any]:
    return {
        "job_type": "syllabus.structure",
        "idempotency_key": key,
        "input": {"syllabus_document_id": ids["document_id"]},
        "refs": {"course_id": ids["course_id"]},
    }


async def drain(container: Container) -> None:
    while await worker_for(container).run_once() is not None:
        pass


async def test_syllabus_job_succeeds_and_is_logged(
    engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    ai, owner = engines
    ids = await seed(owner)
    container = pg_container(ai)
    assert await container.readiness() == []
    async with await http(container) as client:
        created = await client.post("/v1/jobs", json=body(ids))
        assert created.status_code == 202
        again = await client.post("/v1/jobs", json=body(ids))
        assert again.status_code == 200
        assert again.json()["job_id"] == created.json()["job_id"]
        await drain(container)
        job = (await client.get(f"/v1/jobs/{created.json()['job_id']}")).json()
    assert job["status"] == "succeeded"
    assert job["result"]["course_key"] == "fundamentos_machine_learning"
    assert job["cost_usd"] > 0
    async with owner.connect() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT l.json_valid, l.status, l.provider, l.prompt_id, l.cost_usd, "
                        "j.status AS job_status, j.attempts, j.input_sha256 "
                        "FROM llm_call_logs l JOIN ai_jobs j ON j.id = l.ai_job_id"
                    )
                )
            )
            .mappings()
            .one()
        )
    assert row["json_valid"] is True
    assert (row["status"], row["provider"], row["prompt_id"]) == (
        "success",
        "fake",
        "syllabus_structuring",
    )
    assert row["cost_usd"] > 0
    assert (row["job_status"], row["attempts"]) == ("succeeded", 1)
    assert len(row["input_sha256"]) == 64


async def test_invalid_json_fails_with_three_logged_attempts(
    engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    ai, owner = engines
    ids = await seed(owner)
    container = pg_container(ai)
    assert isinstance(container.llm, FakeLlmProvider)
    container.llm.script("syllabus_structuring", "{", "[]", "no")
    async with await http(container) as client:
        job_id = (await client.post("/v1/jobs", json=body(ids))).json()["job_id"]
        await drain(container)
        job = (await client.get(f"/v1/jobs/{job_id}")).json()
        assert job["error"]["code"] == "INVALID_OUTPUT"
        retry = await client.post(f"/v1/jobs/{job_id}/retry")
        assert retry.json()["status"] == "queued"
    logs = await PostgresCallLogRepository(ai).for_job(UUID(job["job_id"]))
    assert [(log.status, log.json_valid) for log in logs] == [("invalid_output", False)] * 3


async def test_budget_exceeded_and_cache(engines: tuple[AsyncEngine, AsyncEngine]) -> None:
    ai, owner = engines
    ids = await seed(owner)
    container = pg_container(ai)
    async with await http(container) as client:
        await client.post("/v1/jobs", json=body(ids))
        await drain(container)
        # Same document under another key: answered from ai_generation_cache.
        cached_id = (await client.post("/v1/jobs", json=body(ids, "k:2"))).json()["job_id"]
        await drain(container)
        cached = (await client.get(f"/v1/jobs/{cached_id}")).json()
        assert cached["result"]["meta"]["from_cache"] is True
        assert cached["cost_usd"] == 0
        # The course already spent more than a tiny cap.
        guard = container.budget
        assert isinstance(guard, CallLogBudgetGuard)
        guard._limits = BudgetLimits(course_usd=Decimal("0.000001"))
        other = body(ids, "k:3")
        async with owner.begin() as conn:
            await conn.execute(text("TRUNCATE ai_generation_cache"))
        blocked_id = (await client.post("/v1/jobs", json=other)).json()["job_id"]
        await drain(container)
        blocked = (await client.get(f"/v1/jobs/{blocked_id}")).json()
    assert blocked["error"]["code"] == "BUDGET_EXCEEDED"
    assert blocked["error"]["retryable"] is False
    logs = await PostgresCallLogRepository(ai).for_job(UUID(blocked_id))
    assert [log.status for log in logs] == ["budget_exceeded"]
    spent = await PostgresCallLogRepository(ai).spent_usd(course_id=ids["course_id"])
    assert spent > 0


async def test_skip_locked_gives_each_worker_a_different_job(
    engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    ai, _ = engines
    repo = PostgresJobRepository(ai)
    container = pg_container(ai)
    now = container.clock()
    for n in range(4):
        await repo.create_or_get(
            NewJob("items.review", f"key:{n}", {"n": n}, JobRefs(), "api"), now
        )
    claimed = await asyncio.gather(*(repo.claim_next(now, 60) for _ in range(4)))
    ids = [job.id for job in claimed if job is not None]
    assert len(ids) == len(set(ids)) == 4
    assert await repo.claim_next(now, 60) is None


async def test_ai_user_cannot_write_business_tables(
    engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    ai, _ = engines
    with pytest.raises(DBAPIError, match="permission denied"):
        async with ai.begin() as conn:
            await conn.execute(text("INSERT INTO courses (name) VALUES ('x')"))
