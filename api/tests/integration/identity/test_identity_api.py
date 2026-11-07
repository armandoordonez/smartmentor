"""API de identidad: usuarios, roles (CU-14), perfil, autorizaciones y solicitudes de derechos."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ADMIN_EMAIL, ClientFactory, insert_user

pytestmark = pytest.mark.integration

API = "/api/v1"
USERS = f"{API}/users"


async def admin_id(client: httpx.AsyncClient) -> int:
    return int((await client.get(f"{API}/me")).json()["id"])


# --- usuarios ---------------------------------------------------------------------------------


async def test_create_get_and_list_user(client: httpx.AsyncClient) -> None:
    created = await client.post(USERS, json={"full_name": "Ana Pérez", "email": "ana@example.com"})
    assert created.status_code == 201
    body = created.json()
    assert body["id"] > 0
    assert body["active"] is True
    assert body["created_at"].endswith("Z")  # UTC

    fetched = await client.get(f"{USERS}/{body['id']}")
    assert fetched.json()["email"] == "ana@example.com"
    page = (await client.get(USERS)).json()
    assert (page["total"], page["limit"]) == (2, 20)  # el administrador de la prueba y Ana


async def test_email_must_be_unique_ignoring_case(client: httpx.AsyncClient) -> None:
    await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})
    duplicate = await client.post(USERS, json={"full_name": "Otra", "email": "ANA@example.com"})
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith("application/problem+json")
    assert duplicate.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_update_changes_only_sent_fields(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()
    updated = await client.patch(f"{USERS}/{user['id']}", json={"full_name": "Ana María"})
    assert updated.json()["full_name"] == "Ana María"
    assert updated.json()["email"] == "ana@example.com"


async def test_deactivate_and_activate_are_logical(client: httpx.AsyncClient) -> None:
    user = (await client.post(USERS, json={"full_name": "Ana", "email": "ana@example.com"})).json()
    assert (await client.patch(f"{USERS}/{user['id']}/deactivate")).json()["active"] is False
    assert (await client.get(USERS)).json()["total"] == 1  # por defecto solo activos
    assert (await client.get(f"{USERS}/{user['id']}")).status_code == 200  # el registro sigue
    assert (await client.patch(f"{USERS}/{user['id']}/activate")).json()["active"] is True


async def test_unknown_fields_and_a_lone_identity_provider_are_rejected(
    client: httpx.AsyncClient,
) -> None:
    extra = await client.post(
        USERS, json={"full_name": "K", "email": "k@example.com", "id": 99, "active": False}
    )
    assert extra.status_code == 422
    assert extra.json()["code"] == "VALIDATION_ERROR"
    lone = await client.post(
        USERS, json={"full_name": "K", "email": "k@example.com", "identity_provider": "keycloak"}
    )
    assert lone.status_code == 422


# --- roles de un usuario (CU-14) ---------------------------------------------------------------


async def test_the_admin_assigns_several_roles_and_the_change_is_audited(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    me = await admin_id(client)
    user_id = await insert_user(engine, email="multi@example.com", role="learner", sub=None)
    response = await client.put(f"{USERS}/{user_id}/roles", json={"roles": ["instructor", "learner"]})
    assert response.status_code == 200
    assert response.json() == {"roles": ["instructor", "learner"]}
    assert (await client.get(f"{USERS}/{user_id}/roles")).json() == {
        "roles": ["instructor", "learner"]
    }
    async with engine.connect() as conn:
        actors = (
            (
                await conn.execute(
                    text(
                        "SELECT DISTINCT app_user_id FROM user_roles_audit "
                        "WHERE new_data ->> 'user_id' = :uid AND operation = 'INSERT' "
                        "AND changed_at > now() - interval '1 minute' "
                        "AND (new_data ->> 'role_id')::bigint = "
                        "(SELECT id FROM roles WHERE code = 'instructor')"
                    ),
                    {"uid": str(user_id)},
                )
            )
            .scalars()
            .all()
        )
    assert actors == [str(me)]


async def test_removing_a_role_deactivates_the_assignment_and_can_be_undone(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await insert_user(engine, email="multi@example.com", role="learner", sub=None)
    await client.put(f"{USERS}/{user_id}/roles", json={"roles": ["instructor"]})
    assert (await client.get(f"{USERS}/{user_id}/roles")).json() == {"roles": ["instructor"]}
    await client.put(f"{USERS}/{user_id}/roles", json={"roles": ["learner", "instructor"]})
    assert (await client.get(f"{USERS}/{user_id}/roles")).json() == {
        "roles": ["instructor", "learner"]
    }
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT count(*) FROM user_roles WHERE user_id = :u"), {"u": user_id}
            )
        ).scalar_one()
    assert rows == 2  # nunca se borra una fila


async def test_invalid_role_sets_are_rejected(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await insert_user(engine, email="x@example.com", role="learner", sub=None)
    for body in ({"roles": []}, {"roles": ["evaluator"]}, {"roles": ["learner", "learner"]}):
        assert (await client.put(f"{USERS}/{user_id}/roles", json=body)).status_code == 422
    missing = await client.put(f"{USERS}/9999/roles", json={"roles": ["learner"]})
    assert (missing.status_code, missing.json()["code"]) == (404, "USER_NOT_FOUND")


async def test_the_platform_never_loses_its_last_administrator(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    me = await admin_id(client)
    blocked = await client.put(f"{USERS}/{me}/roles", json={"roles": ["instructor"]})
    assert (blocked.status_code, blocked.json()["code"]) == (409, "LAST_ADMIN")
    assert (await client.patch(f"{USERS}/{me}/deactivate")).json()["code"] == "LAST_ADMIN"
    roles = {r["code"]: r["id"] for r in (await client.get(f"{API}/roles")).json()["items"]}
    own = (await client.get(f"{API}/user-roles", params={"user_id": me})).json()["items"]
    admin_assignment = next(a for a in own if a["role_id"] == roles["admin"])
    denied = await client.patch(f"{API}/user-roles/{admin_assignment['id']}/deactivate")
    assert (denied.status_code, denied.json()["code"]) == (409, "LAST_ADMIN")

    # Con un segundo administrador, el primero sí puede dejar el rol.
    second = await insert_user(engine, email="otro@example.com", role="admin", sub=None)
    assert (await client.put(f"{USERS}/{me}/roles", json={"roles": ["learner"]})).status_code == 200
    assert second > 0


async def test_user_roles_crud_conflicts_and_reactivation(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await insert_user(engine, email="x@example.com", role="learner", sub=None)
    roles = {r["code"]: r["id"] for r in (await client.get(f"{API}/roles")).json()["items"]}
    duplicate = await client.post(
        f"{API}/user-roles", json={"user_id": user_id, "role_id": roles["learner"]}
    )
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "ROLE_ALREADY_ASSIGNED")
    created = await client.post(
        f"{API}/user-roles", json={"user_id": user_id, "role_id": roles["instructor"]}
    )
    assert created.status_code == 201
    await client.patch(f"{API}/user-roles/{created.json()['id']}/deactivate")
    again = await client.post(
        f"{API}/user-roles", json={"user_id": user_id, "role_id": roles["instructor"]}
    )
    assert again.status_code == 201
    assert again.json()["id"] == created.json()["id"]  # se reactivó la misma fila
    missing = await client.post(f"{API}/user-roles", json={"user_id": 9999, "role_id": 1})
    assert (missing.status_code, missing.json()["code"]) == (404, "USER_NOT_FOUND")


async def test_the_roles_catalog_has_exactly_the_three_neutral_roles(
    client: httpx.AsyncClient,
) -> None:
    codes = {r["code"] for r in (await client.get(f"{API}/roles")).json()["items"]}
    assert codes == {"learner", "instructor", "admin"}
    duplicate = await client.post(f"{API}/roles", json={"code": "admin", "name": "Otro"})
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "ROLE_CODE_ALREADY_EXISTS")


# --- perfil y hoja de vida ------------------------------------------------------------------------

PROFILE = {
    "description": "Soy ingeniera industrial y trabajo como analista de datos.",
    "education_level": "undergraduate",
    "qualification_title": "Ingeniería industrial",
    "job_title": "Analista de datos",
    "experience_band": "1_3_years",
    "tools": ["Excel", "SQL"],
    "languages": [{"code": "es", "cefr_level": "C2"}, {"code": "en", "cefr_level": "B1"}],
}


async def test_profile_starts_empty_and_is_replaced_by_put(client_for: ClientFactory) -> None:
    http = client_for(sub="p-sub", email="p@example.com")
    empty = (await http.get(f"{API}/me/profile")).json()
    assert empty["description"] is None
    assert empty["tools"] == []
    assert empty["resume_completed_at"] is None

    saved = await http.put(f"{API}/me/profile", json=PROFILE)
    assert saved.status_code == 200
    body = saved.json()
    assert body["tools"] == ["Excel", "SQL"]
    assert body["languages"][1] == {"code": "en", "cefr_level": "B1"}
    assert body["resume_completed_at"] is not None
    assert body["recalculated_enrollment_ids"] == []
    me = (await http.get(f"{API}/me")).json()
    assert me["profile_completeness"] == {"description": True, "resume": True, "percent": 100}

    partial = await http.put(f"{API}/me/profile", json={"description": "Solo la descripción"})
    assert partial.json()["education_level"] is None
    assert partial.json()["resume_completed_at"] is None


@pytest.mark.parametrize(
    "bad",
    [
        {"education_level": "doctor"},
        {"experience_band": "mucha"},
        {"languages": [{"code": "es", "cefr_level": "Z9"}]},
        {"tools": "Excel"},
        {"unknown": 1},
    ],
)
async def test_invalid_profiles_are_422(client_for: ClientFactory, bad: dict[str, object]) -> None:
    http = client_for(sub="p-sub", email="p@example.com")
    assert (await http.put(f"{API}/me/profile", json=bad)).status_code == 422


async def test_profiles_are_private_to_each_user(client_for: ClientFactory) -> None:
    ana = client_for(sub="ana", email="ana@example.com")
    beto = client_for(sub="beto", email="beto@example.com")
    await ana.put(f"{API}/me/profile", json=PROFILE)
    assert (await beto.get(f"{API}/me/profile")).json()["description"] is None


# --- autorizaciones y solicitudes -----------------------------------------------------------------


async def test_consent_lifecycle(client_for: ClientFactory) -> None:
    http = client_for(sub="c-sub", email="c@example.com")
    body = {"consent_type": "data_processing", "document_version": "1.0"}
    first = await http.post(f"{API}/me/consents", json=body)
    assert first.status_code == 201
    assert first.json()["granted"] is True
    again = await http.post(f"{API}/me/consents", json=body)
    assert (again.status_code, again.json()["id"]) == (200, first.json()["id"])  # idempotente

    me = (await http.get(f"{API}/me")).json()
    assert me["requires_consent"] is False
    assert me["consent_status"]["data_processing"]["document_version"] == "1.0"
    assert me["consent_status"]["pilot_research"]["granted"] is False

    revoked = await http.patch(f"{API}/me/consents/data_processing/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["granted"] is False
    assert revoked.json()["revoked_at"] is not None
    twice = await http.patch(f"{API}/me/consents/data_processing/revoke")
    assert (twice.status_code, twice.json()["code"]) == (409, "CONSENT_ALREADY_REVOKED")
    assert (await http.get(f"{API}/me")).json()["requires_consent"] is True

    regrant = await http.post(f"{API}/me/consents", json={**body, "document_version": "2.0"})
    assert regrant.status_code == 201
    listing = (await http.get(f"{API}/me/consents")).json()
    assert [c["granted"] for c in listing] == [False, True]


async def test_consent_validation_and_ownership(client_for: ClientFactory) -> None:
    http = client_for(sub="c-sub", email="c@example.com")
    assert (
        await http.post(f"{API}/me/consents", json={"consent_type": "marketing", "document_version": "1"})
    ).status_code == 422
    assert (await http.patch(f"{API}/me/consents/pilot_research/revoke")).status_code == 404
    assert (await http.patch(f"{API}/me/consents/otra/revoke")).status_code == 422
    other = client_for(sub="d-sub", email="d@example.com")
    await http.post(
        f"{API}/me/consents", json={"consent_type": "data_processing", "document_version": "1.0"}
    )
    assert (await other.get(f"{API}/me/consents")).json() == []


async def test_a_data_subject_request_is_created_pending(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    http = client_for(sub="r-sub", email="r@example.com")
    created = await http.post(
        f"{API}/me/data-subject-requests", json={"request_type": "deletion", "comment": "Me voy"}
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert created.json()["request_type"] == "deletion"
    async with engine.connect() as conn:
        details = (await conn.execute(text("SELECT details FROM data_subject_requests"))).scalar_one()
    assert details == "Me voy"
    bad = await http.post(f"{API}/me/data-subject-requests", json={"request_type": "borrar"})
    assert bad.status_code == 422


async def test_the_seeded_admin_email_constant_is_what_the_fixture_creates(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get(f"{API}/me")).json()["email"] == ADMIN_EMAIL
