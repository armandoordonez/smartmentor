"""Mundo de pruebas compartido por contenido, evaluación, piloto y observabilidad.

Un curso con tres temas (ingeridos del syllabus de `FakeAiService`), su dueño, un extraño y
utilidades para encolar y ingerir trabajos de contenido con el `FakeAiService` de la aplicación.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.entities import JobRefs
from app.domains.ai_gateway.fake import FakeAiService
from tests.integration.conftest import ClientFactory, insert_user

API = "/api/v1"


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@dataclass
class Course:
    id: int
    path_id: int
    topic_ids: list[int]
    owner: httpx.AsyncClient
    owner_id: int


async def make_instructor(
    engine: AsyncEngine, client_for: ClientFactory, name: str
) -> tuple[httpx.AsyncClient, int]:
    email = f"{name}@example.com"
    user_id = await insert_user(
        engine, email=email, role="instructor", sub=f"{name}-sub", name=name
    )
    return client_for(sub=f"{name}-sub", email=email), user_id


async def make_learner(
    engine: AsyncEngine, client_for: ClientFactory, name: str
) -> tuple[httpx.AsyncClient, int]:
    email = f"{name}@example.com"
    user_id = await insert_user(engine, email=email, role="learner", sub=f"{name}-sub", name=name)
    return client_for(sub=f"{name}-sub", email=email), user_id


async def make_course(owner: httpx.AsyncClient, owner_id: int) -> Course:
    created = await owner.post(
        f"{API}/courses",
        json={"name": "Machine Learning", "description": "Base", "learning_path": {}},
    )
    assert created.status_code == 201, created.text
    course = created.json()
    uploaded = await owner.post(
        f"{API}/courses/{course['id']}/syllabus", json={"text": "Tema uno y dos"}, headers=key()
    )
    polled = await owner.get(f"{API}/jobs/{uploaded.json()['job_id']}")
    assert polled.json()["ingested"] is True, polled.text
    topics = (await owner.get(f"{API}/courses/{course['id']}/topics")).json()["topics"]
    return Course(
        id=course["id"],
        path_id=course["learning_path"]["id"],
        topic_ids=[t["id"] for t in topics],
        owner=owner,
        owner_id=owner_id,
    )


async def run_job(
    ai: FakeAiService,
    http: httpx.AsyncClient,
    course: Course,
    job_type: str,
    input_: dict[str, Any],
    *,
    topic_id: int | None,
    tag: str = "1",
) -> str:
    """Encola un trabajo de `ai/` (el fake lo termina al instante) y lo ingiere con `GET /jobs`."""
    ref = await ai.submit_job(
        job_type,
        input_,
        f"{job_type}:{topic_id}:{tag}",
        JobRefs(course_id=course.id, topic_id=topic_id),
    )
    polled = await http.get(f"{API}/jobs/{ref.job_id}")
    assert polled.status_code == 200, polled.text
    assert polled.json()["ingested"] is True
    return ref.job_id


async def ingest_explanation(
    ai: FakeAiService, course: Course, topic_id: int, tag: str = "1"
) -> str:
    return await run_job(
        ai,
        course.owner,
        course,
        "content.explain_topic",
        {"topic_id": str(topic_id)},
        topic_id=topic_id,
        tag=tag,
    )


async def ingest_quiz_bank(ai: FakeAiService, course: Course, topic_id: int) -> str:
    return await run_job(
        ai,
        course.owner,
        course,
        "items.generate_quiz_bank",
        {"topic_id": str(topic_id), "n_multiple_choice": 3, "n_short_answer": 2},
        topic_id=topic_id,
    )


async def ingest_videos(ai: FakeAiService, course: Course, topic_id: int) -> str:
    return await run_job(
        ai,
        course.owner,
        course,
        "video.collect_candidates",
        {"topic_id": str(topic_id)},
        topic_id=topic_id,
    )


async def insert_enrollment(
    engine: AsyncEngine, user_id: int, path_id: int, *, status: str = "in_path"
) -> int:
    async with engine.begin() as conn:
        value = (
            await conn.execute(
                text(
                    "INSERT INTO enrollments (user_id, learning_path_id, status) "
                    "VALUES (:u, :p, :s) RETURNING id"
                ),
                {"u": user_id, "p": path_id, "s": status},
            )
        ).scalar_one()
    return int(value)
