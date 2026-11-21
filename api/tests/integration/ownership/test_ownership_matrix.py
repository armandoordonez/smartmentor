"""Matriz de propiedad (plan 18.2): un objeto de otro usuario responde 404, nunca 403 ni 200.

El dueño crea un curso con temas y un trabajo; luego otro instructor (y un aprendiz, para los
trabajos) intenta cada ruta que recibe un id. Todas deben responder 404 con el código del recurso.
"""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory, insert_user

pytestmark = pytest.mark.integration

API = "/api/v1"


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@pytest.fixture
async def owner(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    await insert_user(engine, email="owner@example.com", role="instructor", sub="owner-sub")
    return client_for(sub="owner-sub", email="owner@example.com")


@pytest.fixture
async def stranger(client_for: ClientFactory, engine: AsyncEngine) -> httpx.AsyncClient:
    await insert_user(engine, email="stranger@example.com", role="instructor", sub="stranger-sub")
    return client_for(sub="stranger-sub", email="stranger@example.com")


@pytest.fixture
async def ids(owner: httpx.AsyncClient) -> dict[str, Any]:
    course = (
        await owner.post(f"{API}/courses", json={"name": "Privado", "description": "x"})
    ).json()
    uploaded = await owner.post(
        f"{API}/courses/{course['id']}/syllabus",
        json={"text": "Tema uno y tema dos"},
        headers=key(),
    )
    job_id = uploaded.json()["job_id"]
    assert (await owner.get(f"{API}/jobs/{job_id}")).json()["ingested"] is True
    topic = (await owner.get(f"{API}/courses/{course['id']}/topics")).json()["topics"][0]
    return {"course": course["id"], "topic": topic["id"], "job": job_id}


TOPIC_BODY = {"name": "Intento de edición"}

# (método, plantilla de ruta, cuerpo, código esperado)
COURSE_ROUTES: list[tuple[str, str, dict[str, Any] | None, str]] = [
    ("GET", "/courses/{course}", None, "COURSE_NOT_FOUND"),
    ("PATCH", "/courses/{course}", {"name": "Robado"}, "COURSE_NOT_FOUND"),
    ("POST", "/courses/{course}/syllabus", {"text": "otro texto"}, "COURSE_NOT_FOUND"),
    ("POST", "/courses/{course}/extractions", {"confirm_discard_review": True}, "COURSE_NOT_FOUND"),
    ("GET", "/courses/{course}/topics", None, "COURSE_NOT_FOUND"),
    ("GET", "/courses/{course}/topic-graph", None, "COURSE_NOT_FOUND"),
    ("POST", "/courses/{course}/topics", TOPIC_BODY, "COURSE_NOT_FOUND"),
    ("POST", "/courses/{course}/publish", None, "COURSE_NOT_FOUND"),
    ("GET", "/courses/{course}/extraction-metrics", None, "COURSE_NOT_FOUND"),
    ("PUT", "/topics/{topic}", TOPIC_BODY, "TOPIC_NOT_FOUND"),
    ("PATCH", "/topics/{topic}/deactivate", None, "TOPIC_NOT_FOUND"),
]


@pytest.mark.parametrize(("method", "template", "body", "code"), COURSE_ROUTES)
async def test_another_instructor_gets_404_on_every_course_and_topic_route(
    stranger: httpx.AsyncClient,
    ids: dict[str, Any],
    method: str,
    template: str,
    body: dict[str, Any] | None,
    code: str,
) -> None:
    path = API + template.format(**ids)
    response = await stranger.request(method, path, json=body, headers=key())
    assert response.status_code == 404, f"{method} {path}: {response.text}"
    assert response.json()["code"] == code


@pytest.mark.parametrize(("method", "template", "body", "code"), COURSE_ROUTES)
async def test_the_owner_does_not_get_404_on_the_same_routes(
    owner: httpx.AsyncClient,
    ids: dict[str, Any],
    method: str,
    template: str,
    body: dict[str, Any] | None,
    code: str,
) -> None:
    """Control de la matriz: con el dueño las mismas rutas existen (el 404 no es por la ruta)."""
    path = API + template.format(**ids)
    response = await owner.request(method, path, json=body, headers=key())
    assert response.status_code != 404, f"{method} {path}: {response.text}"
    assert response.status_code != 403


async def test_the_listing_never_leaks_other_instructors_courses(
    owner: httpx.AsyncClient, stranger: httpx.AsyncClient, ids: dict[str, Any]
) -> None:
    assert (await stranger.get(f"{API}/courses")).json()["total"] == 0
    assert (await stranger.get(f"{API}/courses", params={"status": "in_review"})).json()[
        "total"
    ] == 0
    assert (await owner.get(f"{API}/courses")).json()["total"] == 1


async def test_a_job_of_another_user_is_404_except_for_the_owner_and_the_admin(
    owner: httpx.AsyncClient,
    stranger: httpx.AsyncClient,
    client: httpx.AsyncClient,
    client_for: ClientFactory,
    ids: dict[str, Any],
) -> None:
    path = f"{API}/jobs/{ids['job']}"
    for outsider in (stranger, client_for(sub="learner-sub", email="learner@example.com")):
        response = await outsider.get(path)
        assert (response.status_code, response.json()["code"]) == (404, "JOB_NOT_FOUND")
    assert (await owner.get(path)).status_code == 200
    assert (await client.get(path)).status_code == 200


async def test_unknown_and_malformed_job_ids(owner: httpx.AsyncClient) -> None:
    unknown = await owner.get(f"{API}/jobs/{uuid.uuid4()}")
    assert (unknown.status_code, unknown.json()["code"]) == (404, "JOB_NOT_FOUND")
    assert (await owner.get(f"{API}/jobs/1")).status_code == 422


async def test_profile_consents_and_requests_only_expose_the_callers_own_data(
    client_for: ClientFactory,
) -> None:
    ana = client_for(sub="ana", email="ana@example.com")
    beto = client_for(sub="beto", email="beto@example.com")
    await ana.post(
        f"{API}/me/consents", json={"consent_type": "data_processing", "document_version": "1.0"}
    )
    await ana.put(f"{API}/me/profile", json={"description": "Privado de Ana"})
    assert (await beto.get(f"{API}/me/consents")).json() == []
    assert (await beto.get(f"{API}/me/profile")).json()["description"] is None
    assert (await beto.patch(f"{API}/me/consents/data_processing/revoke")).status_code == 404
    assert (await beto.get(f"{API}/me")).json()["requires_consent"] is True
