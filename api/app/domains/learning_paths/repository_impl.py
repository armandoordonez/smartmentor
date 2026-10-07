"""Repositorios SQLAlchemy de rutas de aprendizaje."""

from typing import ClassVar

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep
from app.domains.learning_paths.models import EnrollmentModel, LearningPathModel, PathStepModel


class SqlAlchemyLearningPathRepository(SqlAlchemyCrudRepository[LearningPathModel, LearningPath]):
    model = LearningPathModel
    entity = LearningPath
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "learning_paths_course_id_fk": ("COURSE_NOT_FOUND", "The course does not exist."),
        "learning_paths_thresholds_ck": (
            "INVALID_THRESHOLD",
            "Thresholds must be between 0 and 100.",
        ),
        "learning_paths_max_attempts_ck": (
            "INVALID_MAX_ATTEMPTS",
            "max_attempts must be at least 1.",
        ),
    }


class SqlAlchemyEnrollmentRepository(SqlAlchemyCrudRepository[EnrollmentModel, Enrollment]):
    model = EnrollmentModel
    entity = Enrollment
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "enrollments_user_path_uq": (
            "ALREADY_ENROLLED",
            "The user is already enrolled in this learning path.",
        ),
        "enrollments_user_id_fk": ("USER_NOT_FOUND", "The user does not exist."),
        "enrollments_learning_path_id_fk": (
            "LEARNING_PATH_NOT_FOUND",
            "The learning path does not exist.",
        ),
        "enrollments_status_ck": ("INVALID_ENROLLMENT_STATUS", "Invalid enrollment status."),
    }


class SqlAlchemyPathStepRepository(SqlAlchemyCrudRepository[PathStepModel, PathStep]):
    model = PathStepModel
    entity = PathStep
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "path_steps_enrollment_order_uq": (
            "STEP_ORDER_TAKEN",
            "The enrollment already has a step in this position.",
        ),
        "path_steps_enrollment_topic_uq": (
            "TOPIC_ALREADY_IN_PATH",
            "The enrollment already has a step for this topic.",
        ),
        "path_steps_enrollment_id_fk": ("ENROLLMENT_NOT_FOUND", "The enrollment does not exist."),
        "path_steps_topic_id_fk": ("TOPIC_NOT_FOUND", "The topic does not exist."),
        "path_steps_status_ck": ("INVALID_STEP_STATUS", "Invalid step status."),
    }
