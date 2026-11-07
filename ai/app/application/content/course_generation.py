"""``course.generate_content``: orchestrates the content jobs of an approved course (D2).

It does not call the LLM itself: it enqueues one job per task and topic (idempotent keys derived
from its own key, so running it twice does not duplicate work) and returns their ids. The API
follows each job like any other. Order does not matter: ``content.explain_topic`` indexes the
sources by itself when needed, so ``embeddings.index_course`` is only a warm-up.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.application.content.context import TaskContext, TaskResult
from app.application.items.banks import DEFAULT_QUIZ_ITEMS, quiz_split
from app.domain.errors import InputReferenceNotFoundError
from app.ports.catalog import CatalogReader
from app.ports.jobs import JobRefs, JobRepository, NewJob

GENERATE_CONTENT_CONTRACT = "generate_content_jobs.v1"
FINAL_SHORT_ANSWERS = 2
MAX_KEY_CHARS = 200


class GenerateContentInput(BaseModel):
    course_id: int
    learning_path_id: int
    quiz_items_per_topic: int = Field(default=DEFAULT_QUIZ_ITEMS, ge=1, le=40)
    final_versions: int = Field(default=2, ge=1, le=4)


class CourseContentOrchestrator:
    job_type = "course.generate_content"

    def __init__(
        self,
        *,
        catalog: CatalogReader,
        jobs: JobRepository,
        clock: Callable[[], datetime],
        include_diagnostic: bool = False,
    ) -> None:
        """``include_diagnostic``: also enqueue ``diagnostic.generate_items`` (off by default:
        the API enqueues it by itself, and its handler belongs to the diagnostic module)."""
        self._catalog = catalog
        self._jobs = jobs
        self._clock = clock
        self._include_diagnostic = include_diagnostic

    @staticmethod
    def _tag(ctx: TaskContext) -> str:
        seed = ctx.idempotency_key or (str(ctx.job_id) if ctx.job_id else "local")
        return "gc" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = GenerateContentInput.model_validate(raw)
        topics = await self._catalog.course_topics(data.course_id)
        if not topics:
            raise InputReferenceNotFoundError(f"course {data.course_id} has no topics")
        tag = self._tag(ctx)
        n_mc, n_sa = quiz_split(data.quiz_items_per_topic)
        created: list[dict[str, Any]] = []

        async def enqueue(
            job_type: str,
            entity: str,
            entity_id: str,
            payload: dict[str, Any],
            topic_id: str | None,
        ) -> None:
            key = f"{job_type}:{entity}:{entity_id}:{tag}"[:MAX_KEY_CHARS]
            refs = JobRefs(
                course_id=data.course_id,
                topic_id=int(topic_id) if topic_id and topic_id.isdigit() else None,
            )
            job, _ = await self._jobs.create_or_get(
                NewJob(
                    job_type=job_type,
                    idempotency_key=key,
                    input=payload,
                    refs=refs,
                    requested_by=ctx.requested_by,
                ),
                self._clock(),
            )
            created.append({"job_id": str(job.id), "job_type": job_type, "topic_id": topic_id})

        await enqueue(
            "embeddings.index_course",
            "course",
            str(data.course_id),
            {"course_id": data.course_id},
            None,
        )
        if self._include_diagnostic:
            await enqueue(
                "diagnostic.generate_items",
                "course",
                str(data.course_id),
                {"course_id": data.course_id},
                None,
            )
        for topic in topics:
            await enqueue(
                "content.explain_topic", "topic", topic.id, {"topic_id": topic.id}, topic.id
            )
            await enqueue(
                "items.generate_quiz_bank",
                "topic",
                topic.id,
                {
                    "topic_id": topic.id,
                    "n_multiple_choice": n_mc,
                    "n_short_answer": n_sa,
                    "previous_stems": [],
                },
                topic.id,
            )
            await enqueue(
                "video.collect_candidates",
                "topic",
                topic.id,
                {"topic_id": topic.id, "language": "es", "instructor_videos": []},
                topic.id,
            )
        await enqueue(
            "items.generate_final_bank",
            "path",
            str(data.learning_path_id),
            {
                "learning_path_id": data.learning_path_id,
                "topic_ids": [t.id for t in topics],
                "n_short_answer": FINAL_SHORT_ANSWERS,
                "n_versions": data.final_versions,
                "previous_stems": [],
            },
            None,
        )
        return TaskResult(GENERATE_CONTENT_CONTRACT, {"jobs": created})
