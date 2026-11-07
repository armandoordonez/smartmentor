"""``embeddings.index_course``: fragments of the sources and vectors of the topics (plan 5.4.7).

Idempotent by content: a source with the same SHA-256 and a vector of the same model is not
embedded again, and a topic whose text did not change keeps its vector (``content_sha256``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.embeddings.chunking import split_chunks
from app.application.embeddings.sources import SourceMaterialReader
from app.application.embeddings.store import KnowledgeStore
from app.application.llm_runner import CallContext, EmbeddingRunner
from app.ports.catalog import CatalogReader
from app.ports.embedding import EmbeddingPurpose

EMBED_BATCH = 64


@dataclass(frozen=True)
class IndexReport:
    topics_indexed: int
    chunks_indexed: int
    embedding_model: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CourseIndexer:
    def __init__(
        self,
        *,
        catalog: CatalogReader,
        sources: SourceMaterialReader,
        knowledge: KnowledgeStore,
        embeddings: EmbeddingRunner,
    ) -> None:
        self._catalog = catalog
        self._sources = sources
        self._knowledge = knowledge
        self._embeddings = embeddings

    async def _embed_all(
        self, texts: Sequence[str], purpose: EmbeddingPurpose, ctx: CallContext
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            vectors += await self._embeddings.embed(
                texts[start : start + EMBED_BATCH], purpose, ctx
            )
        return vectors

    async def index_course(self, course_id: int, ctx: CallContext) -> IndexReport:
        """Index the sources and the topics of the course; the report counts what is current."""
        model = self._embeddings.model
        chunks_total = 0
        for material in await self._sources.sources(course_id):
            sha = sha256_text(material.text)
            chunks = split_chunks(material.text)
            chunks_total += len(chunks)
            if not chunks or await self._knowledge.has_source(course_id, sha, model):
                continue
            vectors = await self._embed_all([c.text for c in chunks], "document", ctx)
            await self._knowledge.save_source(course_id, material, sha, chunks, vectors, model)

        topics_total = 0
        for topic in await self._catalog.course_topics(course_id):
            try:
                owner_id = int(topic.id)
            except ValueError:
                continue
            text = topic.similarity_text()
            sha = sha256_text(text)
            topics_total += 1
            if await self._knowledge.vector_sha("topic", owner_id, model) == sha:
                continue
            (vector,) = await self._embed_all([text], "similarity", ctx)
            await self._knowledge.save_vector("topic", owner_id, model, vector, sha)
        return IndexReport(topics_total, chunks_total, model)
