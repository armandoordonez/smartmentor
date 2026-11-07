"""Retrieval of the fragments that ground an explanation (top-k = 4 by cosine, plan 5.4.7)."""

from __future__ import annotations

from app.application.embeddings.indexer import CourseIndexer
from app.application.embeddings.store import KnowledgeStore, RetrievedChunk
from app.application.llm_runner import CallContext, EmbeddingRunner
from app.domain.errors import TaskError
from app.ports.catalog import TopicRecord

TOP_K = 4


def topic_query(topic: TopicRecord, extra: str = "") -> str:
    """Text embedded as the search query: the topic, its subtopics and its learning outcomes."""
    outcomes = " ".join(o.statement for o in topic.outcomes)
    parts = [topic.similarity_text(), outcomes, extra]
    return " ".join(p for p in parts if p).strip()


class Retriever:
    def __init__(
        self,
        *,
        indexer: CourseIndexer,
        knowledge: KnowledgeStore,
        embeddings: EmbeddingRunner,
        top_k: int = TOP_K,
    ) -> None:
        self._indexer = indexer
        self._knowledge = knowledge
        self._embeddings = embeddings
        self._top_k = top_k

    async def retrieve(
        self, topic: TopicRecord, ctx: CallContext, *, extra_query: str = ""
    ) -> list[RetrievedChunk]:
        """Top-k fragments of the topic's course.

        The course is indexed first (cheap when nothing changed), so the order of the jobs of
        ``course.generate_content`` does not matter. No fragment ends the job with
        ``NO_SOURCE_FRAGMENTS`` (no sources uploaded for the course).
        """
        await self._indexer.index_course(topic.course_id, ctx)
        (vector,) = await self._embeddings.embed([topic_query(topic, extra_query)], "query", ctx)
        chunks = await self._knowledge.search(
            topic.course_id, vector, self._embeddings.model, self._top_k
        )
        if not chunks:
            raise TaskError(
                "NO_SOURCE_FRAGMENTS", f"no source fragments for the course of topic {topic.id}"
            )
        return chunks
