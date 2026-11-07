"""Read-only access to ``syllabus_documents``, ``topics`` and ``learning_outcomes`` (ADR 0009).

Database ids leave as strings (the contracts treat ids as opaque text).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.ports.catalog import OutcomeRecord, SyllabusDocumentRecord, TopicRecord

_TOPICS = """
    SELECT id, course_id, name, coalesce(description, '') AS description, subtopics, position
    FROM topics
    WHERE active AND review_status <> 'deleted'
"""


def _list(value: Any) -> list[str]:
    data = json.loads(value) if isinstance(value, str) else value
    return [str(v) for v in data] if isinstance(data, list) else []


class PostgresCatalogReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def syllabus_document(self, document_id: int) -> SyllabusDocumentRecord | None:
        async with self._engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT id, course_id, coalesce(extracted_text, '') AS text
                        FROM syllabus_documents WHERE id = :id AND active
                        """
                        ),
                        {"id": document_id},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return SyllabusDocumentRecord(id=row["id"], course_id=row["course_id"], text=row["text"])

    async def _with_outcomes(self, rows: Sequence[Any]) -> list[TopicRecord]:
        ids = [r["id"] for r in rows]
        outcomes: dict[int, list[OutcomeRecord]] = {i: [] for i in ids}
        if ids:
            async with self._engine.connect() as conn:
                found = (
                    (
                        await conn.execute(
                            text(
                                """
                            SELECT id, topic_id, statement, bloom_level FROM learning_outcomes
                            WHERE active AND topic_id = ANY(:ids) ORDER BY topic_id, code, id
                            """
                            ),
                            {"ids": ids},
                        )
                    )
                    .mappings()
                    .all()
                )
            for o in found:
                outcomes[o["topic_id"]].append(
                    OutcomeRecord(
                        id=str(o["id"]), statement=o["statement"], bloom_level=o["bloom_level"]
                    )
                )
        return [
            TopicRecord(
                id=str(r["id"]),
                course_id=r["course_id"],
                name=r["name"],
                description=r["description"],
                subtopics=_list(r["subtopics"]),
                position=r["position"],
                outcomes=outcomes[r["id"]],
            )
            for r in rows
        ]

    async def course_topics(self, course_id: int) -> list[TopicRecord]:
        async with self._engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(_TOPICS + " AND course_id = :course_id ORDER BY position, id"),
                        {"course_id": course_id},
                    )
                )
                .mappings()
                .all()
            )
        return await self._with_outcomes(rows)

    async def topics(self, topic_ids: Sequence[str]) -> list[TopicRecord]:
        ids = [int(t) for t in topic_ids if t.isdigit()]
        if not ids:
            return []
        async with self._engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(_TOPICS + " AND id = ANY(:ids) ORDER BY position, id"), {"ids": ids}
                    )
                )
                .mappings()
                .all()
            )
        return await self._with_outcomes(rows)


async def ping(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
