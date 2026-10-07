import httpx
import pytest

from tests.integration.conftest import MakeFn

pytestmark = pytest.mark.integration


async def test_course_requires_an_existing_owner(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/courses", json={"owner_user_id": 999, "name": "Curso"})
    assert response.status_code == 422
    assert response.json()["code"] == "OWNER_NOT_FOUND"


async def test_course_status_follows_the_enum(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    response = await client.patch(f"/api/v1/courses/{world['course']}", json={"status": "approved"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    invalid = await client.patch(f"/api/v1/courses/{world['course']}", json={"status": "published"})
    assert invalid.status_code == 422


async def test_topic_with_embedding_does_not_return_the_vector(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    response = await client.post(
        "/api/v1/topics",
        json={
            "course_id": world["course"],
            "name": "Clasificación",
            "learning_outcomes": ["Aplicar regresión logística"],
            "bloom_level": "apply",
            "embedding": [0.001] * 1024,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["has_embedding"] is True
    assert "embedding" not in body
    assert body["learning_outcomes"] == ["Aplicar regresión logística"]

    wrong = await client.post(
        "/api/v1/topics", json={"course_id": world["course"], "name": "X", "embedding": [0.1]}
    )
    assert wrong.status_code == 422


async def test_topics_are_filtered_by_course(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    other = await make("courses", {"owner_user_id": world["teacher"], "name": "Otro"})
    await make("topics", {"course_id": other["id"], "name": "Tema del otro curso"})
    listing = await client.get("/api/v1/topics", params={"course_id": world["course"]})
    assert listing.json()["total"] == 1


async def test_prerequisites_form_an_acyclic_graph(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    a = world["topic"]
    b = (await make("topics", {"course_id": world["course"], "name": "B"}))["id"]
    c = (await make("topics", {"course_id": world["course"], "name": "C"}))["id"]

    ok = await client.post(
        "/api/v1/topic-prerequisites", json={"topic_id": b, "prerequisite_topic_id": a}
    )
    assert ok.status_code == 201
    await make("topic-prerequisites", {"topic_id": c, "prerequisite_topic_id": b})

    duplicate = await client.post(
        "/api/v1/topic-prerequisites", json={"topic_id": b, "prerequisite_topic_id": a}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "PREREQUISITE_ALREADY_EXISTS"

    cycle = await client.post(
        "/api/v1/topic-prerequisites", json={"topic_id": a, "prerequisite_topic_id": c}
    )
    assert cycle.status_code == 422
    assert cycle.json()["code"] == "PREREQUISITE_CYCLE"


async def test_prerequisite_must_stay_in_the_same_course(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    other = await make("courses", {"owner_user_id": world["teacher"], "name": "Otro"})
    foreign = await make("topics", {"course_id": other["id"], "name": "Ajeno"})
    response = await client.post(
        "/api/v1/topic-prerequisites",
        json={"topic_id": world["topic"], "prerequisite_topic_id": foreign["id"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PREREQUISITE_ACROSS_COURSES"
