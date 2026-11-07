"""Ingesta de resultados de `ai/` por consulta (modelo pull, ADR 0010, plan 5.3.3).

`GET /jobs/{id}` pide el estado al servicio de IA; si el trabajo terminó, valida el resultado contra
su contrato y lo escribe en las tablas de negocio en una transacción **idempotente**: cada ingestor
decide si ya ingirió ese trabajo mirando el estado de su propia entidad (con bloqueo de fila), de
modo que dos consultas simultáneas, o una consulta y el barrido, no duplican nada.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.common.constants import RoleCode
from app.common.exceptions import DomainError
from app.domains.ai_gateway.entities import JobRefs, JobStatus, PendingJob
from app.domains.ai_gateway.exceptions import (
    AiBudgetExceededError,
    AiJobNotFoundError,
    AiResultInvalidError,
    AiTaskFailedError,
)
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.identity.authentication import CurrentUser

logger = logging.getLogger("app.ai_gateway")

BUDGET_ERROR_CODES = frozenset({"BUDGET_EXCEEDED"})


class JobIngestor(Protocol):
    """Traductor de un tipo de trabajo: valida su resultado y lo escribe en el negocio."""

    job_type: str
    result_model: type[BaseModel]
    progress_label: str

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        """El usuario puede ver el trabajo (dueño del curso, de la inscripción...)."""
        ...

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        """Escribe el resultado. Devuelve `False` si ya estaba ingerido (idempotente)."""
        ...

    async def on_failed(self, job: JobStatus, error_code: str) -> None:
        """Deja la entidad en un estado coherente si el trabajo falló o su salida es inválida."""
        ...

    async def pending_jobs(self) -> list[PendingJob]:
        """Trabajos terminados en `ai/` cuyo resultado aún no se ingirió (para el barrido)."""
        ...


class IngestorRegistry:
    def __init__(self, ingestors: list[JobIngestor]) -> None:
        self._by_type = {ingestor.job_type: ingestor for ingestor in ingestors}

    def get(self, job_type: str) -> JobIngestor | None:
        return self._by_type.get(job_type)

    def all(self) -> list[JobIngestor]:
        return list(self._by_type.values())


@dataclass(frozen=True)
class JobView:
    """El trabajo visto por la API (`Job` de docs/contracts/api-v2.md, sección 7)."""

    job_id: str
    job_type: str
    status: str
    progress_label: str
    ingested: bool


class JobService:
    def __init__(self, ai: AiServicePort, registry: IngestorRegistry) -> None:
        self._ai = ai
        self._registry = registry

    async def get(self, job_id: str, user: CurrentUser) -> JobView:
        """Consulta del usuario: autoriza, ingiere si terminó y traduce los fallos."""
        job = await self._ai.get_job(job_id)
        ingestor = self._registry.get(job.job_type)
        if not user.has_any_role(RoleCode.ADMIN) and (
            ingestor is None or not await ingestor.is_owner(job.refs, user)
        ):
            # Un trabajo ajeno es indistinguible de uno inexistente (sección 18.2 del plan).
            raise AiJobNotFoundError(job_id)
        return await self._process(job, ingestor)

    async def sweep_one(self, pending: PendingJob) -> None:
        """Ingesta del barrido: sin usuario; los errores se registran y no detienen el barrido."""
        try:
            job = await self._ai.get_job(pending.job_id)
            await self._process(job, self._registry.get(job.job_type))
        except DomainError as exc:
            logger.warning(
                "sweep could not ingest the job", extra={"code": exc.code, "job_id": pending.job_id}
            )

    async def pending(self) -> list[PendingJob]:
        found: list[PendingJob] = []
        for ingestor in self._registry.all():
            found.extend(await ingestor.pending_jobs())
        return found

    async def _process(self, job: JobStatus, ingestor: JobIngestor | None) -> JobView:
        label = ingestor.progress_label if ingestor is not None else job.job_type
        if not job.is_finished:
            return JobView(job.job_id, job.job_type, job.status, label, ingested=False)
        if ingestor is None:
            # Tipo que ningún dominio ingiere todavía: el administrador solo ve el estado.
            return JobView(job.job_id, job.job_type, job.status, label, ingested=False)

        if job.status == "failed":
            error = job.error
            code = error.code if error is not None else "INTERNAL_ERROR"
            await ingestor.on_failed(job, code)
            if code in BUDGET_ERROR_CODES:
                raise AiBudgetExceededError(job.job_id)
            raise AiTaskFailedError(
                job.job_id, retryable=error.retryable if error else True, error_code=code
            )

        try:
            parsed = ingestor.result_model.model_validate(job.result)
        except ValidationError as exc:
            logger.error("the AI result is invalid", extra={"job_id": job.job_id})
            await ingestor.on_failed(job, "AI_RESULT_INVALID")
            raise AiResultInvalidError(job.job_id) from exc
        try:
            await ingestor.ingest(job, parsed)
        except AiResultInvalidError:
            # La salida cumple el esquema pero no tiene sentido (por ejemplo, un ciclo).
            await ingestor.on_failed(job, "AI_RESULT_INVALID")
            raise
        return JobView(job.job_id, job.job_type, "succeeded", label, ingested=True)
