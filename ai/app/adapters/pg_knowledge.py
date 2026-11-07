"""``PgKnowledgeStore``: ``source_documents``, ``document_chunks`` and ``ai_embeddings`` in
PostgreSQL with pgvector (ADR 0012 and 0013).

The fragment vector lives in ``ai_embeddings`` (``owner_type = 'chunk'``); the search is one query
with the cosine distance operator ``<=>`` over the active fragments of the course, filtered by
model so vectors of different models are never compared. Vectors travel as text literals
(``'[0.1,0.2]'`` cast to ``vector``), so no pgvector codec is needed in asyncpg.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.embeddings.chunking import Chunk
from app.application.embeddings.indexer import sha256_text
from app.application.embeddings.store import OwnerType, RetrievedChunk, SourceMaterial


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.8g}" for v in vector) + "]"


class PgKnowledgeStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def has_source(self, course_id: int, sha256: str, model: str) -> bool:
        query = text(
            """
            SELECT count(c.id) AS chunks, count(e.id) AS vectors
            FROM source_documents s
            JOIN document_chunks c ON c.source_document_id = s.id AND c.active
            LEFT JOIN ai_embeddings e
              ON e.owner_type = 'chunk' AND e.owner_id = c.id AND e.model = :model AND e.active
            WHERE s.course_id = :course_id AND s.sha256 = :sha256 AND s.active
            """
        )
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    query, {"course_id": course_id, "sha256": sha256, "model": model}
                )
            ).one()
        return bool(row.chunks) and row.chunks == row.vectors

    async def save_source(
        self,
        course_id: int,
        material: SourceMaterial,
        sha256: str,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        model: str,
    ) -> int:
        async with self._engine.begin() as conn:
            source_id = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO source_documents (course_id, title, url, license, sha256)
                        VALUES (:course_id, :title, :url, :license, :sha256)
                        ON CONFLICT (course_id, sha256) DO UPDATE SET active = true
                        RETURNING id
                        """
                    ),
                    {
                        "course_id": course_id,
                        "title": material.title[:500],
                        "url": material.url,
                        "license": material.license,
                        "sha256": sha256,
                    },
                )
            ).scalar_one()
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk_id = (
                    await conn.execute(
                        text(
                            """
                            INSERT INTO document_chunks
                              (source_document_id, chunk_index, text, token_count)
                            VALUES (:source_id, :idx, :text, :tokens)
                            ON CONFLICT (source_document_id, chunk_index)
                            DO UPDATE SET text = EXCLUDED.text, token_count = EXCLUDED.token_count
                            RETURNING id
                            """
                        ),
                        {
                            "source_id": source_id,
                            "idx": chunk.index,
                            "text": chunk.text,
                            "tokens": chunk.token_count,
                        },
                    )
                ).scalar_one()
                await self._upsert_vector(
                    conn, "chunk", chunk_id, model, vector, sha256_text(chunk.text)
                )
        return int(source_id)

    @staticmethod
    async def _upsert_vector(
        conn: AsyncConnection,
        owner_type: OwnerType,
        owner_id: int,
        model: str,
        vector: Sequence[float],
        content_sha256: str,
    ) -> None:
        await conn.execute(
            text(
                """
                INSERT INTO ai_embeddings (owner_type, owner_id, model, embedding, content_sha256)
                VALUES (:owner_type, :owner_id, :model, CAST(:embedding AS vector), :sha)
                ON CONFLICT (owner_type, owner_id, model)
                DO UPDATE SET embedding = EXCLUDED.embedding,
                              content_sha256 = EXCLUDED.content_sha256, active = true
                """
            ),
            {
                "owner_type": owner_type,
                "owner_id": owner_id,
                "model": model,
                "embedding": vector_literal(vector),
                "sha": content_sha256,
            },
        )

    async def search(
        self, course_id: int, vector: Sequence[float], model: str, k: int
    ) -> list[RetrievedChunk]:
        query = text(
            """
            SELECT c.id, c.source_document_id, c.chunk_index, c.text,
                   s.title, s.url, s.license,
                   1 - (e.embedding <=> CAST(:query AS vector)) AS score
            FROM ai_embeddings e
            JOIN document_chunks c ON e.owner_type = 'chunk' AND e.owner_id = c.id AND c.active
            JOIN source_documents s ON s.id = c.source_document_id AND s.active
            WHERE s.course_id = :course_id AND e.model = :model AND e.active
            ORDER BY e.embedding <=> CAST(:query AS vector), c.id
            LIMIT :k
            """
        )
        params = {
            "course_id": course_id,
            "model": model,
            "query": vector_literal(vector),
            "k": k,
        }
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query, params)).all()
        return [_retrieved(r) for r in rows]

    async def chunks_by_ids(self, chunk_ids: Sequence[str]) -> list[RetrievedChunk]:
        ids = [int(i) for i in chunk_ids if i.isdigit()]
        if not ids:
            return []
        query = text(
            """
            SELECT c.id, c.source_document_id, c.chunk_index, c.text,
                   s.title, s.url, s.license, 1.0 AS score
            FROM document_chunks c
            JOIN source_documents s ON s.id = c.source_document_id
            WHERE c.id = ANY(:ids)
            """
        )
        async with self._engine.connect() as conn:
            rows = {r.id: r for r in (await conn.execute(query, {"ids": ids})).all()}
        return [_retrieved(rows[int(i)]) for i in chunk_ids if i.isdigit() and int(i) in rows]

    async def vector_sha(self, owner_type: OwnerType, owner_id: int, model: str) -> str | None:
        query = text(
            """
            SELECT content_sha256 FROM ai_embeddings
            WHERE owner_type = :owner_type AND owner_id = :owner_id AND model = :model AND active
            """
        )
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    query, {"owner_type": owner_type, "owner_id": owner_id, "model": model}
                )
            ).first()
        return None if row is None else str(row.content_sha256)

    async def save_vector(
        self,
        owner_type: OwnerType,
        owner_id: int,
        model: str,
        vector: Sequence[float],
        content_sha256: str,
    ) -> None:
        async with self._engine.begin() as conn:
            await self._upsert_vector(conn, owner_type, owner_id, model, vector, content_sha256)


def _retrieved(row: Row[Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(row.id),
        source_document_id=int(row.source_document_id),
        chunk_index=int(row.chunk_index),
        text=str(row.text),
        title=str(row.title),
        url=row.url,
        license=row.license,
        score=float(row.score),
    )
