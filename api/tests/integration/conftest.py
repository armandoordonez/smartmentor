"""Fixtures de integración: base smartmentor_test migrada por Liquibase y tokens firmados de prueba.

Prepárala con: api/scripts/dev.sh prepare-test-db

Por defecto `client` está autenticado como un administrador. Para otros roles o sin token usa
`client_for(...)` y `bare_client`.
"""

import os
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.idempotency import InMemoryIdempotencyStore
from app.core.security import TokenValidator
from app.domains.ai_gateway.fake import FakeAiService
from app.main import app
from tests.auth_helpers import AUDIENCE, ISSUER, KeyPair, StaticKeyResolver, make_token

# Tablas de negocio que las pruebas vacían (con su `_audit`). `roles` es un catálogo sembrado.
_BUSINESS_TABLES = [
    "alerts",
    "survey_responses",
    "badges",
    "attempt_answers",
    "assessment_attempts",
    "attempt_grants",
    "path_steps",
    "diagnostics",
    "enrollments",
    "assessment_items",
    "syllabus_extractions",
    "syllabus_documents",
    "learning_outcomes",
    "topic_prerequisites",
    "topics",
    "learning_paths",
    "courses",
    "ai_jobs",
    "consents",
    "data_subject_requests",
    "user_profiles",
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
    app.state.ai_service = FakeAiService()
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


@pytest.fixture(scope="session")
async def setup_engine(engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """Motor para vaciar la base. Con `TEST_SETUP_DATABASE_USER` la API corre con el usuario de
    mínimo privilegio (`smartmentor_api`, sin TRUNCATE) y la limpieza usa ese otro usuario.
    """
    user = os.environ.get("TEST_SETUP_DATABASE_USER")
    if not user:
        yield engine
        return
    settings = get_settings().model_copy(
        update={
            "database_user": user,
            "database_password": SecretStr(os.environ.get("TEST_SETUP_DATABASE_PASSWORD", "")),
        }
    )
    setup = create_engine(settings)
    yield setup
    await setup.dispose()


@pytest.fixture(autouse=True)
async def clean_database(engine: AsyncEngine, setup_engine: AsyncEngine) -> None:
    app.state.ai_service = FakeAiService()
    app.state.idempotency_store = InMemoryIdempotencyStore()
    # `interaction_events` es de solo inserción: no tiene `_audit`.
    tables = ", ".join([*(f"{t}, {t}_audit" for t in _BUSINESS_TABLES), "interaction_events"])
    async with setup_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await insert_user(
        engine, email=ADMIN_EMAIL, role="admin", sub=ADMIN_SUB, name="Admin de prueba"
    )


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


@pytest.fixture
def ai() -> FakeAiService:
    """El `FakeAiService` que usa la aplicación en esta prueba."""
    service = app.state.ai_service
    assert isinstance(service, FakeAiService)
    return service
