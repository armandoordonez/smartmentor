"""Wiring of the content tasks: ``job_type`` -> handler (the extension point for the worker).

``build_content_handlers(deps)`` returns every task of the content, evaluation and video modules
(plus ``items.review`` and ``video.rank``, which the HTTP service can also run synchronously).
The worker looks a job up by ``job_type`` and calls ``handler(job.input, TaskContext(...))``; the
``TaskResult`` carries the contract name and the validated result to store with ``succeed``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.badge.compose import BadgeTextTask
from app.application.content.context import Handler, TaskContext, TaskResult
from app.application.content.course_generation import CourseContentOrchestrator
from app.application.content.explain import ExplanationService
from app.application.content.faithfulness import CheckFaithfulnessTask, FaithfulnessChecker
from app.application.content.personal_example import PersonalExampleTask
from app.application.embeddings.indexer import CourseIndexer
from app.application.embeddings.retrieval import Retriever
from app.application.embeddings.sources import SourceMaterialReader
from app.application.embeddings.store import KnowledgeStore
from app.application.grading.short_answer import GradeShortAnswerTask, GradingService
from app.application.items.banks import FinalBankTask, QuizBankTask
from app.application.items.review import ItemReviewer, ReviewTask
from app.application.llm_runner import EmbeddingRunner, LlmRunner
from app.application.video.service import CollectCandidatesTask, RankTask, VideoRecommender
from app.ports.catalog import CatalogReader
from app.ports.jobs import JobRepository
from app.ports.video import TranscriptProvider, VideoSearchProvider


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


def build_indexing_handler(indexer: CourseIndexer, embeddings: EmbeddingRunner) -> Handler:
    async def handler(raw: dict[str, object], ctx: TaskContext) -> TaskResult:
        course_id = raw.get("course_id")
        if not isinstance(course_id, int) or isinstance(course_id, bool):
            raise ValueError("course_id must be an integer")
        report = await indexer.index_course(
            course_id, ctx.call("embeddings.index_course", course_id=course_id)
        )
        return TaskResult(
            "embeddings_index.v1",
            {
                "topics_indexed": report.topics_indexed,
                "chunks_indexed": report.chunks_indexed,
                "embedding_model": embeddings.model,
            },
        )

    return handler


def build_content_handlers(deps: ContentDeps) -> dict[str, Handler]:
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
    return {
        "embeddings.index_course": build_indexing_handler(indexer, deps.embeddings),
        "content.explain_topic": explanations.explain_task,
        "content.check_faithfulness": CheckFaithfulnessTask(checker, deps.knowledge).run,
        "content.remedial": explanations.remedial_task,
        "content.personal_example": PersonalExampleTask(
            runner=deps.runner, catalog=deps.catalog
        ).run,
        "items.generate_quiz_bank": QuizBankTask(
            runner=deps.runner, reviewer=reviewer, catalog=deps.catalog
        ).run,
        "items.generate_final_bank": FinalBankTask(
            runner=deps.runner, reviewer=reviewer, catalog=deps.catalog
        ).run,
        "items.review": ReviewTask(reviewer).run,
        "grading.short_answer": GradeShortAnswerTask(GradingService(deps.runner)).run,
        "video.collect_candidates": CollectCandidatesTask(recommender, deps.catalog).run,
        "video.rank": RankTask(recommender).run,
        "badge.compose_text": BadgeTextTask(deps.runner).run,
        "course.generate_content": orchestrator.run,
    }
