"""Barrido periódico: ingiere los trabajos terminados que nadie consultó (plan 5.3.3).

Corre en el `lifespan` de la API cada `AI_SWEEP_INTERVAL_SECONDS` (60 por defecto). Por ejemplo, la
generación del contenido de un curso termina minutos después de que el instructor cerró la pantalla.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import apply_audit_user
from app.domains.ai_gateway.dependencies import build_job_service
from app.domains.ai_gateway.repository import AiServicePort

logger = logging.getLogger("app.ai_gateway.sweeper")

SWEEPER_AUDIT_USER = "system:ai-sweeper"
MAX_JOBS_PER_SWEEP = 200


async def sweep_once(session_factory: async_sessionmaker[AsyncSession], ai: AiServicePort) -> int:
    """Una pasada del barrido. Devuelve cuántos trabajos pendientes revisó."""
    async with session_factory() as session:
        await apply_audit_user(session, SWEEPER_AUDIT_USER)
        service = build_job_service(session, ai)
        pending = (await service.pending())[:MAX_JOBS_PER_SWEEP]
    checked = 0
    for job in pending:
        # Una sesión por trabajo: un fallo en uno no deja la transacción de los demás rota.
        async with session_factory() as session:
            await apply_audit_user(session, SWEEPER_AUDIT_USER)
            await build_job_service(session, ai).sweep_one(job)
        checked += 1
    return checked


async def run_sweeper(
    session_factory: async_sessionmaker[AsyncSession], ai: AiServicePort, interval_seconds: int
) -> None:
    """Bucle del barrido; se cancela al apagar la aplicación."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await sweep_once(session_factory, ai)
        except asyncio.CancelledError:
            raise
        except Exception:
            # El barrido nunca debe tumbar la API: se registra y se vuelve a intentar.
            logger.exception("the AI jobs sweep failed")
