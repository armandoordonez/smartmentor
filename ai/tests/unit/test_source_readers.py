"""Source readers of the RAG (DEF-08): the folder and the combination with the syllabus."""

from __future__ import annotations

from pathlib import Path

from app.application.embeddings.sources import (
    CombinedSourceReader,
    DirectorySourceReader,
    InMemorySourceReader,
)
from app.application.embeddings.store import SourceMaterial

SYLLABUS = SourceMaterial(title="Syllabus del curso", text="Tema 1. Bases de datos.")
NOTES = SourceMaterial(title="Apuntes", text="Normalización y modelos.", license="CC BY 4.0")


async def test_combined_reader_keeps_the_order_of_its_readers() -> None:
    reader = CombinedSourceReader(
        InMemorySourceReader({7: [SYLLABUS]}), InMemorySourceReader({7: [NOTES]})
    )
    assert await reader.sources(7) == [SYLLABUS, NOTES]


async def test_combined_reader_without_sources_is_empty() -> None:
    reader = CombinedSourceReader(InMemorySourceReader(), InMemorySourceReader())
    assert await reader.sources(7) == []


async def test_combined_reader_works_when_the_folder_is_missing(tmp_path: Path) -> None:
    reader = CombinedSourceReader(
        InMemorySourceReader({7: [SYLLABUS]}), DirectorySourceReader(tmp_path / "no-existe")
    )
    assert await reader.sources(7) == [SYLLABUS]
