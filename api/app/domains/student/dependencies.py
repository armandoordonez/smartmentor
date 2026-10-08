"""Composición: construye el servicio del estudiante con los repositorios de varios dominios."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.assessments.repository_impl import (
    SqlAlchemyAssessmentAttemptRepository,
    SqlAlchemyBadgeRepository,
    SqlAlchemyDiagnosticRepository,
)
from app.domains.learning_paths.repository_impl import (
    SqlAlchemyEnrollmentRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyPathStepRepository,
)
from app.domains.student.service import StudentService


def get_student_service(session: SessionDep) -> StudentService:
    return StudentService(
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemyPathStepRepository(session),
        SqlAlchemyDiagnosticRepository(session),
        SqlAlchemyAssessmentAttemptRepository(session),
        SqlAlchemyBadgeRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
