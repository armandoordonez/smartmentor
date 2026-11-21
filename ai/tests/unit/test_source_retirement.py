"""The indexer follows the current sources of the course (R-010).

A note the instructor deactivates (or a replaced syllabus) is no longer read by the source
readers; the indexer retires its document so the search stops returning its fragments, and
reactivates it if the same text comes back.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from app.adapters.memory_knowledge import InMemoryKnowledgeStore
from app.application.embeddings.chunking import Chunk
from app.application.embeddings.indexer import CourseIndexer
from app.application.embeddings.sources import InMemorySourceReader
from app.application.embeddings.store import SourceMaterial
from app.application.llm_runner import CallContext, EmbeddingRunner
from app.ports.catalog import CatalogReader, TopicRecord
from app.ports.embedding import EmbeddingPurpose

COURSE = 7
SYLLABUS = SourceMaterial("Syllabus del curso", "Tema 1: regresión lineal y mínimos cuadrados.")
NOTES = SourceMaterial("Apuntes del curso (u1.md)", "La regresión ajusta una recta a los datos.")
CTX = CallContext(task="embeddings.index_course")


class _Embeddings:
    """Same vector for every text: the test only cares about which sources are active."""

    model = "fake-embedding"

    async def embed(
        self, texts: Sequence[str], purpose: EmbeddingPurpose, ctx: CallContext
    ) -> list[list[float]]:
        del purpose, ctx
        return [[1.0, 0.0] for _ in texts]


class _NoTopics:
    async def course_topics(self, course_id: int) -> list[TopicRecord]:
        del course_id
        return []


def _indexer(reader: InMemorySourceReader, store: InMemoryKnowledgeStore) -> CourseIndexer:
    return CourseIndexer(
        catalog=cast(CatalogReader, _NoTopics()),
        sources=reader,
        knowledge=store,
        embeddings=cast(EmbeddingRunner, _Embeddings()),
    )


async def _titles(store: InMemoryKnowledgeStore) -> set[str]:
    return {c.title for c in await store.search(COURSE, [1.0, 0.0], "fake-embedding", 10)}


async def test_a_deactivated_note_stops_grounding_the_explanations() -> None:
    store = InMemoryKnowledgeStore()
    reader = InMemorySourceReader({COURSE: [SYLLABUS, NOTES]})
    indexer = _indexer(reader, store)
    await indexer.index_course(COURSE, CTX)
    assert await _titles(store) == {SYLLABUS.title, NOTES.title}

    reader.by_course[COURSE] = [SYLLABUS]  # el instructor desactivó el apunte
    await indexer.index_course(COURSE, CTX)

    assert await _titles(store) == {SYLLABUS.title}


async def test_a_note_uploaded_again_is_used_again() -> None:
    store = InMemoryKnowledgeStore()
    reader = InMemorySourceReader({COURSE: [SYLLABUS, NOTES]})
    indexer = _indexer(reader, store)
    await indexer.index_course(COURSE, CTX)
    reader.by_course[COURSE] = [SYLLABUS]
    await indexer.index_course(COURSE, CTX)

    reader.by_course[COURSE] = [SYLLABUS, NOTES]
    await indexer.index_course(COURSE, CTX)

    assert await _titles(store) == {SYLLABUS.title, NOTES.title}


async def test_retiring_only_touches_the_given_course() -> None:
    store = InMemoryKnowledgeStore()
    for course in (COURSE, COURSE + 1):
        await store.save_source(course, NOTES, "sha-n", [Chunk(0, "x", 1)], [[1.0, 0.0]], "m")

    assert await store.retire_sources_except(COURSE, set()) == 1

    assert await store.search(COURSE, [1.0, 0.0], "m", 4) == []
    assert len(await store.search(COURSE + 1, [1.0, 0.0], "m", 4)) == 1
    assert not await store.has_source(COURSE, "sha-n", "m")
