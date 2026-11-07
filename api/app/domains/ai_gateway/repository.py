"""Puerto del servicio de IA (plan 5.3.1, estándar §34).

La API **nunca** llama a un SDK de LLM: solo habla con `ai/` a través de este puerto. Adaptadores:
`HttpAiService` (producción, `httpx`) y `FakeAiService` (pruebas y desarrollo sin `ai/`).
"""

from datetime import UTC, datetime
from typing import Any, Protocol

from app.domains.ai_gateway.entities import JobRef, JobRefs, JobStatus


class AiServicePort(Protocol):
    async def submit_job(
        self,
        job_type: str,
        input: dict[str, Any],
        idempotency_key: str,
        refs: JobRefs | None = None,
    ) -> JobRef:
        """Crea un trabajo asíncrono. La misma `idempotency_key` devuelve el mismo trabajo."""
        ...

    async def get_job(self, job_id: str) -> JobStatus:
        """Estado y resultado. Lanza `AiJobNotFoundError` si no existe."""
        ...

    async def list_jobs(
        self,
        *,
        job_type: str | None = None,
        status: str | None = None,
        course_id: int | None = None,
        limit: int = 100,
    ) -> list[JobStatus]:
        """Lista de trabajos (observabilidad y barrido de ingesta)."""
        ...

    async def run_task(
        self,
        task: str,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        """Tarea síncrona (< 3 s): `levels.estimate`, `path.sequence`, `video.rank`."""
        ...


async def latest_job(
    ai: AiServicePort, job_type: str, course_id: int, *, only_finished: bool = False
) -> JobStatus | None:
    """El trabajo más reciente de ese tipo para el curso (`ai/` no garantiza el orden)."""
    jobs = await ai.list_jobs(job_type=job_type, course_id=course_id, limit=100)
    if only_finished:
        jobs = [j for j in jobs if j.is_finished]
    if not jobs:
        return None
    epoch = datetime.min.replace(tzinfo=UTC)
    return max(enumerate(jobs), key=lambda pair: (pair[1].created_at or epoch, pair[0]))[1]
