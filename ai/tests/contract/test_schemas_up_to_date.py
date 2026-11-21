"""The versioned JSON Schemas match the Pydantic models (plan 5.4.14, contract tests)."""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from app.domain.contracts.registry import CONTRACTS, LLM_SCHEMAS
from scripts.export_schemas import expected_files
from tests.support import SCHEMAS_DIR

EXPECTED = expected_files()


@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_versioned_schema_matches_models(relative: str) -> None:
    path = SCHEMAS_DIR / relative
    assert path.exists(), f"missing {relative}: run `uv run python -m scripts.export_schemas`"
    assert path.read_text(encoding="utf-8") == EXPECTED[relative], (
        f"{relative} is stale: run `uv run python -m scripts.export_schemas`"
    )


def test_no_orphan_schema_files() -> None:
    on_disk = {p.relative_to(SCHEMAS_DIR).as_posix() for p in SCHEMAS_DIR.rglob("*.json")}
    assert on_disk == set(EXPECTED)


def test_registry_has_contracts_and_llm_schemas() -> None:
    assert len(CONTRACTS) == 16
    assert len(LLM_SCHEMAS) == 10
    assert len(EXPECTED) == len(CONTRACTS) + len(LLM_SCHEMAS)


@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_schema_is_valid_draft_2020_12(relative: str) -> None:
    schema = json.loads(EXPECTED[relative])
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith(relative)
