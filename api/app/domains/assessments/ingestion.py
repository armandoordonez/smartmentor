"""Ingestores de los trabajos de `ai/` que escriben en evaluaciones (modelo pull, ADR 0010).

Cada uno valida el resultado contra su contrato y delega en el servicio, que bloquea la fila de la
inscripción y comprueba que el trabajo siga siendo el vigente: ingerir dos veces no duplica nada.
"""

from pydantic import BaseModel

from app.domains.ai_gateway.entities import JobRefs, JobStatus, PendingJob
from app.domains.assessments.contracts import (
    AssessmentItemBankV1,
    DiagnosticFinalizationV1,
    GradingV1,
)
from app.domains.assessments.service import (
    DIAGNOSTIC_FINALIZE,
    GRADING_SHORT_ANSWER,
    QUIZ_BANK,
    AttemptService,
    DiagnosticService,
)
from app.domains.identity.authentication import CurrentUser


class DiagnosticFinalizeIngestor:
    """`diagnostic.finalize` → niveles por tema y objetivo propuesto (U1a → E4)."""

    job_type = DIAGNOSTIC_FINALIZE
    result_model: type[BaseModel] = DiagnosticFinalizationV1
    progress_label = "Calculando tu nivel por tema"

    def __init__(self, service: DiagnosticService) -> None:
        self._service = service

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        return await self._service.can_see(refs.enrollment_id, user)

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        return await self._service.ingest_finalization(job, result)

    async def on_failed(self, job: JobStatus, error_code: str) -> None:  # noqa: ARG002
        await self._service.finalization_failed(job)

    async def pending_jobs(self) -> list[PendingJob]:
        return await self._service.pending_finalizations()


class ShortAnswerGradingIngestor:
    """`grading.short_answer` → respuesta calificada por criterios; cierra el intento (U1c, U1d)."""

    job_type = GRADING_SHORT_ANSWER
    result_model: type[BaseModel] = GradingV1
    progress_label = "Calificando tus respuestas"

    def __init__(self, service: AttemptService) -> None:
        self._service = service

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        return await self._service.can_see(refs.enrollment_id, user)

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        return await self._service.ingest_grading(job, result)

    async def on_failed(self, job: JobStatus, error_code: str) -> None:  # noqa: ARG002
        await self._service.grading_failed(job)

    async def pending_jobs(self) -> list[PendingJob]:
        return await self._service.pending_gradings()


class QuizBankIngestor:
    """`items.generate_quiz_bank` bajo demanda → ítems nuevos del tema (U1b)."""

    job_type = QUIZ_BANK
    result_model: type[BaseModel] = AssessmentItemBankV1
    progress_label = "Preparando preguntas nuevas"

    def __init__(self, service: AttemptService) -> None:
        self._service = service

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        return await self._service.can_see(refs.enrollment_id, user)

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        return await self._service.ingest_quiz_bank(job, result)

    async def on_failed(self, job: JobStatus, error_code: str) -> None:  # noqa: ARG002
        return None

    async def pending_jobs(self) -> list[PendingJob]:
        # Solo se ingiere al consultar: el aprendiz vuelve a pedir el intento (U1b).
        return []
