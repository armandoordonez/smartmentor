"""Shared fixtures: settings without ``.env``, fake providers, in-memory adapters, test tokens."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jsonschema import Draft202012Validator

from app.adapters.fake_embedding import FakeEmbeddingProvider
from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.memory import (
    InMemoryCallLogRepository,
    InMemoryCatalogReader,
    InMemoryGenerationCache,
    InMemoryJobRepository,
)
from app.application.pricing import ModelPrice, PriceTable
from app.container import Container, Overrides, build_container
from app.core.config import Settings
from app.core.security import ServiceTokenValidator
from app.main import create_app
from app.ports.catalog import OutcomeRecord, SyllabusDocumentRecord, TopicRecord
from tests.support import EXAMPLES_DIR, PROMPTS_DIR, SCHEMAS_DIR

ISSUER = "http://keycloak.test/realms/smartmentor"
AUDIENCE = "smartmentor-ai"
COURSE_ID = 3
SYLLABUS_DOCUMENT_ID = 7

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class _SigningKey:
    key: Any


class StaticKeyResolver:
    def get_signing_key_from_jwt(self, token: str) -> _SigningKey:
        del token
        return _SigningKey(_KEY.public_key())


def make_token(*, audience: str = AUDIENCE, issuer: str = ISSUER, ttl: int = 300) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": "service-account-smartmentor-api-service",
        "azp": "smartmentor-api-service",
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(claims, _KEY, algorithm="RS256")


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def outcomes(topic: str, n: int) -> list[OutcomeRecord]:
    return [
        OutcomeRecord(id=f"lo_{topic}_{i}", statement=f"Resultado {i} de {topic}")
        for i in range(1, n + 1)
    ]


def example_topics() -> list[TopicRecord]:
    """The three topics of the example syllabus (ids as in prompts/examples/llm/*.json)."""
    return [
        TopicRecord(
            id="fundamentos_datos",
            course_id=COURSE_ID,
            name="Fundamentos y preparación de datos",
            description="Partición de datos, fuga de información y preprocesamiento.",
            subtopics=["Partición entrenamiento/prueba", "Escalado de variables"],
            position=1,
            outcomes=outcomes("fundamentos_datos", 2),
        ),
        TopicRecord(
            id="regresion_lineal",
            course_id=COURSE_ID,
            name="Regresión lineal",
            description="Modelos lineales para variables continuas y sus métricas.",
            subtopics=["Mínimos cuadrados", "Error cuadrático medio"],
            position=2,
            outcomes=outcomes("regresion_lineal", 2),
        ),
        TopicRecord(
            id="regresion_logistica",
            course_id=COURSE_ID,
            name="Regresión logística",
            description="Clasificación binaria con la sigmoide y métricas de clasificación.",
            subtopics=["Sigmoide", "Matriz de confusión"],
            position=3,
            outcomes=outcomes("regresion_logistica", 3),
        ),
    ]


def make_settings(**changes: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "log_level": "WARNING",
        "ai_llm_provider": "fake",
        "ai_llm_model_default": "fake-default",
        "ai_llm_model_small": "fake-small",
        "ai_embedding_provider": "fake",
        "ai_embedding_model": "fake-embedding",
        "embedding_dimension": 64,
        "oidc_issuer_url": ISSUER,
        "oidc_jwks_url": "http://keycloak.test/certs",
        "ai_prompts_dir": PROMPTS_DIR,
    }
    values.update(changes)
    return Settings.model_validate(values)


TEST_PRICES = PriceTable(
    {
        "fake-default": ModelPrice(Decimal("0.30"), Decimal("2.50")),
        "fake-small": ModelPrice(Decimal("0.10"), Decimal("0.40")),
        "fake-embedding": ModelPrice(Decimal("0.15"), Decimal(0)),
    }
)


async def _ok() -> None:
    return None


def make_container(settings: Settings | None = None, **overrides: Any) -> Container:
    defaults: dict[str, Any] = {
        "clock": FakeClock(),
        "llm": FakeLlmProvider(EXAMPLES_DIR / "llm"),
        "embeddings": FakeEmbeddingProvider("fake-embedding", 64),
        "jobs": InMemoryJobRepository(),
        "call_logs": InMemoryCallLogRepository(),
        "cache": InMemoryGenerationCache(),
        "catalog": InMemoryCatalogReader(
            documents=[
                SyllabusDocumentRecord(
                    id=SYLLABUS_DOCUMENT_ID,
                    course_id=COURSE_ID,
                    text="Unidad 1. Fundamentos de datos. Unidad 2. Regresión lineal.",
                )
            ],
            topics=example_topics(),
        ),
        "prices": TEST_PRICES,
        "token_validator": ServiceTokenValidator(
            issuer=ISSUER, audience=AUDIENCE, key_resolver=StaticKeyResolver()
        ),
        "database_ping": _ok,
        "provider_backoff_seconds": 0.0,
    }
    defaults.update(overrides)
    return build_container(settings or make_settings(), Overrides(**defaults))


@pytest.fixture
def container() -> Container:
    return make_container()


@pytest.fixture
def fake_llm(container: Container) -> FakeLlmProvider:
    assert isinstance(container.llm, FakeLlmProvider)
    return container.llm


@pytest.fixture
def call_logs(container: Container) -> InMemoryCallLogRepository:
    assert isinstance(container.call_logs, InMemoryCallLogRepository)
    return container.call_logs


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(container)
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {make_token()}"}
    async with httpx.AsyncClient(
        transport=transport, base_url="http://ai.test", headers=headers
    ) as http:
        yield http


def contract_errors(contract: str, value: Any) -> list[str]:
    """Validate a result against ``prompts/schemas/<contract>.json`` (e.g. ``syllabus.v1``)."""
    schema = json.loads((SCHEMAS_DIR / f"{contract}.json").read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema).iter_errors(value)]


def example_llm(prompt_id: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (EXAMPLES_DIR / "llm" / f"{prompt_id}.json").read_text(encoding="utf-8")
    )
    return data


def repo_path(*parts: str) -> Path:
    return PROMPTS_DIR.parent.joinpath(*parts)
