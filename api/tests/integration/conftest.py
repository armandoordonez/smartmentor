"""Fixtures de integración: base smartmentor_test migrada por Liquibase y tokens firmados de prueba.

Prepárala con: api/scripts/dev.sh prepare-test-db

Por defecto `client` está autenticado como un administrador. Para otros roles o sin token usa
`client_for(...)` y `bare_client`.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.security import TokenValidator
from app.main import app
from tests.auth_helpers import AUDIENCE, ISSUER, KeyPair, StaticKeyResolver, make_token

# Tablas de negocio que las pruebas vacían. roles es un catálogo sembrado por Liquibase.
_BUSINESS_TABLES = [
    "llm_call_logs",
    "badges",
    "assessment_attempts",
    "resources",
    "path_steps",
    "diagnostics",
    "enrollments",
    "learning_paths",
    "topic_prerequisites",
    "topics",
    "courses",
    "user_roles",
    "users",
]

ADMIN_SUB = "admin-sub"
ADMIN_EMAIL = "admin@test.example"


@pytest.fixture(scope="session")
def keys() -> KeyPair:
    return KeyPair()


@pytest.fixture(scope="session")
async def engine(keys: KeyPair) -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    assert settings.database_name.endswith("_test"), "Las pruebas solo corren sobre una base *_test"
    eng = create_engine(settings)
    app.state.session_factory = create_session_factory(eng)
    app.state.token_validator = TokenValidator(
        issuer=ISSUER, audience=AUDIENCE, key_resolver=StaticKeyResolver(keys)
    )
    yield eng
    await eng.dispose()


async def insert_user(
    engine: AsyncEngine, *, email: str, role: str, sub: str | None, name: str = "Usuario"
) -> int:
    """Crea un usuario con un rol directamente en la base (como lo dejaría un administrador)."""
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO users (full_name, email, identity_provider, identity_subject) "
                    "VALUES (:name, :email, CASE WHEN CAST(:sub AS text) IS NULL THEN NULL "
                    "ELSE 'keycloak' END, :sub) RETURNING id"
                ),
                {"name": name, "email": email, "sub": sub},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT :user_id, id FROM roles WHERE code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return int(user_id)


@pytest.fixture(autouse=True)
async def clean_database(engine: AsyncEngine) -> AsyncIterator[None]:
    tables = ", ".join(f"{t}, {t}_audit" for t in _BUSINESS_TABLES)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await insert_user(
        engine, email=ADMIN_EMAIL, role="admin", sub=ADMIN_SUB, name="Admin de prueba"
    )
    yield


@pytest.fixture
def token(keys: KeyPair) -> Callable[..., str]:
    """Firma un token con las llaves de prueba (argumentos de `make_token`)."""

    def _token(**kwargs: Any) -> str:
        return make_token(keys, **kwargs)

    return _token


@pytest.fixture
async def bare_client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente sin credenciales."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


ClientFactory = Callable[..., httpx.AsyncClient]


@pytest.fixture
async def client_for(
    engine: AsyncEngine, token: Callable[..., str]
) -> AsyncIterator[ClientFactory]:
    """Fábrica de clientes autenticados: client_for(sub=..., email=..., **claims)."""
    opened: list[httpx.AsyncClient] = []

    def _factory(**claims: Any) -> httpx.AsyncClient:
        http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token(**claims)}"},
        )
        opened.append(http)
        return http

    yield _factory
    for http in opened:
        await http.aclose()


@pytest.fixture
async def client(client_for: ClientFactory) -> httpx.AsyncClient:
    """Cliente autenticado como el administrador sembrado en cada prueba."""
    return client_for(sub=ADMIN_SUB, email=ADMIN_EMAIL)


Factory = Callable[..., Awaitable[dict[str, Any]]]
MakeFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@pytest.fixture
def make(client: httpx.AsyncClient) -> MakeFn:
    """POST a /api/v1/<path> como administrador y devuelve el JSON; falla si no responde 201."""

    async def _make(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await client.post(f"/api/v1/{path}", json=payload)
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    return _make


@pytest.fixture
async def world(make: MakeFn) -> dict[str, int]:
    """Cadena mínima de datos: usuario → curso → tema → ruta → inscripción."""
    user = await make("users", {"full_name": "Docente", "email": "docente@example.com"})
    student = await make("users", {"full_name": "Estudiante", "email": "estudiante@example.com"})
    course = await make("courses", {"owner_user_id": user["id"], "name": "Ciencia de datos"})
    topic = await make("topics", {"course_id": course["id"], "name": "Regresión"})
    path = await make("learning-paths", {"course_id": course["id"], "name": "Ruta base"})
    enrollment = await make(
        "enrollments", {"user_id": student["id"], "learning_path_id": path["id"]}
    )
    return {
        "teacher": user["id"],
        "student": student["id"],
        "course": course["id"],
        "topic": topic["id"],
        "path": path["id"],
        "enrollment": enrollment["id"],
    }
