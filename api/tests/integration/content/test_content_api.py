import httpx
import pytest

from tests.integration.conftest import MakeFn

pytestmark = pytest.mark.integration


async def test_text_and_video_resources_of_a_topic(
    client: httpx.AsyncClient, make: MakeFn, world: dict[str, int]
) -> None:
    await make(
        "resources",
        {
            "topic_id": world["topic"],
            "resource_type": "text",
            "content": "La regresión lineal estima...",
            "sources": [{"title": "ISLP", "page": 59}],
            "prompt_version": "text-v1",
        },
    )
    await make(
        "resources",
        {"topic_id": world["topic"], "resource_type": "video", "url": "https://youtu.be/abc"},
    )
    videos = await client.get("/api/v1/resources", params={"resource_type": "video"})
    assert videos.json()["total"] == 1
    assert (await client.get("/api/v1/resources")).json()["total"] == 2


async def test_resource_without_url_or_content_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    response = await client.post(
        "/api/v1/resources", json={"topic_id": world["topic"], "resource_type": "text"}
    )
    assert response.status_code == 422


async def test_resource_type_is_validated(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    response = await client.post(
        "/api/v1/resources",
        json={"topic_id": world["topic"], "resource_type": "audio", "content": "x"},
    )
    assert response.status_code == 422


async def test_resource_needs_an_existing_topic(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/resources", json={"topic_id": 999, "resource_type": "text", "content": "x"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "TOPIC_NOT_FOUND"
