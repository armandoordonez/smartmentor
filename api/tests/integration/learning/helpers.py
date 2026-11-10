"""Ayudas de las pruebas de la ruta del aprendiz: curso publicado, banco de ítems y respuestas."""

import json
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory, insert_user

API = "/api/v1"
SYLLABUS = {"text": "Tema 1 fundamentos. Tema 2 regresión lineal. Tema 3 regresión logística."}
RUBRIC = [
    {"criterion": "concepto clave", "points": 0.4},
    {"criterion": "ejemplo aplicado", "points": 0.3},
    {"criterion": "conclusión clara", "points": 0.3},
]
GOOD_SHORT_ANSWER = "Define el concepto clave, da un ejemplo aplicado y una conclusión clara"
TWO_OF_THREE = "concepto clave y un ejemplo"
BAD_SHORT_ANSWER = "no recuerdo"


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@dataclass
class PublishedPath:
    course_id: int
    path_id: int
    topics: dict[str, int]  # nombre -> id

    @property
    def fundamentals(self) -> int:
        return self.topics["Fundamentos"]

    @property
    def linear(self) -> int:
        return self.topics["Regresión lineal"]

    @property
    def logistic(self) -> int:
        return self.topics["Regresión logística"]


async def instructor_client(
    client_for: ClientFactory, engine: AsyncEngine, name: str = "doc"
) -> httpx.AsyncClient:
    await insert_user(engine, email=f"{name}@example.com", role="instructor", sub=f"{name}-sub")
    return client_for(sub=f"{name}-sub", email=f"{name}@example.com")


async def publish_path(
    instructor: httpx.AsyncClient, name: str = "Machine Learning"
) -> PublishedPath:
    """Curso con los tres temas del syllabus falso, revisado y publicado (FakeAiService)."""
    course = (
        await instructor.post(
            f"{API}/courses",
            json={"name": name, "description": "Base", "learning_path": {"group_label": "Piloto"}},
        )
    ).json()
    uploaded = await instructor.post(
        f"{API}/courses/{course['id']}/syllabus", json=SYLLABUS, headers=key()
    )
    assert (await instructor.get(f"{API}/jobs/{uploaded.json()['job_id']}")).json()["ingested"]
    published = await instructor.post(f"{API}/courses/{course['id']}/publish", headers=key())
    assert published.status_code == 202, published.text
    assert (await instructor.get(published.json()["poll_url"])).json()["ingested"]
    detail = (await instructor.get(f"{API}/courses/{course['id']}")).json()
    topics = (await instructor.get(f"{API}/courses/{course['id']}/topics")).json()["topics"]
    return PublishedPath(
        course_id=course["id"],
        path_id=detail["learning_path"]["id"],
        topics={t["name"]: t["id"] for t in topics},
    )


async def seed_items(
    engine: AsyncEngine,
    topic_id: int,
    source: str,
    *,
    choices: int,
    short_answers: int = 0,
    correct: str = "0",
) -> list[int]:
    """Ítems `approved` en el banco (como los dejaría el instructor tras revisarlos)."""
    ids: list[int] = []
    async with engine.begin() as conn:
        for n in range(choices + short_answers):
            short = n >= choices
            found = await conn.execute(
                text(
                    "INSERT INTO assessment_items (topic_id, source, item_type, bloom_level, "
                    "difficulty, stem, options, correct_option, model_answer, rubric, "
                    "review_status) VALUES (:topic_id, :source, :item_type, 'apply', 1, :stem, "
                    "CAST(:options AS jsonb), :correct, :model_answer, CAST(:rubric AS jsonb), "
                    "'approved') RETURNING id"
                ),
                {
                    "topic_id": topic_id,
                    "source": source,
                    "item_type": "short_answer" if short else "multiple_choice",
                    "stem": f"{source} {topic_id} pregunta {n}",
                    "options": None if short else json.dumps(["A", "B", "C", "D"]),
                    "correct": None if short else correct,
                    "model_answer": "concepto clave, ejemplo aplicado y conclusión clara",
                    "rubric": json.dumps(RUBRIC) if short else None,
                },
            )
            ids.append(int(found.scalar_one()))
    return ids


async def correct_options(engine: AsyncEngine, item_ids: list[int]) -> dict[int, int | None]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id, correct_option FROM assessment_items WHERE id = ANY(:ids)"),
            {"ids": item_ids},
        )
        return {int(r[0]): (int(r[1]) if r[1] is not None else None) for r in rows.all()}


async def learner_client(
    client_for: ClientFactory,
    engine: AsyncEngine,
    name: str = "ana",
    *,
    consent: bool = True,
    description: str | None = "Analista de datos en logística; uso Excel y SQL.",
) -> httpx.AsyncClient:
    await insert_user(engine, email=f"{name}@example.com", role="learner", sub=f"{name}-sub")
    http = client_for(sub=f"{name}-sub", email=f"{name}@example.com")
    if consent:
        granted = await http.post(
            f"{API}/me/consents",
            json={"consent_type": "data_processing", "document_version": "1.0"},
        )
        assert granted.status_code in (200, 201), granted.text
    if description is not None:
        saved = await http.put(f"{API}/me/profile", json={"description": description})
        assert saved.status_code == 200, saved.text
    return http


async def answer_attempt(
    http: httpx.AsyncClient,
    engine: AsyncEngine,
    attempt: dict[str, Any],
    *,
    correct: bool,
    short_text: str | None = None,
) -> httpx.Response:
    """Responde todas las preguntas (bien o mal), entrega y, si hay trabajo, lo consulta."""
    keys = await correct_options(engine, [i["item_id"] for i in attempt["items"]])
    answers = []
    for item in attempt["items"]:
        if item["item_type"] == "short_answer":
            text_answer = short_text or (GOOD_SHORT_ANSWER if correct else BAD_SHORT_ANSWER)
            answers.append({"item_id": item["item_id"], "text_answer": text_answer})
        else:
            right = keys[item["item_id"]] or 0
            option = right if correct else (right + 1) % 4
            answers.append({"item_id": item["item_id"], "selected_option": option})
    saved = await http.put(f"{API}/me/attempts/{attempt['id']}/answers", json={"answers": answers})
    assert saved.status_code == 200, saved.text
    submitted = await http.post(f"{API}/me/attempts/{attempt['id']}/submit", headers=key())
    assert submitted.status_code in (200, 202), submitted.text
    if submitted.status_code == 202:
        polled = await http.get(submitted.json()["poll_url"])
        assert polled.status_code == 200, polled.text
    result = await http.get(f"{API}/me/attempts/{attempt['id']}/result")
    assert result.status_code == 200, result.text
    return result


async def start_attempt(
    http: httpx.AsyncClient, enrollment_id: int, step_id: int
) -> dict[str, Any]:
    created = await http.post(
        f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/attempts",
        json={"assessment_type": "topic"},
        headers=key(),
    )
    if created.status_code == 202:  # banco agotado: se genera y se vuelve a pedir (U1b)
        await http.get(created.json()["poll_url"])
        created = await http.post(
            f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/attempts",
            json={"assessment_type": "topic"},
            headers=key(),
        )
    assert created.status_code == 201, created.text
    body: dict[str, Any] = created.json()
    return body


async def enrollment_in_path(
    http: httpx.AsyncClient, path: PublishedPath, *, diagnostic_correct: dict[int, bool]
) -> int:
    """Inscribe, presenta el diagnóstico, ingiere el resultado y confirma el objetivo."""
    enrollment = (
        await http.post(f"{API}/me/enrollments", json={"learning_path_id": path.path_id})
    ).json()
    enrollment_id = int(enrollment["id"])
    diagnostic = (await http.post(f"{API}/me/enrollments/{enrollment_id}/diagnostic")).json()
    answers = [
        {
            "item_id": item["item_id"],
            "selected_option": 1 if diagnostic_correct.get(item["topic_id"], False) else 2,
        }
        for item in diagnostic["items"]
    ]
    await http.put(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/answers", json={"answers": answers}
    )
    submitted = await http.post(
        f"{API}/me/enrollments/{enrollment_id}/diagnostic/submit", headers=key()
    )
    assert submitted.status_code == 202, submitted.text
    assert (await http.get(submitted.json()["poll_url"])).json()["ingested"] is True
    confirmed = await http.put(
        f"{API}/me/enrollments/{enrollment_id}/objective",
        json={
            "bloom_verb": "Aplicar",
            "content": "regresión a mi trabajo",
            "criterion": "con 80 %",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    return enrollment_id
