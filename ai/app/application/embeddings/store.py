"""``KnowledgeStore``: sources, fragments and their vectors (``source_documents``,
``document_chunks`` and ``ai_embeddings``, ADR 0012 and 0013).

``ai/`` writes these tables (ADR 0009). The vector of a fragment lives in ``ai_embeddings`` with
``owner_type = chunk``; the cosine search is one SQL query (no LlamaIndex, ADR 0013).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from app.application.embeddings.chunking import Chunk

OwnerType = Literal["topic", "profile", "video", "chunk"]


@dataclass(frozen=True)
class SourceMaterial:
    """A reference document of a course (instructor notes, open book) with its license."""

    title: str
    text: str
    url: str | None = None
    license: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    """A fragment found by the search, with the data of its source for the citations."""

    chunk_id: str
    source_document_id: int
    chunk_index: int
    text: str
    title: str
    url: str | None
    license: str | None
    score: float


class KnowledgeStore(Protocol):
    async def has_source(self, course_id: int, sha256: str, model: str) -> bool:
        """The document is stored and every fragment has a vector of ``model``."""
        ...

    async def save_source(
        self,
        course_id: int,
        material: SourceMaterial,
        sha256: str,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        model: str,
    ) -> int:
        """Store (or complete) a document with its fragments and vectors; returns its id."""
        ...

    async def search(
        self, course_id: int, vector: Sequence[float], model: str, k: int
    ) -> list[RetrievedChunk]:
        """Top ``k`` fragments of the course by cosine similarity (same ``model`` only)."""
        ...

    async def chunks_by_ids(self, chunk_ids: Sequence[str]) -> list[RetrievedChunk]:
        """The given fragments in the given order (unknown ids are left out)."""
        ...

    async def vector_sha(self, owner_type: OwnerType, owner_id: int, model: str) -> str | None: ...

    async def save_vector(
        self,
        owner_type: OwnerType,
        owner_id: int,
        model: str,
        vector: Sequence[float],
        content_sha256: str,
    ) -> None: ...
