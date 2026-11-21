"""Entry point of the ``ai-worker`` process: ``python -m app.worker``.

Refuses to start (exit 1) while ``/ready`` would fail: missing settings, database, prompts with a
changed hash or a configured model without price. Stops cleanly on SIGTERM and SIGINT.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from app.container import build_container
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker.loop import JobWorker

logger = logging.getLogger("app.worker")


async def main() -> int:
    settings = get_settings()
    configure_logging(
        service="smartmentor-ai-worker",
        environment=settings.app_env,
        timezone=settings.app_timezone,
        level=settings.log_level,
    )
    container = build_container(settings)
    try:
        missing = await container.readiness()
        if missing:
            logger.error("worker not ready: %s", "; ".join(missing), extra={"code": "NOT_READY"})
            return 1
        worker = JobWorker(
            jobs=container.jobs,
            service=container.job_service,
            config=container.worker_config,
            clock=container.clock,
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, worker.stop)
        await worker.run_forever()
        return 0
    finally:
        await container.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
