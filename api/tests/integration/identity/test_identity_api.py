import httpx
import pytest

pytestmark = pytest.mark.integration

USERS = "/api/v1/users"


async def test_create_get_and_list_user(client: httpx.AsyncClient) -> None:
    created = await client.post(USERS, json={"full_name": "Ana Pérez", "email": "ana@example.com"})
    assert created.status_code == 201
    body = created.json()
    assert body["id"] > 0
    assert body["active"] is True
    assert body["created_at"].endswith("-05:00")  # zona horaria America/Bogota

    fetched = await client.get(f"{USERS}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "ana@example.com"

    listing = await client.get(USERS)
    assert listing.status_code == 200
    page = listing.json()
    assert page["total"] == 2  # el administrador de la prueba y Ana
    assert page["limit"] == 20
    assert body["id"] in [item["id"] for item in page["items"]]


async def test_email_must_be_unique_ignoring_case(client: httpx.AsyncClient) -> None:
    await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})
    duplicate = await client.post(USERS, json={"full_name": "Otra", "email": "ANA@example.com"})
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith("application/problem+json")
    assert duplicate.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_update_changes_only_sent_fields(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()
    updated = await client.patch(f"{USERS}/{user['id']}", json={"full_name": "Ana María"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Ana María"
    assert updated.json()["email"] == "ana@example.com"


async def test_deactivate_and_activate_are_logical(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()

    off = await client.patch(f"{USERS}/{user['id']}/deactivate")
    assert off.status_code == 200
    assert off.json()["active"] is False

    assert (await client.get(USERS)).json()[
        "total"
    ] == 1  # por defecto solo activos (queda el admin)
    inactive = await client.get(USERS, params={"active": "false"})
    assert inactive.json()["total"] == 1
    assert (await client.get(f"{USERS}/{user['id']}")).status_code == 200  # el registro sigue

    on = await client.patch(f"{USERS}/{user['id']}/activate")
    assert on.json()["active"] is True


async def test_there_is_no_delete_endpoint(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()
    assert (await client.delete(f"{USERS}/{user['id']}")).status_code == 405


async def test_unknown_user_is_404_problem(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{USERS}/9999")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["request_id"]


async def test_validation_error_does_not_echo_input(client: httpx.AsyncClient) -> None:
    response = await client.post(USERS, json={"full_name": "Ana", "email": "no-es-un-correo"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "no-es-un-correo" not in response.text


async def test_unknown_fields_are_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        USERS, json={"full_name": "Ana", "email": "ana@example.com", "active": False, "id": 7}
    )
    assert response.status_code == 422


async def test_identity_fields_go_together(client: httpx.AsyncClient) -> None:
    response = await client.post(
        USERS,
        json={"full_name": "K", "email": "k@example.com", "identity_provider": "keycloak"},
    )
    assert response.status_code == 422

    ok = await client.post(
        USERS,
        json={
            "full_name": "K",
            "email": "k@example.com",
            "identity_provider": "keycloak",
            "identity_subject": "abc-123",
        },
    )
    assert ok.status_code == 201

    same_identity = await client.post(
        USERS,
        json={
            "full_name": "K2",
            "email": "k2@example.com",
            "identity_provider": "keycloak",
            "identity_subject": "abc-123",
        },
    )
    assert same_identity.status_code == 409
    assert same_identity.json()["code"] == "IDENTITY_ALREADY_LINKED"


async def test_assign_role_to_user(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()
    roles = (await client.get("/api/v1/roles", params={"code": "teacher"})).json()
    assert roles["total"] == 1  # sembrado por Liquibase
    role_id = roles["items"][0]["id"]

    assigned = await client.post(
        "/api/v1/user-roles", json={"user_id": user["id"], "role_id": role_id}
    )
    assert assigned.status_code == 201

    again = await client.post(
        "/api/v1/user-roles", json={"user_id": user["id"], "role_id": role_id}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "ROLE_ALREADY_ASSIGNED"

    missing_user = await client.post(
        "/api/v1/user-roles", json={"user_id": 9999, "role_id": role_id}
    )
    assert missing_user.status_code == 422
    assert missing_user.json()["code"] == "USER_NOT_FOUND"


async def test_audit_records_the_authenticated_user(client: httpx.AsyncClient, engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    created = await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})
    assert created.status_code == 201
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT operation, app_user_id FROM users_audit "
                    "WHERE new_data ->> 'email' = 'ana@example.com' ORDER BY audit_id"
                )
            )
        ).one()
        admin_id = (
            await conn.execute(text("SELECT id FROM users WHERE email = 'admin@test.example'"))
        ).scalar_one()
    assert row.operation == "INSERT"
    assert row.app_user_id == str(admin_id)  # el id del usuario del token, no un dato del cliente
