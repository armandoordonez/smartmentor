from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.auth_helpers import KeyPair
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
    from tests.auth_helpers import make_token

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


# --- quién es el usuario ----------------------------------------------------------------------


async def test_me_returns_the_user_and_the_roles_from_the_database(
    client: httpx.AsyncClient,
) -> None:
    body = (await client.get(ME)).json()
    assert body["email"] == "admin@test.example"
    assert body["roles"] == ["admin"]
    assert body["identity_provider"] == "keycloak"
    assert body["identity_subject"] == "admin-sub"


async def test_first_login_creates_a_student_and_is_idempotent(
    client_for: ClientFactory, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    newcomer = client_for(sub="new-sub", email="nuevo@example.com", name="Nuevo Usuario")
    first = await newcomer.get(ME)
    assert first.status_code == 200
    assert first.json()["roles"] == ["student"]
    assert first.json()["full_name"] == "Nuevo Usuario"
    assert first.json()["identity_subject"] == "new-sub"

    second = await newcomer.get(ME)
    assert second.json()["id"] == first.json()["id"]
    users = await client.get("/api/v1/users", params={"limit": 100})
    assert users.json()["total"] == 2  # el admin y el estudiante, sin duplicados


async def test_first_login_is_audited_as_the_identity_then_as_the_user(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    newcomer = client_for(sub="audit-sub", email="audit@example.com")
    user_id = (await newcomer.get(ME)).json()["id"]
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
    assert user_id > 0


async def test_unverified_email_is_not_provisioned(
    client_for: ClientFactory, client: httpx.AsyncClient
) -> None:
    http = client_for(sub="u-sub", email="sinverificar@example.com", email_verified=False)
    response = await http.get(ME)
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert (await client.get("/api/v1/users")).json()["total"] == 1  # solo el admin


async def test_a_precreated_teacher_is_linked_by_verified_email_and_keeps_its_role(
    client_for: ClientFactory, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await insert_user(engine, email="docente@example.com", role="teacher", sub=None)
    teacher = client_for(sub="teacher-sub", email="Docente@Example.com")
    body = (await teacher.get(ME)).json()
    assert body["roles"] == ["teacher"]  # no se agregó student
    assert body["identity_subject"] == "teacher-sub"
    # después se reconoce por el sub, aunque el correo del token cambie
    renamed = client_for(sub="teacher-sub", email="otro-correo@example.com")
    assert (await renamed.get(ME)).json()["id"] == body["id"]


async def test_email_of_a_user_linked_to_another_identity_is_403(
    client_for: ClientFactory,
) -> None:
    intruder = client_for(sub="intruso", email="admin@test.example")  # el correo del admin
    response = await intruder.get(ME)
    assert response.status_code == 403
    assert response.json()["code"] == "IDENTITY_CONFLICT"


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
    assert (await sneaky.get(ME)).json()["roles"] == ["student"]
    assert (await sneaky.post("/api/v1/roles", json={"code": "x", "name": "X"})).status_code == 403


# --- qué puede hacer cada rol -----------------------------------------------------------------


async def test_student_can_browse_the_catalog_but_not_change_it(
    client_for: ClientFactory, client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    student = client_for(sub="est-sub", email="est@example.com")
    assert (await student.get("/api/v1/courses")).status_code == 200
    assert (await student.get(f"/api/v1/topics/{world['topic']}")).status_code == 200
    assert (await student.get("/api/v1/learning-paths")).status_code == 200
    assert (await student.get("/api/v1/resources")).status_code == 200
    assert (await student.get("/api/v1/roles")).status_code == 200

    for path, body in [
        ("/api/v1/courses", {"owner_user_id": 1, "name": "X"}),
        ("/api/v1/topics", {"course_id": world["course"], "name": "X"}),
        ("/api/v1/learning-paths", {"course_id": world["course"], "name": "X"}),
    ]:
        denied = await student.post(path, json=body)
        assert denied.status_code == 403, path
        assert denied.json()["code"] == "INSUFFICIENT_ROLE"
    assert (await student.patch(f"/api/v1/courses/{world['course']}/deactivate")).status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/users",
        "/api/v1/user-roles",
        "/api/v1/enrollments",
        "/api/v1/path-steps",
        "/api/v1/diagnostics",
        "/api/v1/assessment-attempts",
        "/api/v1/badges",
        "/api/v1/llm-call-logs",
    ],
)
async def test_student_cannot_read_other_peoples_data(client_for: ClientFactory, path: str) -> None:
    student = client_for(sub="est-sub", email="est@example.com")
    assert (await student.get(path)).status_code == 403


async def test_teacher_manages_content_and_reads_users_but_does_not_administer(
    client_for: ClientFactory, engine: AsyncEngine, world: dict[str, int]
) -> None:
    teacher_id = await insert_user(engine, email="doc@example.com", role="teacher", sub="doc-sub")
    teacher = client_for(sub="doc-sub", email="doc@example.com")

    created = await teacher.post(
        "/api/v1/courses", json={"owner_user_id": teacher_id, "name": "Curso del docente"}
    )
    assert created.status_code == 201
    assert (
        await teacher.post("/api/v1/topics", json={"course_id": created.json()["id"], "name": "T"})
    ).status_code == 201
    assert (await teacher.get("/api/v1/users")).status_code == 200
    assert (await teacher.get("/api/v1/enrollments")).status_code == 200

    assert (
        await teacher.post("/api/v1/users", json={"full_name": "X", "email": "x@example.com"})
    ).status_code == 403
    assert (
        await teacher.post("/api/v1/user-roles", json={"user_id": 1, "role_id": 1})
    ).status_code == 403
    assert (await teacher.get("/api/v1/user-roles")).status_code == 403
    assert (await teacher.get("/api/v1/llm-call-logs")).status_code == 403


async def test_admin_can_do_everything_including_creating_teachers_and_admins(
    client: httpx.AsyncClient,
) -> None:
    teacher = (
        await client.post("/api/v1/users", json={"full_name": "Docente", "email": "d@example.com"})
    ).json()
    roles = {r["code"]: r["id"] for r in (await client.get("/api/v1/roles")).json()["items"]}
    assigned = await client.post(
        "/api/v1/user-roles", json={"user_id": teacher["id"], "role_id": roles["teacher"]}
    )
    assert assigned.status_code == 201
    assert (await client.get("/api/v1/llm-call-logs")).status_code == 200


async def test_changes_are_audited_with_the_authenticated_user_id(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    teacher_id = await insert_user(engine, email="doc@example.com", role="teacher", sub="doc-sub")
    teacher = client_for(sub="doc-sub", email="doc@example.com")
    await teacher.post("/api/v1/courses", json={"owner_user_id": teacher_id, "name": "Auditado"})
    async with engine.connect() as conn:
        actor = (
            await conn.execute(
                text("SELECT app_user_id FROM courses_audit WHERE operation = 'INSERT'")
            )
        ).scalar_one()
    assert actor == str(teacher_id)


async def test_openapi_offers_both_ways_to_authenticate(bare_client: httpx.AsyncClient) -> None:
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


Token = Callable[..., str]
