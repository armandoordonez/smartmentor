"""Gemini adapters (SDK ``google-genai``, as the Wizard of Oz notebook v2; ADR 0011 and 0012).

* ``GeminiProvider``: structured output with ``response_json_schema`` (the ``...LLM`` schema
  of ``prompts/schemas/llm/`` with its ``$defs`` resolved inline, as ``gemini_schema`` in the
  notebook). Usage = prompt tokens; output = candidates + thinking tokens.
* ``GeminiEmbeddingProvider``: ``embed_content`` with the task type of the purpose, the
  configured dimension and L2 normalisation.

The SDK client is injected so tests run without network or keys. The SDK is only imported here.
"""

from __future__ import annotations

import asyncio
import copy
import math
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.adapters.fake_llm import estimate_tokens
from app.ports.embedding import EmbeddingPurpose, EmbeddingResult
from app.ports.llm import (
    LlmContentBlockedError,
    LlmProviderError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
    LlmUsage,
)

_BLOCKED_FINISH = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}
_SCHEMA_METADATA = ("$schema", "$id", "$comment")
_TASK_TYPES: dict[EmbeddingPurpose, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
    "similarity": "SEMANTIC_SIMILARITY",
}
EMBED_BATCH = 100


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema with ``$ref`` to ``$defs`` resolved inline and metadata keys removed."""
    body = {k: v for k, v in schema.items() if k not in _SCHEMA_METADATA}
    defs: dict[str, Any] = body.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(i) for i in node]
        return node

    resolved: dict[str, Any] = resolve(body)
    return resolved


def _name(value: Any) -> str:
    return str(getattr(value, "name", value) or "")


class GeminiProvider:
    def __init__(self, client: Any, *, timeout_seconds: float) -> None:
        self._client = client
        self._timeout = timeout_seconds

    @classmethod
    def from_api_key(cls, api_key: str, *, timeout_seconds: float) -> GeminiProvider:
        return cls(genai.Client(api_key=api_key), timeout_seconds=timeout_seconds)

    @property
    def name(self) -> str:
        return "gemini"

    async def generate_structured(self, request: LlmRequest) -> LlmResponse:
        config = types.GenerateContentConfig(
            system_instruction=request.system,
            temperature=request.temperature,
            response_mime_type="application/json",
            response_json_schema=inline_schema(request.schema),
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=request.model, contents=request.user, config=config
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise LlmTimeoutError("gemini did not answer in time") from exc
        except genai_errors.APIError as exc:
            raise LlmProviderError(f"gemini API error {exc.code}") from exc
        except (OSError, ConnectionError) as exc:
            raise LlmProviderError("gemini network error") from exc

        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise LlmContentBlockedError(_name(feedback.block_reason))
        candidates = getattr(response, "candidates", None) or []
        if candidates and _name(getattr(candidates[0], "finish_reason", "")) in _BLOCKED_FINISH:
            raise LlmContentBlockedError(_name(candidates[0].finish_reason))
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) + int(
            getattr(usage, "thoughts_token_count", 0) or 0
        )
        return LlmResponse(
            text=getattr(response, "text", None) or "",
            usage=LlmUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            model=request.model,
        )


class GeminiEmbeddingProvider:
    def __init__(self, client: Any, *, model: str, dimension: int, timeout_seconds: float) -> None:
        self._client = client
        self._model = model
        self._dimension = dimension
        self._timeout = timeout_seconds

    @classmethod
    def from_api_key(
        cls, api_key: str, *, model: str, dimension: int, timeout_seconds: float
    ) -> GeminiEmbeddingProvider:
        return cls(
            genai.Client(api_key=api_key),
            model=model,
            dimension=dimension,
            timeout_seconds=timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str], purpose: EmbeddingPurpose) -> EmbeddingResult:
        config = types.EmbedContentConfig(
            task_type=_TASK_TYPES[purpose], output_dimensionality=self._dimension
        )
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = list(texts[start : start + EMBED_BATCH])
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.embed_content(
                        model=self._model, contents=batch, config=config
                    ),
                    timeout=self._timeout,
                )
            except TimeoutError as exc:
                raise LlmTimeoutError("gemini embeddings did not answer in time") from exc
            except genai_errors.APIError as exc:
                raise LlmProviderError(f"gemini embeddings API error {exc.code}") from exc
            for embedding in response.embeddings or []:
                values = [float(v) for v in embedding.values or []]
                norm = math.sqrt(math.fsum(v * v for v in values))
                vectors.append([v / norm for v in values] if norm > 0 else values)
        if len(vectors) != len(texts) or any(len(v) != self._dimension for v in vectors):
            raise LlmProviderError("gemini embeddings: unexpected count or dimension")
        # The embeddings API does not report usage: estimated from the text length.
        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            input_tokens=sum(estimate_tokens(t) for t in texts),
        )
