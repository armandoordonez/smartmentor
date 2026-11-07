"""``GeminiProvider`` with an injected fake client (no network, no keys)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors as genai_errors

from app.adapters.gemini import GeminiEmbeddingProvider, GeminiProvider, inline_schema
from app.ports.llm import LlmContentBlockedError, LlmProviderError, LlmRequest
from tests.support import SCHEMAS_DIR, load_json


class _Models:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict[str, Any] = {}

    async def generate_content(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response

    async def embed_content(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _client(models: _Models) -> Any:
    return SimpleNamespace(aio=SimpleNamespace(models=models))


REQUEST = LlmRequest(
    prompt_id="item_review",
    prompt_version=1,
    system="system",
    user="user",
    schema_name="llm/item_review_llm.v1.json",
    schema=load_json(SCHEMAS_DIR / "llm" / "item_review_llm.v1.json"),
    model="model-under-test",
    temperature=0.0,
)


def test_inline_schema_resolves_refs_and_drops_metadata() -> None:
    schema = inline_schema(REQUEST.schema)
    assert "$defs" not in schema
    assert "$schema" not in schema
    assert "$ref" not in str(schema)
    assert schema["properties"]["reviews"]["items"]["properties"]["item_id"]["type"] == "string"


async def test_structured_call_maps_config_and_usage() -> None:
    usage = SimpleNamespace(
        prompt_token_count=100, candidates_token_count=40, thoughts_token_count=10
    )
    models = _Models(SimpleNamespace(text='{"reviews": []}', usage_metadata=usage, candidates=[]))
    response = await GeminiProvider(_client(models), timeout_seconds=5).generate_structured(REQUEST)
    assert response.text == '{"reviews": []}'
    assert (response.usage.input_tokens, response.usage.output_tokens) == (100, 50)
    config = models.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.system_instruction == "system"
    assert models.kwargs["model"] == "model-under-test"


async def test_api_errors_become_provider_errors() -> None:
    error = genai_errors.ServerError(503, {"error": {"message": "unavailable"}})
    provider = GeminiProvider(_client(_Models(error=error)), timeout_seconds=5)
    with pytest.raises(LlmProviderError):
        await provider.generate_structured(REQUEST)


async def test_safety_block_is_reported() -> None:
    candidate = SimpleNamespace(finish_reason=SimpleNamespace(name="SAFETY"))
    response = SimpleNamespace(text="", usage_metadata=None, candidates=[candidate])
    provider = GeminiProvider(_client(_Models(response)), timeout_seconds=5)
    with pytest.raises(LlmContentBlockedError):
        await provider.generate_structured(REQUEST)


async def test_embeddings_are_normalised() -> None:
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[3.0, 4.0]), SimpleNamespace(values=[0.0, 2.0])]
    )
    models = _Models(response)
    provider = GeminiEmbeddingProvider(
        _client(models), model="embedding-under-test", dimension=2, timeout_seconds=5
    )
    result = await provider.embed(["a", "b"], "similarity")
    assert result.vectors == [[0.6, 0.8], [0.0, 1.0]]
    assert models.kwargs["config"].task_type == "SEMANTIC_SIMILARITY"
