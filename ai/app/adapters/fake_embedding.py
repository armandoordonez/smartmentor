"""``FakeEmbeddingProvider``: deterministic hashed bag-of-words vectors (no network).

Texts that share words get a higher cosine, which is enough to exercise the profile and resume
signals in tests. Vectors are L2-normalised like the real adapter.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from app.adapters.fake_llm import estimate_tokens
from app.ports.embedding import EmbeddingPurpose, EmbeddingResult

_WORD = re.compile(r"\w+", re.UNICODE)


def hashed_vector(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    for word in _WORD.findall(text.casefold()):
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm > 0 else vector


class FakeEmbeddingProvider:
    def __init__(self, model: str, dimension: int) -> None:
        self._model = model
        self._dimension = dimension
        self.calls: list[tuple[list[str], EmbeddingPurpose]] = []

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str], purpose: EmbeddingPurpose) -> EmbeddingResult:
        self.calls.append((list(texts), purpose))
        return EmbeddingResult(
            vectors=[hashed_vector(t, self._dimension) for t in texts],
            model=self._model,
            input_tokens=sum(estimate_tokens(t) for t in texts),
        )
