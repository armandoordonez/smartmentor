"""Notes and readings uploaded by the instructor as RAG sources (R-004), read from
``course_materials`` (ADR 0009: the API writes the table, ``smartmentor_ai`` only reads it,
changeset ``v2.0.1-008``).

Every active material with text is a source, oldest first. Its ``origin`` becomes the license that
``source_documents`` records (DEF-08). The indexer is idempotent by content hash, so a material
uploaded after the course was published is indexed the next time an explanation is generated.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.embeddings.store import SourceMaterial

# Texts shown to the learner next to each citation, in the language of the interface.
ORIGIN_LICENSES = {
    "own_notes": "Apuntes propios del instructor",
    "open_license": "Libro o material de licencia abierta",
    "permitted": "Material con permiso de uso",
}
DEFAULT_LICENSE = "Material del curso (aportado por el instructor)"

_ACTIVE_MATERIALS = """
    SELECT id, file_name, origin, extracted_text
    FROM course_materials
    WHERE course_id = :course_id AND active AND length(btrim(coalesce(extracted_text, ''))) > 0
    ORDER BY created_at, id
"""


def material_source(row: Mapping[Any, Any]) -> SourceMaterial:
    """One row of ``course_materials`` as a source of the RAG."""
    name = (row["file_name"] or "").strip()
    title = f"Apuntes del curso ({name})" if name else f"Apuntes del curso #{row['id']}"
    return SourceMaterial(
        title=title[:500],
        text=row["extracted_text"],
        license=ORIGIN_LICENSES.get(row["origin"], DEFAULT_LICENSE),
    )


class PostgresCourseMaterialReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def sources(self, course_id: int) -> list[SourceMaterial]:
        async with self._engine.connect() as conn:
            rows = (
                (await conn.execute(text(_ACTIVE_MATERIALS), {"course_id": course_id}))
                .mappings()
                .all()
            )
        return [material_source(row) for row in rows]
