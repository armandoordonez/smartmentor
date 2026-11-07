"""What every content task receives and returns, and helpers shared by the task packages.

The worker (``ai-base``) calls ``handler(input, TaskContext) -> TaskResult``; the registry in
``registry.py`` maps each ``job_type`` to its handler. Handlers parse their own ``input`` with the
Pydantic models next to them, so the HTTP layer can validate a job with the same models.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.application.embeddings.store import RetrievedChunk
from app.application.llm_runner import CallContext
from app.domain.contracts.content import CitedSource
from app.domain.errors import InputReferenceNotFoundError
from app.ports.budget import BudgetScope
from app.ports.catalog import CatalogReader, TopicRecord
from app.ports.jobs import JobRefs, RequestedBy


@dataclass(frozen=True)
class TaskContext:
    """Identity of the running job: its id, its key and the refs used for the budget."""

    job_id: UUID | None = None
    idempotency_key: str = ""
    refs: JobRefs = field(default_factory=JobRefs)
    requested_by: RequestedBy = "api"

    @property
    def scope(self) -> BudgetScope:
        return BudgetScope(course_id=self.refs.course_id, enrollment_id=self.refs.enrollment_id)

    def call(self, task: str, *, course_id: int | None = None) -> CallContext:
        scope = self.scope
        if course_id is not None and scope.course_id is None:
            scope = BudgetScope(course_id=course_id, enrollment_id=scope.enrollment_id)
        return CallContext(task=task, job_id=self.job_id, scope=scope)


@dataclass(frozen=True)
class TaskResult:
    """A validated result: ``contract`` names the schema (``topic_explanation.v1``)."""

    contract: str
    result: dict[str, Any]


Handler = Callable[[dict[str, Any], TaskContext], Awaitable[TaskResult]]


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def topic_payload(topic: TopicRecord) -> dict[str, Any]:
    """The topic as the prompts receive it (JSON): name, subtopics and learning outcomes."""
    return {
        "topic_id": topic.id,
        "name": topic.name,
        "description": topic.description,
        "subtopics": topic.subtopics,
        "learning_outcomes": [
            {"id": o.id, "statement": o.statement, "bloom_level": o.bloom_level}
            for o in topic.outcomes
        ],
    }


def fragments_block(chunks: Sequence[RetrievedChunk]) -> str:
    """Numbered fragments ``[n] text`` (the numbers are the citations of the explanation)."""
    return "\n\n".join(f"[{n}] {c.text}" for n, c in enumerate(chunks, start=1))


def cited_sources(chunks: Sequence[RetrievedChunk]) -> list[CitedSource]:
    return [
        CitedSource(n=n, source_id=c.chunk_id, title=c.title, url=c.url or "", license=c.license)
        for n, c in enumerate(chunks, start=1)
    ]


async def load_topic(catalog: CatalogReader, topic_id: str) -> TopicRecord:
    found = await catalog.topics([topic_id])
    if not found:
        raise InputReferenceNotFoundError(f"topic {topic_id} does not exist")
    return found[0]


async def load_topics(catalog: CatalogReader, topic_ids: Sequence[str]) -> list[TopicRecord]:
    """The topics in the order asked; any unknown id ends the job."""
    found = {t.id: t for t in await catalog.topics(list(topic_ids))}
    if missing := [t for t in topic_ids if t not in found]:
        raise InputReferenceNotFoundError(f"topics {missing} do not exist")
    return [found[t] for t in topic_ids]
