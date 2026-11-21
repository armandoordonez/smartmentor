"""AI_RAG_TOP_K: default, reading from the environment, bounds and use in the retriever."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.adapters.memory_knowledge import InMemoryKnowledgeStore
from app.application.embeddings.retrieval import Retriever
from app.application.embeddings.store import RetrievedChunk
from app.core.config import Settings


def test_default_top_k_is_4() -> None:
    assert Settings.model_validate({}).ai_rag_top_k == 4


def test_top_k_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_RAG_TOP_K", "9")
    assert Settings().ai_rag_top_k == 9


@pytest.mark.parametrize("value", [0, 21])
def test_top_k_out_of_range_is_rejected(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"ai_rag_top_k": value})


class RecordingStore(InMemoryKnowledgeStore):
    def __init__(self) -> None:
        super().__init__()
        self.asked: list[int] = []

    async def search(
        self, course_id: int, vector: Sequence[float], model: str, k: int
    ) -> list[RetrievedChunk]:
        self.asked.append(k)
        return await super().search(course_id, vector, model, k)


class StubIndexer:
    async def index_course(self, course_id: int, ctx: Any) -> None:
        return None


class StubEmbeddings:
    model = "m"

    async def embed(self, texts: Sequence[str], kind: str, ctx: Any) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


@pytest.mark.parametrize("top_k", [1, 4, 12])
async def test_retriever_asks_the_store_for_exactly_top_k(top_k: int) -> None:
    store = RecordingStore()
    retriever = Retriever(
        indexer=StubIndexer(),  # type: ignore[arg-type]
        knowledge=store,
        embeddings=StubEmbeddings(),  # type: ignore[arg-type]
        top_k=top_k,
    )
    topic = SimpleNamespace(id=1, course_id=7, outcomes=[], similarity_text=lambda: "tema")
    # The store is empty, so the retriever ends with NO_SOURCE_FRAGMENTS, but only after asking
    # the store for exactly top_k fragments.
    with pytest.raises(Exception, match="no source fragments"):
        await retriever.retrieve(topic, None)  # type: ignore[arg-type]
    assert store.asked == [top_k]
