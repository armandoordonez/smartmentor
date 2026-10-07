"""Composición: construye los servicios de evaluaciones con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.assessments.repository_impl import (
    SqlAlchemyAssessmentAttemptRepository,
    SqlAlchemyBadgeRepository,
    SqlAlchemyDiagnosticRepository,
)
from app.domains.assessments.service import (
    AssessmentAttemptService,
    BadgeService,
    DiagnosticService,
)
from app.domains.learning_paths.repository_impl import (
    SqlAlchemyEnrollmentRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyPathStepRepository,
)


def get_diagnostic_service(session: SessionDep) -> DiagnosticService:
    return DiagnosticService(SqlAlchemyDiagnosticRepository(session), SqlAlchemyUnitOfWork(session))


def get_assessment_attempt_service(session: SessionDep) -> AssessmentAttemptService:
    return AssessmentAttemptService(
        SqlAlchemyAssessmentAttemptRepository(session),
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemyPathStepRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_badge_service(session: SessionDep) -> BadgeService:
    return BadgeService(
        SqlAlchemyBadgeRepository(session),
        SqlAlchemyAssessmentAttemptRepository(session),
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
