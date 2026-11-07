"""``InMemoryKnowledgeStore``: sources, fragments and vectors in memory (tests and evaluation).

It follows the rules of the PostgreSQL adapter: a source is unique by (course, SHA-256), vectors
are compared only within the same model, and the score is the cosine similarity.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.embeddings.chunking import Chunk
from app.application.embeddings.store import OwnerType, RetrievedChunk, SourceMaterial


@dataclass
class _Source:
    id: int
    course_id: int
    sha256: str
    material: SourceMaterial


@dataclass
class _StoredChunk:
    id: int
    source_id: int
    index: int
    text: str
    vectors: dict[str, list[float]]  # by model


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._sources: list[_Source] = []
        self._chunks: list[_StoredChunk] = []
        self._vectors: dict[tuple[OwnerType, int, str], tuple[list[float], str]] = {}

    def _source(self, course_id: int, sha256: str) -> _Source | None:
        return next(
            (s for s in self._sources if s.course_id == course_id and s.sha256 == sha256), None
        )

    async def has_source(self, course_id: int, sha256: str, model: str) -> bool:
        source = self._source(course_id, sha256)
        if source is None:
            return False
        chunks = [c for c in self._chunks if c.source_id == source.id]
        return bool(chunks) and all(model in c.vectors for c in chunks)

    async def save_source(
        self,
        course_id: int,
        material: SourceMaterial,
        sha256: str,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        model: str,
    ) -> int:
        source = self._source(course_id, sha256)
        if source is None:
            source = _Source(len(self._sources) + 1, course_id, sha256, material)
            self._sources.append(source)
        existing = {c.index: c for c in self._chunks if c.source_id == source.id}
        for chunk, vector in zip(chunks, vectors, strict=True):
            stored = existing.get(chunk.index)
            if stored is None:
                stored = _StoredChunk(len(self._chunks) + 1, source.id, chunk.index, chunk.text, {})
                self._chunks.append(stored)
            stored.vectors[model] = list(vector)
        return source.id

    def _retrieved(self, chunk: _StoredChunk, score: float) -> RetrievedChunk:
        source = next(s for s in self._sources if s.id == chunk.source_id)
        return RetrievedChunk(
            chunk_id=str(chunk.id),
            source_document_id=source.id,
            chunk_index=chunk.index,
            text=chunk.text,
            title=source.material.title,
            url=source.material.url,
            license=source.material.license,
            score=score,
        )

    async def search(
        self, course_id: int, vector: Sequence[float], model: str, k: int
    ) -> list[RetrievedChunk]:
        course_sources = {s.id for s in self._sources if s.course_id == course_id}
        scored = [
            (cosine(vector, c.vectors[model]), c)
            for c in self._chunks
            if c.source_id in course_sources and model in c.vectors
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [self._retrieved(c, score) for score, c in scored[:k]]

    async def chunks_by_ids(self, chunk_ids: Sequence[str]) -> list[RetrievedChunk]:
        by_id = {str(c.id): c for c in self._chunks}
        return [self._retrieved(by_id[i], 1.0) for i in chunk_ids if i in by_id]

    async def vector_sha(self, owner_type: OwnerType, owner_id: int, model: str) -> str | None:
        entry = self._vectors.get((owner_type, owner_id, model))
        return None if entry is None else entry[1]

    async def save_vector(
        self,
        owner_type: OwnerType,
        owner_id: int,
        model: str,
        vector: Sequence[float],
        content_sha256: str,
    ) -> None:
        self._vectors[(owner_type, owner_id, model)] = (list(vector), content_sha256)
