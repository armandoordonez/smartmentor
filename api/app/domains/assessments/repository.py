"""Interfaces (puertos) de los repositorios de evaluaciones."""

from typing import Any, Protocol
from uuid import UUID

from app.domains.assessments.entities import (
    AssessmentAttempt,
    AssessmentItem,
    AttemptAnswer,
    Badge,
    Diagnostic,
)


class ItemRepository(Protocol):
    async def add(self, item: AssessmentItem) -> AssessmentItem: ...

    async def by_ids(self, item_ids: list[int]) -> dict[int, AssessmentItem]: ...

    async def approved(self, topic_ids: list[int], source: str) -> list[AssessmentItem]:
        """Ítems `approved` y activos de esos temas y esa fuente, por id."""
        ...

    async def count_for_topic(self, topic_id: int, source: str) -> int:
        """Ítems de la fuente en el tema, en cualquier estado (versión del banco)."""
        ...

    async def stems_for_topic(self, topic_id: int, source: str) -> list[str]: ...

    async def exists_for_job(self, job_id: str) -> bool:
        """Si ya se ingirieron ítems de ese trabajo de `ai/` (idempotencia)."""
        ...

    async def lock_job(self, job_id: str) -> None:
        """Serializa la ingesta de un mismo trabajo hasta el fin de la transacción."""
        ...


class DiagnosticRepository(Protocol):
    async def add(self, diagnostic: Diagnostic) -> Diagnostic: ...

    async def by_enrollment(
        self, enrollment_id: int, *, for_update: bool = False
    ) -> Diagnostic | None: ...

    async def update(self, diagnostic_id: int, changes: dict[str, Any]) -> Diagnostic | None: ...

    async def list_by_status(self, status: str) -> list[Diagnostic]: ...


class AttemptRepository(Protocol):
    async def add(self, attempt: AssessmentAttempt) -> AssessmentAttempt: ...

    async def get(
        self, attempt_id: int, *, for_update: bool = False
    ) -> AssessmentAttempt | None: ...

    async def update(
        self, attempt_id: int, changes: dict[str, Any]
    ) -> AssessmentAttempt | None: ...

    async def list_for_enrollment(self, enrollment_id: int) -> list[AssessmentAttempt]:
        """Intentos activos de la inscripción, por id."""
        ...

    async def list_by_status(self, status: str) -> list[AssessmentAttempt]: ...


class AnswerRepository(Protocol):
    async def get(self, answer_id: int) -> AttemptAnswer | None: ...

    async def add(self, answer: AttemptAnswer) -> AttemptAnswer: ...

    async def update(self, answer_id: int, changes: dict[str, Any]) -> AttemptAnswer | None: ...

    async def list_for_attempt(self, attempt_id: int) -> list[AttemptAnswer]:
        """Respuestas del intento, por id."""
        ...


class BadgeRepository(Protocol):
    async def add(self, badge: Badge) -> Badge: ...

    async def by_enrollment(self, enrollment_id: int) -> Badge | None: ...

    async def by_public_id(self, public_id: UUID) -> Badge | None: ...

    async def for_enrollments(self, enrollment_ids: list[int]) -> list[Badge]: ...


class ContentReader(Protocol):
    """Lectura de recursos y videos (los escribe el dominio de contenido)."""

    async def explanation(self, topic_id: int) -> dict[str, Any] | None:
        """La explicación principal aprobada más reciente del tema."""
        ...

    async def personal_example(
        self, topic_id: int, enrollment_id: int
    ) -> dict[str, Any] | None: ...

    async def remedial_resource_id(self, topic_id: int, enrollment_id: int) -> int | None: ...

    async def video(self, topic_id: int) -> dict[str, Any] | None:
        """El video `in_use` del tema o, si no hay, el primer respaldo."""
        ...

    async def outcomes(self, topic_id: int) -> list[dict[str, Any]]: ...


class SurveyLookup(Protocol):
    async def has_final_survey(self, enrollment_id: int) -> bool: ...
