"""`FakeAiService` que, como `ai/`, escribe cada trabajo en `ai_jobs` desde su propia conexión.

Sirve para probar que la API no tiene tomada (`FOR UPDATE`) la fila a la que apunta el trabajo
mientras espera la respuesta de `ai/`: si la tuviera, el INSERT agota su `lock_timeout` y falla.
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.ai_gateway.entities import JobRef, JobRefs
from app.domains.ai_gateway.fake import FakeAiService


class RowWritingAi(FakeAiService):
    """Como `ai/`: inserta el trabajo en `ai_jobs` desde otra conexión y no espera más de 2 s."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self._engine = engine

    async def submit_job(
        self,
        job_type: str,
        input: dict[str, Any],
        idempotency_key: str,
        refs: JobRefs | None = None,
    ) -> JobRef:
        ref = await super().submit_job(job_type, input, idempotency_key, refs)
        found = refs or JobRefs()
        async with self._engine.begin() as conn:
            await conn.execute(text("SET LOCAL lock_timeout = '2s'"))
            await conn.execute(
                text(
                    "INSERT INTO ai_jobs (job_type, idempotency_key, input, course_id, topic_id, "
                    "enrollment_id) VALUES (:job_type, :key, CAST(:input AS jsonb), :course_id, "
                    ":topic_id, :enrollment_id) ON CONFLICT (idempotency_key) DO NOTHING"
                ),
                {
                    "job_type": job_type,
                    "key": idempotency_key,
                    "input": json.dumps(input, default=str),
                    **found.as_dict(),
                },
            )
        return ref
