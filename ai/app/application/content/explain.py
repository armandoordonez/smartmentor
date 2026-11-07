"""``content.explain_topic`` (shared by every learner) and ``content.remedial`` (personal).

Both retrieve the top-k fragments of the topic, ask for an explanation with ``[n]`` citations,
validate that the citations stay within the fragments and then verify the claims against the
fragments (``FaithfulnessChecker``). The main explanation carries no learner data (L-01) and is
cached by topic; the remedial one is built per enrollment and attempt and is never cached.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.application.content.context import (
    TaskContext,
    TaskResult,
    cited_sources,
    fragments_block,
    load_topic,
    to_json,
    topic_payload,
)
from app.application.content.faithfulness import FaithfulnessChecker
from app.application.content.privacy import pseudonymize_profile, pseudonymize_value
from app.application.embeddings.retrieval import Retriever
from app.application.embeddings.store import RetrievedChunk
from app.application.llm_runner import LlmRunner
from app.domain.contracts.common import Meta
from app.domain.contracts.content import Section, TopicExplanation, TopicExplanationLLM
from app.domain.contracts.validation import check_explanation, uncited_sections
from app.ports.catalog import CatalogReader, TopicRecord

logger = logging.getLogger("app.content")

EXPLANATION_CONTRACT = "topic_explanation.v1"
MAX_FAILED_ITEMS = 10
MAX_ANSWER_CHARS = 600


class ExplainTopicInput(BaseModel):
    topic_id: str


class FailedItem(BaseModel):
    stem: str
    learner_answer: str = ""


class RemedialInput(BaseModel):
    topic_id: str
    level: float = Field(ge=0, le=100)
    profile_text: str = ""
    failed_items: list[FailedItem] = Field(default_factory=list, max_length=MAX_FAILED_ITEMS)


class ExplanationService:
    def __init__(
        self,
        *,
        runner: LlmRunner,
        retriever: Retriever,
        checker: FaithfulnessChecker,
        catalog: CatalogReader,
    ) -> None:
        self._runner = runner
        self._retriever = retriever
        self._checker = checker
        self._catalog = catalog

    async def _finish(
        self,
        *,
        kind: Literal["main", "remedial"],
        topic: TopicRecord,
        llm: TopicExplanationLLM,
        meta: Meta,
        chunks: list[RetrievedChunk],
        ctx: TaskContext,
        task: str,
    ) -> TopicExplanation:
        if uncited := uncited_sections(llm):
            logger.info("sections without citation", extra={"task": task, "sections": uncited})
        sections = [Section(heading=s.heading, body=s.body) for s in llm.sections]
        draft = TopicExplanation(
            topic_id=topic.id,
            kind=kind,
            audience="all_learners" if kind == "main" else "enrollment",
            title=llm.title,
            sections=sections,
            worked_example=llm.worked_example,
            summary=llm.summary,
            reflection_questions=llm.reflection_questions,
            gaps_detected=llm.gaps_detected,
            sources=cited_sources(chunks),
            meta=meta,
        )
        check = await self._checker.check(
            draft.full_text(),
            chunks,
            ctx.call(task, course_id=topic.course_id),
            use_cache=kind == "main",
        )
        return draft.model_copy(
            update={
                "faithfulness": check.faithfulness,
                "unsupported_claims": check.unsupported_claims,
            }
        )

    async def explain(self, topic_id: str, ctx: TaskContext) -> TopicExplanation:
        task = "content.explain_topic"
        topic = await load_topic(self._catalog, topic_id)
        call = ctx.call(task, course_id=topic.course_id)
        chunks = await self._retriever.retrieve(topic, call)
        llm, meta = await self._runner.run(
            "topic_explanation",
            {"topic": to_json(topic_payload(topic)), "fragments": fragments_block(chunks)},
            TopicExplanationLLM,
            call,
            check=lambda out: check_explanation(out, len(chunks), kind="main"),
        )
        return await self._finish(
            kind="main", topic=topic, llm=llm, meta=meta, chunks=chunks, ctx=ctx, task=task
        )

    async def remedial(self, data: RemedialInput, ctx: TaskContext) -> TopicExplanation:
        task = "content.remedial"
        topic = await load_topic(self._catalog, data.topic_id)
        call = ctx.call(task, course_id=topic.course_id)
        errors = [
            pseudonymize_value(
                {"stem": f.stem, "learner_answer": f.learner_answer[:MAX_ANSWER_CHARS]}
            )
            for f in data.failed_items
        ]
        stems = " ".join(f.stem for f in data.failed_items)
        chunks = await self._retriever.retrieve(topic, call, extra_query=stems)
        llm, meta = await self._runner.run(
            "remedial_explanation",
            {
                "topic": to_json(topic_payload(topic)),
                "profile": pseudonymize_profile(data.profile_text),
                "errors": to_json(errors),
                "fragments": fragments_block(chunks),
                "level": round(data.level, 1),
            },
            TopicExplanationLLM,
            call,
            check=lambda out: check_explanation(out, len(chunks), kind="remedial"),
            use_cache=False,
        )
        return await self._finish(
            kind="remedial", topic=topic, llm=llm, meta=meta, chunks=chunks, ctx=ctx, task=task
        )

    async def explain_task(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = ExplainTopicInput.model_validate(raw)
        explanation = await self.explain(data.topic_id, ctx)
        return TaskResult(EXPLANATION_CONTRACT, explanation.model_dump(mode="json"))

    async def remedial_task(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        explanation = await self.remedial(RemedialInput.model_validate(raw), ctx)
        return TaskResult(EXPLANATION_CONTRACT, explanation.model_dump(mode="json"))
