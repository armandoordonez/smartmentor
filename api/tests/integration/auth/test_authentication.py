"""Autenticación, primer ingreso (CU-34), `GET /me` (CU-35) y autorización por rol de la base."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.auth_helpers import KeyPair, make_token
from tests.integration.conftest import ClientFactory, insert_user

pytestmark = pytest.mark.integration

ME = "/api/v1/me"


# --- el token -------------------------------------------------------------------------------


async def test_health_stays_public(bare_client: httpx.AsyncClient) -> None:
    assert (await bare_client.get("/health")).status_code == 200
    assert (await bare_client.get("/ready")).status_code == 200


async def test_missing_token_is_401_with_www_authenticate(bare_client: httpx.AsyncClient) -> None:
    response = await bare_client.get("/api/v1/courses")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "MISSING_TOKEN"


@pytest.mark.parametrize(
    "claims",
    [
        {"expires_in": -60},
        {"audience": "account"},
        {"issuer": "http://otro-emisor/realms/x"},
    ],
    ids=["expirado", "audiencia", "emisor"],
)
async def test_invalid_tokens_are_401(client_for: ClientFactory, claims: dict[str, object]) -> None:
    http = client_for(sub="x", email="x@example.com", **claims)
    response = await http.get(ME)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_token_signed_with_another_key_is_401(bare_client: httpx.AsyncClient) -> None:
    forged = make_token(KeyPair(), sub="admin-sub", email="admin@test.example")
    response = await bare_client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


async def test_garbage_authorization_header_is_401(bare_client: httpx.AsyncClient) -> None:
    response = await bare_client.get(ME, headers={"Authorization": "Bearer no-es-un-jwt"})
    assert response.status_code == 401


async def test_the_old_x_user_id_header_does_not_authenticate(
    bare_client: httpx.AsyncClient,
) -> None:
    response = await bare_client.get("/api/v1/courses", headers={"X-User-Id": "1"})
    assert response.status_code == 401


# --- GET /me (CU-35) --------------------------------------------------------------------------


async def test_me_returns_roles_labels_default_role_and_the_rest_of_the_contract(
    client: httpx.AsyncClient,
) -> None:
    body = (await client.get(ME)).json()
    assert body["email"] == "admin@test.example"
    assert body["roles"] == ["admin"]
    assert body["default_role"] == "admin"
    assert body["role_labels"] == {
        "learner": "Aprendiz",
        "instructor": "Instructor",
        "admin": "Administrador",
    }
    assert body["role_short_labels"]["admin"] == "Admin"
    assert body["is_new_user"] is False
    assert body["requires_consent"] is True
    assert body["consent_status"]["data_processing"] == {
        "granted": False,
        "document_version": None,
        "granted_at": None,
    }
    assert body["profile_completeness"] == {"description": False, "resume": False, "percent": 0}
    assert body["second_factor"] is False


async def test_a_user_with_several_roles_gets_them_ordered_with_the_highest_as_default(
    client_for: ClientFactory, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    user_id = await insert_user(engine, email="multi@example.com", role="learner", sub="multi")
    replaced = await client.put(
        f"/api/v1/users/{user_id}/roles", json={"roles": ["learner", "instructor"]}
    )
    assert replaced.json() == {"roles": ["instructor", "learner"]}
    body = (await client_for(sub="multi", email="multi@example.com").get(ME)).json()
    assert body["roles"] == ["instructor", "learner"]
    assert body["default_role"] == "instructor"


async def test_second_factor_is_reported_from_the_token(client_for: ClientFactory) -> None:
    http = client_for(sub="admin-sub", email="admin@test.example", extra={"amr": ["pwd", "otp"]})
    assert (await http.get(ME)).json()["second_factor"] is True


# --- primer ingreso (CU-34) -------------------------------------------------------------------


async def test_first_login_creates_a_learner_and_is_idempotent(
    client_for: ClientFactory, client: httpx.AsyncClient
) -> None:
    newcomer = client_for(sub="new-sub", email="nuevo@example.com", name="Nuevo Usuario")
    first = await newcomer.get(ME)
    assert first.status_code == 200
    assert first.json()["roles"] == ["learner"]
    assert first.json()["default_role"] == "learner"
    assert first.json()["is_new_user"] is True
    assert first.json()["full_name"] == "Nuevo Usuario"

    second = await newcomer.get(ME)
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["is_new_user"] is False
    users = await client.get("/api/v1/users", params={"limit": 100})
    assert users.json()["total"] == 2  # el admin y el aprendiz, sin duplicados


async def test_simultaneous_first_logins_create_exactly_one_user_and_one_learner_role(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    newcomers = [client_for(sub="race-sub", email="race@example.com") for _ in range(8)]
    responses = await asyncio.gather(*(http.get(ME) for http in newcomers))
    assert {r.status_code for r in responses} == {200}
    assert len({r.json()["id"] for r in responses}) == 1
    assert sum(1 for r in responses if r.json()["is_new_user"]) == 1
    async with engine.connect() as conn:
        users = (
            await conn.execute(text("SELECT count(*) FROM users WHERE email = 'race@example.com'"))
        ).scalar_one()
        roles = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM user_roles ur JOIN users u ON u.id = ur.user_id "
                    "WHERE u.email = 'race@example.com'"
                )
            )
        ).scalar_one()
    assert (users, roles) == (1, 1)


async def test_simultaneous_first_logins_link_a_precreated_user_once(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    await insert_user(engine, email="pre@example.com", role="instructor", sub=None)
    calls = [client_for(sub="pre-sub", email="pre@example.com") for _ in range(6)]
    responses = await asyncio.gather(*(http.get(ME) for http in calls))
    assert {r.status_code for r in responses} == {200}
    assert {tuple(r.json()["roles"]) for r in responses} == {("instructor",)}  # sin agregar learner
    assert len({r.json()["id"] for r in responses}) == 1


async def test_first_login_is_audited_as_the_identity(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    await client_for(sub="audit-sub", email="audit@example.com").get(ME)
    async with engine.connect() as conn:
        creation = (
            await conn.execute(
                text(
                    "SELECT app_user_id FROM users_audit "
                    "WHERE operation = 'INSERT' AND new_data ->> 'email' = 'audit@example.com'"
                )
            )
        ).scalar_one()
    assert creation == "identity:audit-sub"


async def test_unverified_email_is_not_provisioned(
    client_for: ClientFactory, client: httpx.AsyncClient
) -> None:
    http = client_for(sub="u-sub", email="sinverificar@example.com", email_verified=False)
    response = await http.get(ME)
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert (await client.get("/api/v1/users")).json()["total"] == 1  # solo el admin


async def test_unverified_email_cannot_hijack_the_seeded_administrator(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    await insert_user(engine, email="seed@example.com", role="admin", sub=None)
    attacker = client_for(sub="attacker", email="seed@example.com", email_verified=False)
    assert (await attacker.get(ME)).status_code == 403
    async with engine.connect() as conn:
        linked = (
            await conn.execute(
                text("SELECT identity_subject FROM users WHERE email = 'seed@example.com'")
            )
        ).scalar_one()
    assert linked is None


async def test_a_precreated_instructor_is_linked_by_verified_email_and_keeps_its_role(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    await insert_user(engine, email="docente@example.com", role="instructor", sub=None)
    instructor = client_for(sub="instructor-sub", email="Docente@Example.com")
    body = (await instructor.get(ME)).json()
    assert body["roles"] == ["instructor"]
    assert body["is_new_user"] is False
    renamed = client_for(sub="instructor-sub", email="otro-correo@example.com")
    assert (await renamed.get(ME)).json()["id"] == body["id"]


async def test_email_of_a_user_linked_to_another_identity_is_409(
    client_for: ClientFactory,
) -> None:
    intruder = client_for(sub="intruso", email="admin@test.example")  # el correo del admin
    response = await intruder.get(ME)
    assert response.status_code == 409
    assert response.json()["code"] == "IDENTITY_ALREADY_LINKED"


async def test_deactivated_user_cannot_use_the_api(
    client_for: ClientFactory, client: httpx.AsyncClient
) -> None:
    http = client_for(sub="baja-sub", email="baja@example.com")
    user_id = (await http.get(ME)).json()["id"]
    await client.patch(f"/api/v1/users/{user_id}/deactivate")
    response = await http.get(ME)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DEACTIVATED"


async def test_roles_in_the_token_are_ignored(client_for: ClientFactory) -> None:
    """Manda user_roles de la base de datos; un rol admin en el token no da permisos."""
    sneaky = client_for(
        sub="sneaky-sub",
        email="sneaky@example.com",
        extra={
            "realm_access": {"roles": ["admin"]},
            "resource_access": {"x": {"roles": ["admin"]}},
        },
    )
    assert (await sneaky.get(ME)).json()["roles"] == ["learner"]
    assert (await sneaky.post("/api/v1/roles", json={"code": "x", "name": "X"})).status_code == 403


# --- qué puede hacer cada rol -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/courses"),
        ("GET", "/api/v1/courses"),
        ("GET", "/api/v1/courses/1"),
        ("GET", "/api/v1/courses/1/topics"),
        ("POST", "/api/v1/courses/1/publish"),
        ("PATCH", "/api/v1/courses/1/owner"),
        ("PUT", "/api/v1/topics/1"),
        ("GET", "/api/v1/users"),
        ("PUT", "/api/v1/users/1/roles"),
        ("GET", "/api/v1/user-roles"),
        ("POST", "/api/v1/roles"),
    ],
)
async def test_a_learner_cannot_reach_instructor_or_admin_routes(
    client_for: ClientFactory, method: str, path: str
) -> None:
    learner = client_for(sub="learner-sub", email="learner@example.com")
    response = await learner.request(method, path, json={})
    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_a_learner_can_read_the_roles_catalog(client_for: ClientFactory) -> None:
    learner = client_for(sub="learner-sub", email="learner@example.com")
    assert (await learner.get("/api/v1/roles")).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/users"),
        ("PUT", "/api/v1/users/1/roles"),
        ("POST", "/api/v1/user-roles"),
        ("PATCH", "/api/v1/courses/1/owner"),
        ("POST", "/api/v1/roles"),
    ],
)
async def test_an_instructor_cannot_reach_admin_routes(
    client_for: ClientFactory, engine: AsyncEngine, method: str, path: str
) -> None:
    await insert_user(engine, email="doc@example.com", role="instructor", sub="doc-sub")
    instructor = client_for(sub="doc-sub", email="doc@example.com")
    response = await instructor.request(method, path, json={})
    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_second_factor_is_required_on_privileged_routes_when_enabled(
    client_for: ClientFactory, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    await insert_user(engine, email="doc@example.com", role="instructor", sub="doc-sub")
    monkeypatch.setenv("REQUIRE_SECOND_FACTOR", "true")
    get_settings.cache_clear()
    try:
        without = client_for(sub="doc-sub", email="doc@example.com")
        denied = await without.get("/api/v1/courses")
        assert denied.status_code == 403
        assert denied.json()["code"] == "SECOND_FACTOR_REQUIRED"
        assert (await without.get(ME)).status_code == 200  # /me no lo exige
        with_otp = client_for(sub="doc-sub", email="doc@example.com", extra={"amr": ["otp"]})
        assert (await with_otp.get("/api/v1/courses")).status_code == 200
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


async def test_the_openapi_offers_both_ways_to_authenticate(bare_client: httpx.AsyncClient) -> None:
    spec = (await bare_client.get("/openapi.json")).json()
    schemes = spec["components"]["securitySchemes"]
    assert any(s.get("scheme") == "bearer" for s in schemes.values())  # pegar un token
    password_flows = [s["flows"]["password"] for s in schemes.values() if s.get("type") == "oauth2"]
    assert password_flows, "Swagger debe ofrecer el login con usuario y contraseña"
    assert password_flows[0]["tokenUrl"] == (
        "http://keycloak.test/realms/smartmentor/protocol/openid-connect/token"
    )
    assert set(password_flows[0]["scopes"]) == {"openid", "profile", "email"}
    assert "/api/v1/me" in spec["paths"]


async def test_swagger_ui_is_prefilled_with_the_dev_tools_client(
    bare_client: httpx.AsyncClient,
) -> None:
    page = (await bare_client.get("/docs")).text
    assert "smartmentor-dev-tools" in page
    assert "persistAuthorization" in page
    assert "openid profile email" in page  # Keycloak rechaza un scope vacío
