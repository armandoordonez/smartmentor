"""Casos de uso de rutas de aprendizaje, inscripciones y pasos."""

from app.common.exceptions import NotFoundError
from app.common.service import CrudService
from app.common.unit_of_work import UnitOfWork
from app.domains.courses.repository import TopicRepository
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep
from app.domains.learning_paths.exceptions import TopicNotInPathCourseError
from app.domains.learning_paths.repository import (
    EnrollmentRepository,
    LearningPathRepository,
    PathStepRepository,
)


class LearningPathService(CrudService[LearningPath]):
    resource_name = "Learning path"


class EnrollmentService(CrudService[Enrollment]):
    resource_name = "Enrollment"


class PathStepService(CrudService[PathStep]):
    resource_name = "Path step"

    def __init__(
        self,
        repository: PathStepRepository,
        enrollments: EnrollmentRepository,
        learning_paths: LearningPathRepository,
        topics: TopicRepository,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repository, uow)
        self._enrollments = enrollments
        self._learning_paths = learning_paths
        self._topics = topics

    async def _validate_create(self, entity: PathStep) -> None:
        """Un paso solo puede usar temas del curso al que pertenece la ruta de la inscripción."""
        enrollment = await self._enrollments.get(entity.enrollment_id)
        if enrollment is None:
            raise NotFoundError("Enrollment", entity.enrollment_id)
        learning_path = await self._learning_paths.get(enrollment.learning_path_id)
        if learning_path is None:
            raise NotFoundError("Learning path", enrollment.learning_path_id)
        topic = await self._topics.get(entity.topic_id)
        if topic is None:
            raise NotFoundError("Topic", entity.topic_id)
        if topic.course_id != learning_path.course_id:
            raise TopicNotInPathCourseError
