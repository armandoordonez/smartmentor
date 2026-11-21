"""``syllabus.structure``: syllabus text -> ``syllabus.v1`` (prompt ``syllabus_structuring``)."""

from __future__ import annotations

from pydantic import Field

from app.application.jobs import JobContext, JobHandler
from app.application.llm_runner import LlmRunner
from app.domain.contracts.common import ContractModel
from app.domain.contracts.syllabus import Syllabus, SyllabusLLM, syllabus_from_llm
from app.domain.contracts.validation import check_syllabus
from app.domain.errors import InputReferenceNotFoundError, TaskError
from app.ports.catalog import CatalogReader


class SyllabusStructureInput(ContractModel):
    syllabus_document_id: int = Field(ge=1)


def _check(syllabus: SyllabusLLM) -> list[str]:
    # An empty syllabus is a valid answer ("no topics found"), handled after the call.
    return check_syllabus(syllabus) if syllabus.topics else []


class SyllabusStructureHandler(JobHandler[SyllabusStructureInput]):
    job_type = "syllabus.structure"
    contract = "syllabus.v1"
    input_model = SyllabusStructureInput

    def __init__(self, runner: LlmRunner, catalog: CatalogReader) -> None:
        self._runner = runner
        self._catalog = catalog

    async def run(self, payload: SyllabusStructureInput, ctx: JobContext) -> Syllabus:
        document = await self._catalog.syllabus_document(payload.syllabus_document_id)
        if document is None:
            raise InputReferenceNotFoundError(
                f"syllabus document {payload.syllabus_document_id} does not exist"
            )
        if not document.text.strip():
            raise TaskError("SYLLABUS_NO_TOPICS", "the syllabus document has no text")
        llm, meta = await self._runner.run(
            "syllabus_structuring",
            {"syllabus": document.text},
            SyllabusLLM,
            ctx.call(),
            check=_check,
        )
        if not llm.topics:
            raise TaskError("SYLLABUS_NO_TOPICS", "the model found no topics in the syllabus")
        try:
            return syllabus_from_llm(llm, meta)
        except ValueError as exc:
            raise TaskError("INVALID_OUTPUT", f"syllabus contract: {exc}") from exc
