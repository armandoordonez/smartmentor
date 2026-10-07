"""Casos de uso de evaluaciones: diagnóstico, intentos con umbrales de la ruta y badge."""

from collections.abc import Mapping
from typing import Any

from app.common.exceptions import NotFoundError
from app.common.service import CrudService
from app.common.unit_of_work import UnitOfWork
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic
from app.domains.assessments.exceptions import (
    FinalAssessmentNotPassedError,
    MaxAttemptsExceededError,
    StepEnrollmentMismatchError,
)
from app.domains.assessments.repository import AssessmentAttemptRepository, BadgeRepository
from app.domains.learning_paths.entities import LearningPath
from app.domains.learning_paths.repository import (
    EnrollmentRepository,
    LearningPathRepository,
    PathStepRepository,
)


class DiagnosticService(CrudService[Diagnostic]):
    resource_name = "Diagnostic"


class AssessmentAttemptService(CrudService[AssessmentAttempt]):
    """Reglas del brief: máximo de intentos por ruta y aprobación según el umbral de la ruta."""

    resource_name = "Assessment attempt"

    def __init__(
        self,
        repository: AssessmentAttemptRepository,
        enrollments: EnrollmentRepository,
        learning_paths: LearningPathRepository,
        path_steps: PathStepRepository,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repository, uow)
        self._attempts = repository
        self._enrollments = enrollments
        self._learning_paths = learning_paths
        self._path_steps = path_steps

    async def _learning_path_of(self, enrollment_id: int) -> LearningPath:
        enrollment = await self._enrollments.get(enrollment_id)
        if enrollment is None:
            raise NotFoundError("Enrollment", enrollment_id)
        learning_path = await self._learning_paths.get(enrollment.learning_path_id)
        if learning_path is None:
            raise NotFoundError("Learning path", enrollment.learning_path_id)
        return learning_path

    @staticmethod
    def _is_passed(learning_path: LearningPath, assessment_type: str, score: float) -> bool:
        threshold = (
            learning_path.topic_pass_threshold
            if assessment_type == "topic"
            else learning_path.final_pass_threshold
        )
        return score >= threshold

    async def create(self, entity: AssessmentAttempt) -> AssessmentAttempt:
        learning_path = await self._learning_path_of(entity.enrollment_id)

        if entity.path_step_id is not None:
            step = await self._path_steps.get(entity.path_step_id)
            if step is None:
                raise NotFoundError("Path step", entity.path_step_id)
            if step.enrollment_id != entity.enrollment_id:
                raise StepEnrollmentMismatchError

        previous = await self._attempts.count_attempts(
            entity.enrollment_id, entity.path_step_id, entity.assessment_type
        )
        if previous + 1 > learning_path.max_attempts:
            raise MaxAttemptsExceededError(learning_path.max_attempts)
        entity.attempt_number = previous + 1

        if entity.score is not None:
            entity.passed = self._is_passed(learning_path, entity.assessment_type, entity.score)
        return await super().create(entity)

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> AssessmentAttempt:
        values = dict(changes)
        if values.get("score") is not None:
            current = await self.get(entity_id)
            learning_path = await self._learning_path_of(current.enrollment_id)
            values["passed"] = self._is_passed(
                learning_path, current.assessment_type, values["score"]
            )
        return await super().update(entity_id, values)


class BadgeService(CrudService[Badge]):
    resource_name = "Badge"

    def __init__(
        self,
        repository: BadgeRepository,
        attempts: AssessmentAttemptRepository,
        enrollments: EnrollmentRepository,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repository, uow)
        self._attempts = attempts
        self._enrollments = enrollments

    async def _validate_create(self, entity: Badge) -> None:
        if await self._enrollments.get(entity.enrollment_id) is None:
            raise NotFoundError("Enrollment", entity.enrollment_id)
        if not await self._attempts.has_passed_final(entity.enrollment_id):
            raise FinalAssessmentNotPassedError
