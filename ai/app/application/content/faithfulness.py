"""``content.check_faithfulness``: claim-by-claim verification of a text against its fragments."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from app.application.content.context import TaskContext, TaskResult, fragments_block
from app.application.embeddings.store import KnowledgeStore, RetrievedChunk
from app.application.llm_runner import CallContext, LlmRunner
from app.domain.contracts.content import (
    FaithfulnessCheck,
    FaithfulnessCheckLLM,
    faithfulness_from_llm,
)
from app.domain.contracts.validation import check_faithfulness
from app.domain.errors import InputReferenceNotFoundError

FAITHFULNESS_CONTRACT = "faithfulness_check.v1"


class CheckFaithfulnessInput(BaseModel):
    topic_id: str
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1, description="Ids of the fragments (chunks)")


class FaithfulnessChecker:
    """Runs ``rag_faithfulness`` (temperature 0) and builds the ``faithfulness_check`` contract."""

    def __init__(self, runner: LlmRunner) -> None:
        self._runner = runner

    async def check(
        self,
        text: str,
        chunks: Sequence[RetrievedChunk],
        ctx: CallContext,
        *,
        use_cache: bool = True,
    ) -> FaithfulnessCheck:
        """``use_cache=False`` for personal texts (the remedial explanation)."""
        llm, meta = await self._runner.run(
            "rag_faithfulness",
            {"text": text, "fragments": fragments_block(chunks)},
            FaithfulnessCheckLLM,
            ctx,
            check=lambda out: check_faithfulness(out, len(chunks)),
            use_cache=use_cache,
        )
        return faithfulness_from_llm(llm, meta)


class CheckFaithfulnessTask:
    job_type = "content.check_faithfulness"

    def __init__(self, checker: FaithfulnessChecker, knowledge: KnowledgeStore) -> None:
        self._checker = checker
        self._knowledge = knowledge

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = CheckFaithfulnessInput.model_validate(raw)
        chunks = await self._knowledge.chunks_by_ids(data.source_ids)
        if len(chunks) != len(data.source_ids):
            raise InputReferenceNotFoundError("some source fragments do not exist")
        check = await self._checker.check(data.text, chunks, ctx.call(self.job_type))
        return TaskResult(FAITHFULNESS_CONTRACT, check.model_dump(mode="json"))
