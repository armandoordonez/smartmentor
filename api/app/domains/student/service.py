"""Casos de uso del estudiante sobre sus propios datos: inscripciones, pasos, diagnóstico,
intentos y badge.

Toda operación recibe el id del usuario autenticado y comprueba que la inscripción sea suya. Si no
lo es (o no existe), responde «no encontrado»: no revela que el dato exista. El estudiante no puede
poner puntajes ni estados de aprobación: eso lo calcula el sistema.
"""

from datetime import UTC, datetime
from typing import Any

from app.common.exceptions import NotFoundError
from app.common.unit_of_work import UnitOfWork
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic
from app.domains.assessments.repository import (
    AssessmentAttemptRepository,
    BadgeRepository,
    DiagnosticRepository,
)
from app.domains.learning_paths.entities import Enrollment, PathStep
from app.domains.learning_paths.repository import (
    EnrollmentRepository,
    LearningPathRepository,
    PathStepRepository,
)
from app.domains.student.exceptions import AlreadySubmittedError, EnrollmentClosedError

_CLOSED_STATUSES = ("completed", "abandoned")


class StudentService:
    def __init__(
        self,
        enrollments: EnrollmentRepository,
        learning_paths: LearningPathRepository,
        path_steps: PathStepRepository,
        diagnostics: DiagnosticRepository,
        attempts: AssessmentAttemptRepository,
        badges: BadgeRepository,
        uow: UnitOfWork,
    ) -> None:
        self._enrollments = enrollments
        self._learning_paths = learning_paths
        self._path_steps = path_steps
        self._diagnostics = diagnostics
        self._attempts = attempts
        self._badges = badges
        self._uow = uow

    async def _own_enrollment(self, user_id: int, enrollment_id: int) -> Enrollment:
        enrollment = await self._enrollments.get(enrollment_id)
        if enrollment is None or not enrollment.active or enrollment.user_id != user_id:
            raise NotFoundError("Enrollment", enrollment_id)
        return enrollment

    # --- inscripciones -----------------------------------------------------------------------
    async def enroll(
        self,
        user_id: int,
        learning_path_id: int,
        profile_description: str | None,
        personal_objective: str | None,
    ) -> Enrollment:
        learning_path = await self._learning_paths.get(learning_path_id)
        if learning_path is None or not learning_path.active:
            raise NotFoundError("Learning path", learning_path_id)
        enrollment = await self._enrollments.add(
            Enrollment(
                user_id=user_id,
                learning_path_id=learning_path_id,
                profile_description=profile_description,
                personal_objective=personal_objective,
            )
        )
        await self._uow.commit()
        return enrollment

    async def list_enrollments(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]:
        return await self._enrollments.search(
            filters={"user_id": user_id}, active=True, limit=limit, offset=offset
        )

    async def get_enrollment(self, user_id: int, enrollment_id: int) -> Enrollment:
        return await self._own_enrollment(user_id, enrollment_id)

    async def update_profile(
        self, user_id: int, enrollment_id: int, changes: dict[str, Any]
    ) -> Enrollment:
        enrollment = await self._own_enrollment(user_id, enrollment_id)
        if enrollment.status in _CLOSED_STATUSES:
            raise EnrollmentClosedError
        if not changes:
            return enrollment
        updated = await self._enrollments.update(enrollment_id, changes)
        if updated is None:
            raise NotFoundError("Enrollment", enrollment_id)
        await self._uow.commit()
        return updated

    async def abandon(self, user_id: int, enrollment_id: int) -> Enrollment:
        enrollment = await self._own_enrollment(user_id, enrollment_id)
        if enrollment.status == "abandoned":
            return enrollment
        if enrollment.status == "completed":
            raise EnrollmentClosedError
        updated = await self._enrollments.update(enrollment_id, {"status": "abandoned"})
        if updated is None:
            raise NotFoundError("Enrollment", enrollment_id)
        await self._uow.commit()
        return updated

    # --- ruta personalizada ------------------------------------------------------------------
    async def list_steps(
        self, user_id: int, enrollment_id: int, *, limit: int, offset: int
    ) -> tuple[list[PathStep], int]:
        await self._own_enrollment(user_id, enrollment_id)
        steps, total = await self._path_steps.search(
            filters={"enrollment_id": enrollment_id}, active=True, limit=limit, offset=offset
        )
        return sorted(steps, key=lambda step: step.step_order), total

    # --- diagnóstico -------------------------------------------------------------------------
    async def get_diagnostic(self, user_id: int, enrollment_id: int) -> Diagnostic:
        await self._own_enrollment(user_id, enrollment_id)
        found, _ = await self._diagnostics.search(
            filters={"enrollment_id": enrollment_id}, active=True, limit=1, offset=0
        )
        if not found:
            raise NotFoundError("Diagnostic", enrollment_id)
        return found[0]

    async def submit_diagnostic(
        self, user_id: int, enrollment_id: int, answers: list[Any] | dict[str, Any]
    ) -> Diagnostic:
        diagnostic = await self.get_diagnostic(user_id, enrollment_id)
        if diagnostic.completed_at is not None:
            raise AlreadySubmittedError("diagnostic")
        assert diagnostic.id is not None
        updated = await self._diagnostics.update(
            diagnostic.id, {"answers": answers, "completed_at": datetime.now(UTC)}
        )
        if updated is None:
            raise NotFoundError("Diagnostic", enrollment_id)
        await self._uow.commit()
        return updated

    # --- evaluaciones ------------------------------------------------------------------------
    async def list_attempts(
        self, user_id: int, enrollment_id: int, *, limit: int, offset: int
    ) -> tuple[list[AssessmentAttempt], int]:
        await self._own_enrollment(user_id, enrollment_id)
        return await self._attempts.search(
            filters={"enrollment_id": enrollment_id}, active=True, limit=limit, offset=offset
        )

    async def submit_attempt(
        self,
        user_id: int,
        enrollment_id: int,
        attempt_id: int,
        answers: list[Any] | dict[str, Any],
    ) -> AssessmentAttempt:
        """Entrega respuestas; el puntaje y la aprobación los calcula el sistema."""
        await self._own_enrollment(user_id, enrollment_id)
        attempt = await self._attempts.get(attempt_id)
        if attempt is None or not attempt.active or attempt.enrollment_id != enrollment_id:
            raise NotFoundError("Assessment attempt", attempt_id)
        if attempt.submitted_at is not None:
            raise AlreadySubmittedError("assessment attempt")
        updated = await self._attempts.update(
            attempt_id, {"answers": answers, "submitted_at": datetime.now(UTC)}
        )
        if updated is None:
            raise NotFoundError("Assessment attempt", attempt_id)
        await self._uow.commit()
        return updated

    # --- badge -------------------------------------------------------------------------------
    async def get_badge(self, user_id: int, enrollment_id: int) -> Badge:
        await self._own_enrollment(user_id, enrollment_id)
        found, _ = await self._badges.search(
            filters={"enrollment_id": enrollment_id}, active=True, limit=1, offset=0
        )
        if not found:
            raise NotFoundError("Badge", enrollment_id)
        return found[0]
