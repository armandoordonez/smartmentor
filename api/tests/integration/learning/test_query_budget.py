"""Presupuesto de consultas SQL por petición en las rutas del aprendiz (R-008, B-018).

Contra Neon cada sentencia cuesta un viaje de ~110 ms, así que una ruta que vuelva a crecer en
consultas se nota enseguida en la app. Si una de estas pruebas falla, el mensaje trae las
sentencias de la petición: revisa cuál se repite antes de subir el tope.

Los topes son los valores medidos después de R-008 (entre paréntesis, los de antes).
"""

from collections.abc import Awaitable

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    PublishedPath,
    instructor_client,
    key,
    learner_client,
    publish_path,
    seed_items,
    start_attempt,
)
from tests.integration.query_counter import QueryLog, count_queries

pytestmark = pytest.mark.integration

BUDGETS = {
    "GET /me": 4,  # (8)
    "POST /me/enrollments": 16,  # (21)
    "GET /me/enrollments": 10,  # (15)
    "GET /me/enrollments/{id} · diagnosing": 9,  # (14)
    "POST diagnostic": 11,  # (17)
    "GET /me/enrollments/{id} · diagnostic in progress": 9,  # (14)
    "GET diagnostic": 6,  # (12)
    "PUT diagnostic/answers": 6,  # (9)
    "GET /me/enrollments/{id} · waiting job": 9,  # (14)
    "GET diagnostic/result": 7,  # (10)
    "PUT objective": 25,  # (30)
    "GET /me/enrollments/{id} · in_path": 9,  # (14)
    "GET path": 9,  # (14)
    "GET step content · first open": 13,  # (17)
    "GET step content · reopen": 10,  # (14)
    "GET /me/enrollments/{id} · attempt open": 9,  # (14)
    "GET attempt": 7,  # (13)
    "PUT attempt answers": 8,  # (11)
}


class Meter:
    """Ejecuta cada petición contando sus sentencias y comprueba el tope al final."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self.logs: dict[str, QueryLog] = {}

    async def __call__(
        self, label: str, request: Awaitable[httpx.Response], status: int = 200
    ) -> httpx.Response:
        with count_queries(self._engine) as log:
            response = await request
        assert response.status_code == status, response.text
        self.logs[label] = log
        return response

    def over_budget(self) -> list[str]:
        return [
            f"{label}: {log.count} consultas (tope {BUDGETS[label]})\n{log.describe()}"
            for label, log in self.logs.items()
            if log.count > BUDGETS[label]
        ]


@pytest.fixture
async def path(client_for: ClientFactory, engine: AsyncEngine) -> PublishedPath:
    instructor = await instructor_client(client_for, engine)
    published = await publish_path(instructor)
    for topic_id in published.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=2, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
    return published


@pytest.fixture
async def learner(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    return await learner_client(client_for, engine)


async def test_learner_routes_stay_within_their_query_budget(
    learner: httpx.AsyncClient, path: PublishedPath, engine: AsyncEngine
) -> None:
    m = Meter(engine)
    me = f"{API}/me"

    await m("GET /me", learner.get(me))
    created = await m(
        "POST /me/enrollments",
        learner.post(f"{me}/enrollments", json={"learning_path_id": path.path_id}),
        201,
    )
    eid = created.json()["id"]
    enrollment = f"{me}/enrollments/{eid}"
    await m("GET /me/enrollments", learner.get(f"{me}/enrollments"))
    await m("GET /me/enrollments/{id} · diagnosing", learner.get(enrollment))

    diagnostic = await m("POST diagnostic", learner.post(f"{enrollment}/diagnostic"), 201)
    await m("GET /me/enrollments/{id} · diagnostic in progress", learner.get(enrollment))
    await m("GET diagnostic", learner.get(f"{enrollment}/diagnostic"))
    answers = [
        {"item_id": item["item_id"], "selected_option": 1 if n % 2 else 2}
        for n, item in enumerate(diagnostic.json()["items"])
    ]
    await m(
        "PUT diagnostic/answers",
        learner.put(f"{enrollment}/diagnostic/answers", json={"answers": answers[:1]}),
    )
    await learner.put(f"{enrollment}/diagnostic/answers", json={"answers": answers})
    submitted = await learner.post(f"{enrollment}/diagnostic/submit", headers=key())
    assert submitted.status_code == 202, submitted.text
    await m("GET /me/enrollments/{id} · waiting job", learner.get(enrollment))
    assert (await learner.get(submitted.json()["poll_url"])).json()["ingested"] is True
    await m("GET diagnostic/result", learner.get(f"{enrollment}/diagnostic/result"))
    await m(
        "PUT objective",
        learner.put(
            f"{enrollment}/objective",
            json={"bloom_verb": "Aplicar", "content": "regresión", "criterion": "con 80 %"},
        ),
    )
    await m("GET /me/enrollments/{id} · in_path", learner.get(enrollment))

    steps = (await m("GET path", learner.get(f"{enrollment}/path"))).json()["steps"]
    step_id = next(s["step_id"] for s in steps if s["status"] == "pending")
    content = f"{enrollment}/steps/{step_id}/content"
    await m("GET step content · first open", learner.get(content))
    await m("GET step content · reopen", learner.get(content))

    attempt = await start_attempt(learner, eid, step_id)
    await m("GET /me/enrollments/{id} · attempt open", learner.get(enrollment))
    await m("GET attempt", learner.get(f"{me}/attempts/{attempt['id']}"))
    first = attempt["items"][0]
    answer = (
        {"item_id": first["item_id"], "text_answer": "algo"}
        if first["item_type"] == "short_answer"
        else {"item_id": first["item_id"], "selected_option": 0}
    )
    await m(
        "PUT attempt answers",
        learner.put(f"{me}/attempts/{attempt['id']}/answers", json={"answers": [answer]}),
    )

    assert set(m.logs) == set(BUDGETS)
    over = m.over_budget()
    assert not over, "\n\n".join(over)
