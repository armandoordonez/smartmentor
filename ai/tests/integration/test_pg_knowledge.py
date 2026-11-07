"""``PgKnowledgeStore`` against PostgreSQL with pgvector (skipped without AI_TEST_DATABASE_URL).

The URL must point to a disposable database. The test creates the three tables with the columns
of the Liquibase changelog (``040``, ``041`` and ``039``) in a private schema, so it works on a
bare ``pgvector`` image and leaves nothing behind.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.adapters.pg_knowledge import PgKnowledgeStore
from app.application.embeddings.chunking import Chunk
from app.application.embeddings.store import SourceMaterial

URL = os.environ.get("AI_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(URL is None, reason="AI_TEST_DATABASE_URL is not set"),
]

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
DROP SCHEMA IF EXISTS kn_test CASCADE;
CREATE SCHEMA kn_test;
SET search_path TO kn_test, public;
CREATE TABLE source_documents (
  id bigserial PRIMARY KEY, course_id bigint NOT NULL, title varchar(500) NOT NULL,
  url varchar(1000), license varchar(200), sha256 char(64) NOT NULL,
  active boolean NOT NULL DEFAULT true, UNIQUE (course_id, sha256));
CREATE TABLE document_chunks (
  id bigserial PRIMARY KEY, source_document_id bigint NOT NULL REFERENCES source_documents(id),
  chunk_index integer NOT NULL, text text NOT NULL, token_count integer NOT NULL,
  active boolean NOT NULL DEFAULT true, UNIQUE (source_document_id, chunk_index));
CREATE TABLE ai_embeddings (
  id bigserial PRIMARY KEY, owner_type varchar(10) NOT NULL, owner_id bigint NOT NULL,
  model varchar(100) NOT NULL, embedding vector(3) NOT NULL, content_sha256 char(64) NOT NULL,
  active boolean NOT NULL DEFAULT true, UNIQUE (owner_type, owner_id, model));
"""


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    assert URL is not None
    eng = create_async_engine(
        URL, connect_args={"server_settings": {"search_path": "kn_test,public"}}
    )
    async with eng.begin() as conn:
        for statement in [s for s in DDL.split(";") if s.strip()]:
            await conn.execute(text(statement))
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA kn_test CASCADE"))
    await eng.dispose()


async def test_save_search_and_reload(engine: AsyncEngine) -> None:
    store = PgKnowledgeStore(engine)
    sha = "a" * 64
    material = SourceMaterial("Apuntes", "x", url="https://example.org/a", license="CC0")
    chunks = [Chunk(0, "cerca", 1), Chunk(1, "lejos", 1)]
    assert not await store.has_source(1, sha, "m1")
    await store.save_source(1, material, sha, chunks, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], "m1")
    await store.save_source(
        2, SourceMaterial("Ajeno", "y"), "b" * 64, [Chunk(0, "otro", 1)], [[1.0, 0.0, 0.0]], "m1"
    )
    assert await store.has_source(1, sha, "m1")
    assert not await store.has_source(1, sha, "m2")

    found = await store.search(1, [0.9, 0.1, 0.0], "m1", 4)
    assert [c.text for c in found] == ["cerca", "lejos"]
    assert found[0].license == "CC0" and found[0].score > found[1].score
    assert await store.search(1, [1.0, 0.0, 0.0], "m2", 4) == []

    by_id = await store.chunks_by_ids([found[1].chunk_id, found[0].chunk_id, "abc"])
    assert [c.text for c in by_id] == ["lejos", "cerca"]

    # Saving the same source again is idempotent.
    await store.save_source(1, material, sha, chunks, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], "m1")
    assert len(await store.search(1, [1.0, 0.0, 0.0], "m1", 10)) == 2


async def test_topic_vectors_keep_their_hash(engine: AsyncEngine) -> None:
    store = PgKnowledgeStore(engine)
    assert await store.vector_sha("topic", 5, "m1") is None
    await store.save_vector("topic", 5, "m1", [0.0, 0.0, 1.0], "c" * 64)
    assert await store.vector_sha("topic", 5, "m1") == "c" * 64
    await store.save_vector("topic", 5, "m1", [0.0, 1.0, 0.0], "d" * 64)
    assert await store.vector_sha("topic", 5, "m1") == "d" * 64
