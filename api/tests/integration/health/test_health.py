import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_health_is_always_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_database_and_vector_extension(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_request_id_is_returned_and_respected(client: httpx.AsyncClient) -> None:
    generated = await client.get("/health")
    assert generated.headers["x-request-id"]
    echoed = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"


async def test_openapi_has_no_delete_operations(client: httpx.AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    methods = {m for path in spec["paths"].values() for m in path}
    assert "delete" not in methods
    assert {"get", "post", "patch"} <= methods
