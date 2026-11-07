"""Puerto del servicio de IA (plan 5.3.1, estándar §34).

La API **nunca** llama a un SDK de LLM: solo habla con `ai/` a través de este puerto. Adaptadores:
`HttpAiService` (producción, `httpx`) y `FakeAiService` (pruebas y desarrollo sin `ai/`).
"""

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
