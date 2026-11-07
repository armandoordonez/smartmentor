"""``EmbeddingProvider`` port (plan 5.4.7, ADR 0012).

Every vector compared with another must come from the same model: the adapter reports its
``model`` and ``dimension`` and returns L2-normalised vectors.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

EmbeddingPurpose = Literal["document", "query", "similarity"]


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    input_tokens: int


class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: Sequence[str], purpose: EmbeddingPurpose) -> EmbeddingResult: ...
