"""Barrido: deja de insistir con los trabajos que no se pueden ingerir (B-039)."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.domains.ai_gateway import sweeper
from app.domains.ai_gateway.entities import PendingJob


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeJobService:
    """Dos trabajos pendientes: uno se ingiere y otro falla siempre (huérfano)."""

    def __init__(self, swept: list[str]) -> None:
        self._swept = swept

    async def pending(self) -> list[PendingJob]:
        return [PendingJob("orphan", "x"), PendingJob("good", "x")]

    async def sweep_one(self, job: PendingJob) -> bool:
        self._swept.append(job.job_id)
        return job.job_id != "orphan"


@pytest.fixture
def swept(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def no_audit(*_: Any) -> None:
        return None

    monkeypatch.setattr(sweeper, "apply_audit_user", no_audit)
    monkeypatch.setattr(sweeper, "build_job_service", lambda *_: FakeJobService(calls))
    return calls


async def test_a_job_that_keeps_failing_is_dropped_after_the_attempt_limit(
    swept: list[str],
) -> None:
    attempts: dict[str, int] = {}
    for _ in range(sweeper.MAX_FAILED_ATTEMPTS + 3):
        await sweeper.sweep_once(lambda: FakeSession(), SimpleNamespace(), attempts)  # type: ignore[arg-type, return-value]
    assert swept.count("orphan") == sweeper.MAX_FAILED_ATTEMPTS
    assert swept.count("good") == sweeper.MAX_FAILED_ATTEMPTS + 3
