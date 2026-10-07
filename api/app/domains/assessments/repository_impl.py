"""Repositorios SQLAlchemy de evaluaciones."""

from typing import ClassVar

from sqlalchemy import func, select

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.assessments.entities import AssessmentAttempt, Badge, Diagnostic
from app.domains.assessments.models import AssessmentAttemptModel, BadgeModel, DiagnosticModel


class SqlAlchemyDiagnosticRepository(SqlAlchemyCrudRepository[DiagnosticModel, Diagnostic]):
    model = DiagnosticModel
    entity = Diagnostic
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "diagnostics_enrollment_uq": (
            "DIAGNOSTIC_ALREADY_EXISTS",
            "The enrollment already has a diagnostic.",
        ),
        "diagnostics_enrollment_id_fk": ("ENROLLMENT_NOT_FOUND", "The enrollment does not exist."),
    }


class SqlAlchemyAssessmentAttemptRepository(
    SqlAlchemyCrudRepository[AssessmentAttemptModel, AssessmentAttempt]
):
    model = AssessmentAttemptModel
    entity = AssessmentAttempt
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "assessment_attempts_enrollment_id_fk": (
            "ENROLLMENT_NOT_FOUND",
            "The enrollment does not exist.",
        ),
        "assessment_attempts_path_step_id_fk": (
            "PATH_STEP_NOT_FOUND",
            "The path step does not exist.",
        ),
        "assessment_attempts_type_ck": (
            "INVALID_ASSESSMENT_TYPE",
            "assessment_type must be topic or final.",
        ),
        "assessment_attempts_step_ck": (
            "INVALID_ATTEMPT_STEP",
            "A topic attempt needs a path step and a final attempt cannot have one.",
        ),
    }

    async def count_attempts(
        self, enrollment_id: int, path_step_id: int | None, assessment_type: str
    ) -> int:
        step_condition = (
            AssessmentAttemptModel.path_step_id.is_(None)
            if path_step_id is None
            else AssessmentAttemptModel.path_step_id == path_step_id
        )
        result = await self._session.execute(
            select(func.count())
            .select_from(AssessmentAttemptModel)
            .where(
                AssessmentAttemptModel.enrollment_id == enrollment_id,
                AssessmentAttemptModel.assessment_type == assessment_type,
                step_condition,
            )
        )
        return result.scalar_one()

    async def has_passed_final(self, enrollment_id: int) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(AssessmentAttemptModel)
            .where(
                AssessmentAttemptModel.enrollment_id == enrollment_id,
                AssessmentAttemptModel.assessment_type == "final",
                AssessmentAttemptModel.passed.is_(True),
                AssessmentAttemptModel.active.is_(True),
            )
        )
        return result.scalar_one() > 0


class SqlAlchemyBadgeRepository(SqlAlchemyCrudRepository[BadgeModel, Badge]):
    model = BadgeModel
    entity = Badge
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "badges_enrollment_uq": ("BADGE_ALREADY_ISSUED", "The enrollment already has a badge."),
        "badges_enrollment_id_fk": ("ENROLLMENT_NOT_FOUND", "The enrollment does not exist."),
    }
