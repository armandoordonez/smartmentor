"""Where the reference documents of a course come from (DEF-08).

The contract of ``embeddings.index_course`` only carries ``course_id``, so the documents are read
through a port. ``DirectorySourceReader`` reads ``<root>/<course_id>/sources.yaml`` (a list of
``{file, title, url, license}``) with the text files next to it; it serves local runs and the
evaluation harness until the owner decides where instructors upload their notes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

import yaml

from app.application.embeddings.store import SourceMaterial


class SourceMaterialReader(Protocol):
    async def sources(self, course_id: int) -> list[SourceMaterial]: ...


class InMemorySourceReader:
    def __init__(self, by_course: dict[int, list[SourceMaterial]] | None = None) -> None:
        self.by_course = by_course or {}

    async def sources(self, course_id: int) -> list[SourceMaterial]:
        return list(self.by_course.get(course_id, []))


class DirectorySourceReader:
    def __init__(self, root: Path, *, default_course: bool = False) -> None:
        """``default_course``: every course reads ``<root>/sources.yaml`` (evaluation)."""
        self._root = root
        self._default_course = default_course

    async def sources(self, course_id: int) -> list[SourceMaterial]:
        folder = self._root if self._default_course else self._root / str(course_id)
        index = folder / "sources.yaml"
        if not index.is_file():
            return []
        entries = cast(list[dict[str, Any]], yaml.safe_load(index.read_text(encoding="utf-8")))
        materials: list[SourceMaterial] = []
        for entry in entries or []:
            path = (folder / str(entry["file"])).resolve()
            if folder.resolve() not in path.parents:
                continue  # a file outside the folder is ignored
            materials.append(
                SourceMaterial(
                    title=str(entry["title"]),
                    text=path.read_text(encoding="utf-8"),
                    url=entry.get("url"),
                    license=entry.get("license"),
                )
            )
        return materials
