"""``CatalogReader`` port: what ``ai/`` reads from the business tables (ADR 0009).

``smartmentor_ai`` may only read ``courses``, ``topics``, ``learning_outcomes`` and
``syllabus_documents``. Ids leave this port as opaque strings (``"12"``), as the contracts use
them (``docs/contracts/ai-service-v1.md``, section 1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class OutcomeRecord:
    id: str
    statement: str
    bloom_level: str | None = None


@dataclass(frozen=True)
class TopicRecord:
    id: str
    course_id: int
    name: str
    description: str
    subtopics: list[str] = field(default_factory=list)
    position: int = 0
    outcomes: list[OutcomeRecord] = field(default_factory=list)

    def similarity_text(self) -> str:
        """Text embedded for the profile and resume signals (as the notebook v2)."""
        subtopics = ", ".join(self.subtopics)
        return f"{self.name}. {self.description} Subtemas: {subtopics}."


@dataclass(frozen=True)
class SyllabusDocumentRecord:
    id: int
    course_id: int
    text: str


class CatalogReader(Protocol):
    async def syllabus_document(self, document_id: int) -> SyllabusDocumentRecord | None: ...

    async def course_topics(self, course_id: int) -> list[TopicRecord]:
        """Topics of a course in syllabus order, with their learning outcomes."""
        ...

    async def topics(self, topic_ids: Sequence[str]) -> list[TopicRecord]:
        """The given topics (unknown ids are left out; the caller reports them)."""
        ...
