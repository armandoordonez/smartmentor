"""Settings without defaults for models, ``/ready`` and the price table."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.application.pricing import PriceTable
from app.core.config import Settings
from tests.conftest import make_container, make_settings, repo_path


def test_no_model_or_provider_defaults_in_code() -> None:
    settings = Settings.model_validate({})
    assert settings.ai_llm_provider is None
    assert settings.ai_llm_model_default is None
    missing = settings.missing_configuration()
    for name in (
        "AI_LLM_PROVIDER",
        "AI_LLM_MODEL_DEFAULT",
        "AI_LLM_MODEL_SMALL",
        "AI_EMBEDDING_PROVIDER",
        "AI_EMBEDDING_MODEL",
        "EMBEDDING_DIMENSION",
    ):
        assert name in missing


def test_empty_values_count_as_missing() -> None:
    settings = Settings.model_validate({"ai_llm_model_default": "", "ai_daily_budget_usd": ""})
    assert settings.ai_llm_model_default is None
    assert settings.ai_daily_budget_usd is None


def test_real_provider_needs_key_and_every_budget() -> None:
    settings = make_settings(ai_llm_provider="gemini")
    missing = settings.missing_configuration()
    assert "GEMINI_API_KEY" in missing
    assert "AI_DAILY_BUDGET_USD" in missing
    assert "AI_ENROLLMENT_BUDGET_USD" in missing


def test_versioned_prices_file_has_structure_and_no_prices() -> None:
    table = PriceTable.load(repo_path("ai", "config", "prices.yaml"))
    assert table.issues == []
    assert table.missing(["any-model"]) == ["any-model"]


def test_price_file_parsing(tmp_path: Path) -> None:
    path = tmp_path / "prices.yaml"
    path.write_text(
        "currency: USD\nunit: per_million_tokens\nmodels:\n  m1: {input: 0.3, output: 2.5}\n"
        "  bad: {output: 1}\n",
        encoding="utf-8",
    )
    table = PriceTable.load(path)
    assert table.cost("m1", 1_000_000, 1_000_000) == Decimal("2.800000")
    assert table.issues == ["prices.yaml: model bad needs numeric input and output"]


async def test_ready_with_fake_provider() -> None:
    assert await make_container().readiness() == []


async def test_ready_lists_missing_configuration_and_prices() -> None:
    settings = make_settings(
        ai_llm_provider="gemini",
        gemini_api_key="test-only-not-a-secret",
        ai_daily_budget_usd=Decimal(5),
        ai_monthly_budget_usd=Decimal(30),
        ai_course_budget_usd=Decimal(2),
        ai_enrollment_budget_usd=Decimal("0.5"),
        ai_llm_model_small=None,
    )
    missing = await make_container(settings, prices=PriceTable({})).readiness()
    assert "env:AI_LLM_MODEL_SMALL" in missing
    assert "prices:model fake-default has no price in config/prices.yaml" in missing


async def test_ready_reports_database_errors() -> None:
    async def broken() -> None:
        raise ConnectionRefusedError

    missing = await make_container(database_ping=broken).readiness()
    assert missing == ["database:ConnectionRefusedError"]


def test_database_url_requires_tls_only_when_asked() -> None:
    base = {
        "database_host": "ep-demo.neon.tech",
        "database_name": "smartmentor",
        "ai_database_user": "smartmentor_ai",
        "ai_database_password": "x",
    }
    assert not Settings.model_validate(base).database_url.endswith("?ssl=require")
    secure = Settings.model_validate({**base, "database_ssl": True})
    assert secure.database_url.endswith("/smartmentor?ssl=require")
