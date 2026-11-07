"""Contratos HTTP del cliente de IA: trabajos asíncronos (docs/contracts/api-v2.md, sección 7)."""

from typing import Any

from pydantic import BaseModel


class JobAccepted(BaseModel):
    """Respuesta `202` de toda operación asíncrona; la app consulta `poll_url` cada 2 s."""

    job_id: str
    status: str = "queued"
    poll_url: str

    @classmethod
    def for_job(cls, job_id: str) -> "JobAccepted":
        return cls(job_id=job_id, poll_url=f"/api/v1/jobs/{job_id}")


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress_label: str
    ingested: bool
    next_action: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
