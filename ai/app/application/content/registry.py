"""Wiring of the content tasks: ``job_type`` -> handler (the extension point of ``container.py``).

``build_task_specs(deps)`` describes every task of the content, grading, video and badge modules
(job type, result contract, input model and function). ``build_job_handlers`` wraps them as
``JobHandler`` objects for ``JobService`` and the worker; the evaluation harness calls the
functions directly. ``items.review`` and the syllabus/diagnostic tasks belong to ``ai-base``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, RootModel

from app.application.badge.compose import BadgeTextInput, BadgeTextTask
from app.application.content.context import Handler, TaskContext, TaskResult
from app.application.content.course_generation import (
    GENERATE_CONTENT_CONTRACT,
    CourseContentOrchestrator,
    GenerateContentInput,
)
from app.application.content.explain import (
    EXPLANATION_CONTRACT,
    ExplainTopicInput,
    ExplanationService,
    RemedialInput,
)
from app.application.content.faithfulness import (
    CheckFaithfulnessInput,
    CheckFaithfulnessTask,
    FaithfulnessChecker,
)
from app.application.content.personal_example import PersonalExampleInput, PersonalExampleTask
from app.application.embeddings.indexer import CourseIndexer
from app.application.embeddings.retrieval import Retriever
from app.application.embeddings.sources import SourceMaterialReader
from app.application.embeddings.store import KnowledgeStore
from app.application.grading.short_answer import (
    GradeInput,
    GradeShortAnswerTask,
    GradingService,
)
from app.application.items.banks import FinalBankInput, FinalBankTask, QuizBankInput, QuizBankTask
from app.application.items.review import BANK_CONTRACT, ItemReviewer
from app.application.jobs import JobContext, JobHandler
from app.application.llm_runner import EmbeddingRunner, LlmRunner
from app.application.video.service import (
    CollectCandidatesTask,
    CollectInput,
    RankInput,
    RankTask,
    VideoRecommender,
)
from app.ports.catalog import CatalogReader
from app.ports.jobs import JobRepository
from app.ports.video import TranscriptProvider, VideoSearchProvider

INDEX_CONTRACT = "embeddings_index.v1"


class IndexCourseInput(BaseModel):
    course_id: int


@dataclass(frozen=True)
class ContentDeps:
    runner: LlmRunner
    embeddings: EmbeddingRunner
    catalog: CatalogReader
    knowledge: KnowledgeStore
    sources: SourceMaterialReader
    jobs: JobRepository
    transcripts: TranscriptProvider
    clock: Callable[[], datetime]
    video_search: VideoSearchProvider | None = None  # None: no YOUTUBE_API_KEY (L-08)
    include_diagnostic: bool = False


@dataclass(frozen=True)
class TaskSpec:
    job_type: str
    contract: str
    input_model: type[BaseModel]
    run: Handler


class RawResult(RootModel[dict[str, Any]]):
    """A result already validated against its contract by the task."""


class ContentJobHandler(JobHandler[Any]):
    """Adapts a ``TaskSpec`` to the ``JobHandler`` interface of ``JobService``."""

    def __init__(self, spec: TaskSpec) -> None:
        self.job_type = spec.job_type
        self.contract = spec.contract
        self.input_model = spec.input_model
        self._run = spec.run

    async def run(self, payload: BaseModel, ctx: JobContext) -> BaseModel:
        # The job id seeds the keys of the child jobs of ``course.generate_content``, so a retry
        # of the same job does not duplicate them.
        task_ctx = TaskContext(job_id=ctx.job_id, idempotency_key=str(ctx.job_id), refs=ctx.refs)
        result = await self._run(payload.model_dump(mode="json"), task_ctx)
        return RawResult(result.result)


@dataclass(frozen=True)
class ContentServices:
    specs: dict[str, TaskSpec]
    recommender: VideoRecommender


def build_content_services(deps: ContentDeps) -> ContentServices:
    indexer = CourseIndexer(
        catalog=deps.catalog,
        sources=deps.sources,
        knowledge=deps.knowledge,
        embeddings=deps.embeddings,
    )
    retriever = Retriever(indexer=indexer, knowledge=deps.knowledge, embeddings=deps.embeddings)
    checker = FaithfulnessChecker(deps.runner)
    explanations = ExplanationService(
        runner=deps.runner, retriever=retriever, checker=checker, catalog=deps.catalog
    )
    reviewer = ItemReviewer(deps.runner)
    recommender = VideoRecommender(
        catalog=deps.catalog,
        search=deps.video_search,
        transcripts=deps.transcripts,
        embeddings=deps.embeddings,
    )
    orchestrator = CourseContentOrchestrator(
        catalog=deps.catalog,
        jobs=deps.jobs,
        clock=deps.clock,
        include_diagnostic=deps.include_diagnostic,
    )

    async def index_course(raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = IndexCourseInput.model_validate(raw)
        report = await indexer.index_course(
            data.course_id, ctx.call("embeddings.index_course", course_id=data.course_id)
        )
        return TaskResult(
            INDEX_CONTRACT,
            {
                "topics_indexed": report.topics_indexed,
                "chunks_indexed": report.chunks_indexed,
                "embedding_model": report.embedding_model,
            },
        )

    specs = [
        TaskSpec("embeddings.index_course", INDEX_CONTRACT, IndexCourseInput, index_course),
        TaskSpec(
            "content.explain_topic",
            EXPLANATION_CONTRACT,
            ExplainTopicInput,
            explanations.explain_task,
        ),
        TaskSpec(
            "content.check_faithfulness",
            "faithfulness_check.v1",
            CheckFaithfulnessInput,
            CheckFaithfulnessTask(checker, deps.knowledge).run,
        ),
        TaskSpec(
            "content.remedial", EXPLANATION_CONTRACT, RemedialInput, explanations.remedial_task
        ),
        TaskSpec(
            "content.personal_example",
            "personalized_example.v1",
            PersonalExampleInput,
            PersonalExampleTask(runner=deps.runner, catalog=deps.catalog).run,
        ),
        TaskSpec(
            "items.generate_quiz_bank",
            BANK_CONTRACT,
            QuizBankInput,
            QuizBankTask(runner=deps.runner, reviewer=reviewer, catalog=deps.catalog).run,
        ),
        TaskSpec(
            "items.generate_final_bank",
            BANK_CONTRACT,
            FinalBankInput,
            FinalBankTask(runner=deps.runner, reviewer=reviewer, catalog=deps.catalog).run,
        ),
        TaskSpec(
            "grading.short_answer",
            "grading.v1",
            GradeInput,
            GradeShortAnswerTask(GradingService(deps.runner)).run,
        ),
        TaskSpec(
            "video.collect_candidates",
            "video_resource.v1",
            CollectInput,
            CollectCandidatesTask(recommender, deps.catalog).run,
        ),
        TaskSpec("video.rank", "video_resource.v1", RankInput, RankTask(recommender).run),
        TaskSpec(
            "badge.compose_text", "badge_text.v1", BadgeTextInput, BadgeTextTask(deps.runner).run
        ),
        TaskSpec(
            "course.generate_content",
            GENERATE_CONTENT_CONTRACT,
            GenerateContentInput,
            orchestrator.run,
        ),
    ]
    return ContentServices({s.job_type: s for s in specs}, recommender)


def build_job_handlers(services: ContentServices) -> list[JobHandler[Any]]:
    """Handlers for ``JobService``: every task except ``video.rank`` (synchronous, HTTP route)."""
    return [ContentJobHandler(s) for t, s in services.specs.items() if t != "video.rank"]
