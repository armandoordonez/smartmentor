"""prompts/catalog.yaml and prompts/<id>/v<n>.md are consistent (plan 5.4.5 and 5.4.12)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import pytest

from app.domain.contracts.registry import CONTRACTS, LLM_SCHEMAS, schema_relative_path
from tests.support import PROMPTS_DIR, SCHEMAS_DIR, PromptFile, load_catalog, parse_prompt

CATALOG = load_catalog()
ENTRIES: dict[str, dict[str, Any]] = {p["id"]: p for p in CATALOG["prompts"]}
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
DATA_BLOCK = re.compile(r"^<<<\n(.*?)\n>>>$", re.DOTALL | re.M)
FORBIDDEN_WORDS = re.compile(r"\b(estudiantes?|docentes?|students?|teachers?)\b", re.IGNORECASE)
FRONT_MATTER_KEYS = {
    "id",
    "version",
    "name_es",
    "task",
    "temperature",
    "model_tier",
    "output_schema",
    "contract",
    "variables",
    "source",
}


def _current(prompt_id: str) -> PromptFile:
    version = ENTRIES[prompt_id]["current_version"]
    return parse_prompt(PROMPTS_DIR / prompt_id / f"v{version}.md")


def test_catalog_has_the_thirteen_prompts_of_the_notebook() -> None:
    assert CATALOG["schema_version"] == "v1"
    assert len(ENTRIES) == len(CATALOG["prompts"]) == 13


@pytest.mark.parametrize("prompt_id", sorted(ENTRIES))
def test_every_version_file_matches_its_registered_hash(prompt_id: str) -> None:
    versions: dict[int, str] = ENTRIES[prompt_id]["versions"]
    files = sorted((PROMPTS_DIR / prompt_id).glob("v*.md"))
    assert {int(f.stem[1:]) for f in files} == set(versions)
    for number, digest in versions.items():
        content = (PROMPTS_DIR / prompt_id / f"v{number}.md").read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest, (
            f"{prompt_id}/v{number}.md changed: create a new version instead of editing it"
        )
    assert ENTRIES[prompt_id]["current_version"] == max(versions)


@pytest.mark.parametrize("prompt_id", sorted(ENTRIES))
def test_front_matter_agrees_with_catalog(prompt_id: str) -> None:
    entry, prompt = ENTRIES[prompt_id], _current(prompt_id)
    assert set(prompt.meta) == FRONT_MATTER_KEYS
    assert prompt.meta["id"] == prompt_id
    assert prompt.meta["version"] == entry["current_version"]
    for key in ("name_es", "task", "temperature", "model_tier", "output_schema", "contract"):
        assert prompt.meta[key] == entry[key], key
    assert entry["model_tier"] in {"default", "small"}
    assert 0 <= entry["temperature"] <= 1


@pytest.mark.parametrize("prompt_id", sorted(ENTRIES))
def test_schemas_referenced_by_the_prompt_exist(prompt_id: str) -> None:
    entry = ENTRIES[prompt_id]
    assert (SCHEMAS_DIR / entry["output_schema"]).exists()
    assert (SCHEMAS_DIR / entry["contract"]).exists()
    llm_names = {schema_relative_path(n, "llm") for n in LLM_SCHEMAS}
    contract_names = {schema_relative_path(n, "contract") for n in CONTRACTS}
    assert entry["output_schema"] in llm_names
    assert entry["contract"] in contract_names


@pytest.mark.parametrize("prompt_id", sorted(ENTRIES))
def test_placeholders_are_declared_and_user_data_is_delimited(prompt_id: str) -> None:
    prompt = _current(prompt_id)
    declared: dict[str, list[str]] = prompt.meta["variables"]
    data, parameters = set(declared["data"]), set(declared["parameters"])
    assert not data & parameters
    assert PLACEHOLDER.findall(prompt.system) == []
    used = set(PLACEHOLDER.findall(prompt.user))
    assert used == data | parameters
    # Plan 5.4.12: user and third-party text goes between delimiters and is treated as data.
    delimited = {m for block in DATA_BLOCK.findall(prompt.user) for m in PLACEHOLDER.findall(block)}
    outside = PLACEHOLDER.findall(DATA_BLOCK.sub("", prompt.user))
    assert data <= delimited
    assert not data & set(outside)
    assert "<<<" in prompt.system
    assert ">>>" in prompt.system
    # Only {placeholder} braces: str.format must render every template.
    rendered = prompt.user.format(**dict.fromkeys(used, "x"))
    assert "{" not in rendered
    assert "}" not in rendered


@pytest.mark.parametrize("prompt_id", sorted(ENTRIES))
def test_prompt_text_uses_learner_and_instructor_vocabulary(prompt_id: str) -> None:
    prompt = _current(prompt_id)
    assert FORBIDDEN_WORDS.findall(prompt.system + "\n" + prompt.user) == []
