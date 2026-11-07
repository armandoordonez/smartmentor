"""``GeminiEmbeddingProvider``: embeddings of the Gemini family behind ``EmbeddingProvider``
(ADR 0012: the model of the notebook v2, 768 dimensions, L2-normalised).

``task_type`` differs by purpose (documents, queries, symmetric similarity) as the notebook does.
Vectors cut to ``output_dimensionality`` are not unit length, so they are normalised here: the
rest of the service compares them with a plain dot product.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Any

from google.genai import errors, types

from app.ports.embedding import EmbeddingPurpose, EmbeddingResult
from app.ports.llm import LlmProviderError, LlmTimeoutError

TASK_TYPES: dict[EmbeddingPurpose, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
    "similarity": "SEMANTIC_SIMILARITY",
}
CHARS_PER_TOKEN = 4


def l2_normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm > 0 else list(vector)


class GeminiEmbeddingProvider:
    """``client`` is a ``google.genai.Client`` (only ``aio.models.embed_content`` is used)."""

    def __init__(self, client: Any, model: str, dimension: int, *, timeout_seconds: float = 60.0):
        self._client = client
        self._model = model
        self._dimension = dimension
        self._timeout = timeout_seconds

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
        if not texts:
            return EmbeddingResult(vectors=[], model=self._model, input_tokens=0)
        config = types.EmbedContentConfig(
            task_type=TASK_TYPES[purpose], output_dimensionality=self._dimension
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.embed_content(
                    model=self._model, contents=list(texts), config=config
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise LlmTimeoutError("the embedding request timed out") from exc
        except errors.APIError as exc:
            raise LlmProviderError(f"embedding provider error {exc.code}") from None
        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise LlmProviderError("the embedding provider returned a different number of vectors")
        vectors = [l2_normalize(e.values or []) for e in embeddings]
        if any(len(v) != self._dimension for v in vectors):
            raise LlmProviderError(f"embedding dimension is not {self._dimension}")
        tokens = sum(max(1, len(t) // CHARS_PER_TOKEN) for t in texts)
        return EmbeddingResult(vectors=vectors, model=self._model, input_tokens=tokens)
