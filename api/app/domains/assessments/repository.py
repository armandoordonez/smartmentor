"""Interfaces (puertos) de los repositorios de evaluaciones."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic


class DiagnosticRepository(CrudRepository[Diagnostic], Protocol): ...


class AssessmentAttemptRepository(CrudRepository[AssessmentAttempt], Protocol):
    async def count_attempts(
        self, enrollment_id: int, path_step_id: int | None, assessment_type: str
    ) -> int:
        """Intentos ya registrados (activos o no) de una evaluación, para numerar el siguiente."""
        ...

    async def has_passed_final(self, enrollment_id: int) -> bool:
        """Si la inscripción tiene una evaluación final activa y aprobada."""
        ...


class BadgeRepository(CrudRepository[Badge], Protocol): ...
