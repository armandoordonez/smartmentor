"""Every default answer of ``FakeLlmProvider`` validates against the prompt's output schema
(plan 5.4.14, contract tests) and the prompt store serves the versioned prompts."""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.prompt_files import FilePromptStore
from app.ports.llm import LlmRequest
from tests.support import EXAMPLES_DIR, PROMPTS_DIR, load_catalog

STORE = FilePromptStore(PROMPTS_DIR)
PROMPT_IDS = sorted(p["id"] for p in load_catalog()["prompts"])


def test_prompt_store_loads_every_prompt_without_issues() -> None:
    assert STORE.verify() == []
    assert sorted(e.id for e in STORE.catalog()) == PROMPT_IDS


@pytest.mark.parametrize("prompt_id", PROMPT_IDS)
async def test_fake_default_answer_matches_the_output_schema(prompt_id: str) -> None:
    template = STORE.get(prompt_id)
    fake = FakeLlmProvider(EXAMPLES_DIR / "llm")
    user = template.user
    if prompt_id == "item_review":
        items = [{"item_id": "q1"}, {"item_id": "q2"}]
        user = template.render({"items": json.dumps(items)})
    request = LlmRequest(
        prompt_id=prompt_id,
        prompt_version=template.version,
        system=template.system,
        user=user,
        schema_name=template.output_schema_name,
        schema=template.output_schema,
        model="fake-default",
        temperature=template.temperature,
    )
    response = await fake.generate_structured(request)
    errors = list(
        Draft202012Validator(template.output_schema).iter_errors(json.loads(response.text))
    )
    assert errors == []
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


async def test_fake_item_review_reviews_exactly_the_received_items() -> None:
    template = STORE.get("item_review")
    fake = FakeLlmProvider(EXAMPLES_DIR / "llm")
    items = [{"item_id": "d_a_1"}, {"item_id": "d_a_2"}]
    request = LlmRequest(
        prompt_id="item_review",
        prompt_version=1,
        system=template.system,
        user=template.render({"items": json.dumps(items)}),
        schema_name=template.output_schema_name,
        schema=template.output_schema,
        model="fake-small",
        temperature=0.0,
    )
    answer = json.loads((await fake.generate_structured(request)).text)
    assert [r["item_id"] for r in answer["reviews"]] == ["d_a_1", "d_a_2"]
