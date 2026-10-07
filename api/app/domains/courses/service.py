"""Casos de uso de cursos, temas y prerrequisitos."""

from app.common.exceptions import NotFoundError
from app.common.service import CrudService
from app.common.unit_of_work import UnitOfWork
from app.domains.courses.entities import Course, Topic, TopicPrerequisite
from app.domains.courses.exceptions import PrerequisiteAcrossCoursesError, PrerequisiteCycleError
from app.domains.courses.repository import TopicPrerequisiteRepository, TopicRepository


class CourseService(CrudService[Course]):
    resource_name = "Course"


class TopicService(CrudService[Topic]):
    resource_name = "Topic"


class TopicPrerequisiteService(CrudService[TopicPrerequisite]):
    """Los prerrequisitos forman un grafo dirigido acíclico (DAG) dentro de un curso."""

    resource_name = "Topic prerequisite"

    def __init__(
        self,
        repository: TopicPrerequisiteRepository,
        topics: TopicRepository,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repository, uow)
        self._prerequisites = repository
        self._topics = topics

    async def _validate_create(self, entity: TopicPrerequisite) -> None:
        topic = await self._topics.get(entity.topic_id)
        if topic is None:
            raise NotFoundError("Topic", entity.topic_id)
        prerequisite = await self._topics.get(entity.prerequisite_topic_id)
        if prerequisite is None:
            raise NotFoundError("Topic", entity.prerequisite_topic_id)
        if topic.course_id != prerequisite.course_id:
            raise PrerequisiteAcrossCoursesError
        if await self._creates_cycle(entity.topic_id, entity.prerequisite_topic_id):
            raise PrerequisiteCycleError

    async def _creates_cycle(self, topic_id: int, prerequisite_id: int) -> bool:
        """Hay ciclo si el prerrequisito ya depende, directa o indirectamente, del tema."""
        if topic_id == prerequisite_id:
            return True
        pending = [prerequisite_id]
        visited: set[int] = set()
        while pending:
            current = pending.pop()
            if current == topic_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(await self._prerequisites.get_prerequisite_ids(current))
        return False
