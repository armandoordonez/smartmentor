"""The course syllabus as a RAG source (DEF-08), read from ``syllabus_documents`` (ADR 0009).

Until instructors can upload their notes, the text of the syllabus is the one source every course
has. Only the latest active syllabus with text counts: an older upload would ground the
explanations on a syllabus the instructor already replaced. ``smartmentor_ai`` can read the table
(changeset ``045``).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.embeddings.store import SourceMaterial

SYLLABUS_LICENSE = "Syllabus del curso (aportado por el instructor)"

_LATEST_SYLLABUS = """
    SELECT file_name, extracted_text
    FROM syllabus_documents
    WHERE course_id = :course_id AND active AND length(btrim(coalesce(extracted_text, ''))) > 0
    ORDER BY created_at DESC, id DESC
    LIMIT 1
"""


class PostgresSyllabusSourceReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def sources(self, course_id: int) -> list[SourceMaterial]:
        async with self._engine.connect() as conn:
            row = (
                (await conn.execute(text(_LATEST_SYLLABUS), {"course_id": course_id}))
                .mappings()
                .first()
            )
        if row is None:
            return []
        name = (row["file_name"] or "").strip()
        title = f"Syllabus del curso ({name})" if name else "Syllabus del curso"
        return [
            SourceMaterial(title=title[:500], text=row["extracted_text"], license=SYLLABUS_LICENSE)
        ]
