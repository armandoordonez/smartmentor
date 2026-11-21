"""Entidades del cliente de `ai/` (Python puro): referencias, estado de un trabajo y errores."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class JobRefs:
    """Referencias que `ai/` guarda en `ai_jobs` para filtrar costos y presupuesto (AD2)."""

    course_id: int | None = None
    topic_id: int | None = None
    enrollment_id: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "course_id": self.course_id,
            "topic_id": self.topic_id,
            "enrollment_id": self.enrollment_id,
        }


@dataclass(frozen=True)
class JobRef:
    """Respuesta de `POST /v1/jobs`: el trabajo creado (o el existente con la misma clave)."""

    job_id: str
    job_type: str
    status: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class AiJobError:
    """Error de un trabajo `failed` (códigos en docs/contracts/error-codes.md)."""

    code: str
    message: str
    retryable: bool


@dataclass(frozen=True)
class JobStatus:
    """Estado de un trabajo de `ai/` (`GET /v1/jobs/{job_id}`)."""

    job_id: str
    job_type: str
    status: str  # queued | running | succeeded | failed
    contract: str | None = None
    result: dict[str, Any] | None = None
    error: AiJobError | None = None
    attempts: int = 0
    cost_usd: float | None = None
    refs: JobRefs = JobRefs()
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_finished(self) -> bool:
        return self.status in ("succeeded", "failed")


@dataclass(frozen=True)
class PendingJob:
    """Un trabajo terminado en `ai/` cuyo resultado aún no se ha ingerido."""

    job_id: str
    job_type: str
