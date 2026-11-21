"""Listados de inscripciones sin consultas por fila (B-063).

`GET /enrollments` (AD5) y `GET /me/enrollments` (E1, Mi progreso) armaban la vista de cada
inscripción por separado: ruta, pasos, diagnóstico, intentos, intentos extra y encuesta, unas seis
consultas por fila. Contra Neon (~110 ms por consulta) una página de 20 inscripciones sumaba más de
13 s. Aquí se compara el total de sentencias con una inscripción y con cinco: no debe crecer.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    enrollment_in_path,
    instructor_client,
    key,
    learner_client,
    publish_path,
    seed_items,
    start_attempt,
)
from tests.integration.query_counter import count_queries

pytestmark = pytest.mark.integration


async def _enroll(
    admin: httpx.AsyncClient,
    client_for: ClientFactory,
    engine: AsyncEngine,
    path_id: int,
    name: str,
) -> None:
    learner = await learner_client(client_for, engine, name)
    me = (await learner.get(f"{API}/me")).json()
    created = await admin.post(
        f"{API}/enrollments", json={"user_id": me["id"], "learning_path_id": path_id}
    )
    assert created.status_code == 201, created.text


async def test_admin_enrollment_list_does_not_grow_with_the_page(
    client: httpx.AsyncClient, client_for: ClientFactory, engine: AsyncEngine
) -> None:
    instructor = await instructor_client(client_for, engine)
    path = await publish_path(instructor)
    listing = f"{API}/enrollments"

    await _enroll(client, client_for, engine, path.path_id, "uno")
    with count_queries(engine) as one:
        first = await client.get(listing)
    assert first.status_code == 200, first.text

    for name in ("dos", "tres", "cuatro", "cinco"):
        await _enroll(client, client_for, engine, path.path_id, name)
    with count_queries(engine) as many:
        page = await client.get(listing)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 5

    assert many.count == one.count, f"1 → {one.count}, 5 → {many.count}\n{many.describe()}"
    by_id = {row["id"]: row for row in page.json()["items"]}
    for row in first.json()["items"]:
        assert by_id[row["id"]]["next_action"] == row["next_action"]


async def test_own_enrollment_list_does_not_grow_with_the_page(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    instructor = await instructor_client(client_for, engine)
    paths = [await publish_path(instructor, f"Curso {n}") for n in range(1, 4)]
    learner = await learner_client(client_for, engine)
    listing = f"{API}/me/enrollments"

    enrolled = await learner.post(
        f"{API}/me/enrollments", json={"learning_path_id": paths[0].path_id}
    )
    assert enrolled.status_code == 201, enrolled.text
    first_id = enrolled.json()["id"]
    with count_queries(engine) as one:
        first = await learner.get(listing)
    assert first.status_code == 200, first.text
    before = first.json()["items"][0]

    for path in paths[1:]:
        created = await learner.post(
            f"{API}/me/enrollments", json={"learning_path_id": path.path_id}
        )
        assert created.status_code == 201, created.text
    with count_queries(engine) as many:
        page = await learner.get(listing)
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 3

    assert many.count == one.count, f"1 → {one.count}, 3 → {many.count}\n{many.describe()}"
    after = next(row for row in page.json()["items"] if row["id"] == first_id)
    assert after["next_action"] == before["next_action"]
    assert after["status"] == before["status"]


async def test_the_list_says_the_same_as_each_enrollment_detail(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    """La vista en lote no cambia nada: estado y `next_action` iguales al detalle de cada una.

    Tres inscripciones en estados distintos: con un intento abierto, esperando la calificación del
    diagnóstico (esa pasa por la lectura de una en una, porque ubica su trabajo de IA) y recién
    inscrita.
    """
    instructor = await instructor_client(client_for, engine)
    paths = [await publish_path(instructor, f"Curso {n}") for n in range(1, 4)]
    for path in paths:
        for topic_id in path.topics.values():
            await seed_items(engine, topic_id, "diagnostic", choices=2, correct="1")
            await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
    learner = await learner_client(client_for, engine)
    me = f"{API}/me/enrollments"

    in_path = await enrollment_in_path(learner, paths[0], diagnostic_correct={})
    steps = (await learner.get(f"{me}/{in_path}/path")).json()["steps"]
    step_id = next(s["step_id"] for s in steps if s["status"] == "pending")
    await start_attempt(learner, in_path, step_id)

    scoring = (await learner.post(me, json={"learning_path_id": paths[1].path_id})).json()["id"]
    diagnostic = (await learner.post(f"{me}/{scoring}/diagnostic")).json()
    answers = [{"item_id": i["item_id"], "selected_option": 1} for i in diagnostic["items"]]
    await learner.put(f"{me}/{scoring}/diagnostic/answers", json={"answers": answers})
    submitted = await learner.post(f"{me}/{scoring}/diagnostic/submit", headers=key())
    assert submitted.status_code == 202, submitted.text

    fresh = (await learner.post(me, json={"learning_path_id": paths[2].path_id})).json()["id"]

    listed = (await learner.get(me)).json()["items"]
    assert {row["id"] for row in listed} == {in_path, scoring, fresh}
    for row in listed:
        detail = (await learner.get(f"{me}/{row['id']}")).json()
        assert row["status"] == detail["status"], row["id"]
        assert row["next_action"] == detail["next_action"], row["id"]
    by_id = {row["id"]: row["next_action"]["type"] for row in listed}
    assert by_id[in_path] == "continue_attempt"
    assert by_id[scoring] == "wait_job"
