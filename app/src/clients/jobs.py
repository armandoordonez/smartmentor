"""Sondeo de trabajos de IA con espera progresiva (contrato, secciones 1 y 7).

La app consulta `GET /jobs/{id}` cada pocos segundos (U1x). Hay dos formas de usarlo:

- `next_poll_delay(attempt)`: para páginas con `st.fragment(run_every=...)`, que consultan una vez
  por ejecución sin bloquear el hilo.
- `wait_for_job(...)`: bloqueante, para pruebas y tareas cortas; recibe el `sleep` por parámetro.
"""

import time
from collections.abc import Callable

from clients.base import ApiError, SmartMentorClient
from clients.models import Job

FIRST_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 5.0
DEFAULT_TIMEOUT_SECONDS = 90.0

FINAL_STATUSES = frozenset({"succeeded", "failed"})


def next_poll_delay(attempt: int) -> float:
    """Espera antes de la consulta número `attempt` (desde 0): 1 s, 2 s, 3 s… hasta 5 s."""
    return min(FIRST_DELAY_SECONDS * (attempt + 1), MAX_DELAY_SECONDS)


def is_done(job: Job) -> bool:
    """Un trabajo termina cuando la API lo ingirió con éxito o cuando falló."""
    return (job.status == "succeeded" and job.ingested) or job.status == "failed"


def wait_for_job(
    client: SmartMentorClient,
    job_id: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Job:
    """Consulta el trabajo hasta que termina o vence `timeout`; lanza `ApiError(504)` si vence."""
    waited = 0.0
    attempt = 0
    while True:
        job = client.get_job(job_id)
        if is_done(job):
            return job
        delay = next_poll_delay(attempt)
        if waited + delay > timeout:
            raise ApiError(504, "JOB_TIMEOUT", "job did not finish in time", retryable=True)
        sleep(delay)
        waited += delay
        attempt += 1
