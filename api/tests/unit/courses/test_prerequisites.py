import pytest

from app.common.exceptions import NotFoundError
from app.domains.courses.entities import Topic, TopicPrerequisite
from app.domains.courses.exceptions import PrerequisiteAcrossCoursesError, PrerequisiteCycleError
from app.domains.courses.service import TopicPrerequisiteService
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository


class InMemoryPrerequisites(InMemoryRepository[TopicPrerequisite]):
    async def get_prerequisite_ids(self, topic_id: int) -> list[int]:
        return [
            e.prerequisite_topic_id
            for e in self.items.values()
            if e.topic_id == topic_id and e.active
        ]


def make_service(
    edges: list[tuple[int, int]],
) -> TopicPrerequisiteService:
    topics = InMemoryRepository[Topic](
        [
            Topic(id=1, course_id=1, name="A"),
            Topic(id=2, course_id=1, name="B"),
            Topic(id=3, course_id=1, name="C"),
            Topic(id=4, course_id=2, name="Otro curso"),
        ]
    )
    prerequisites = InMemoryPrerequisites(
        [TopicPrerequisite(topic_id=t, prerequisite_topic_id=p) for t, p in edges]
    )
    return TopicPrerequisiteService(prerequisites, topics, FakeUnitOfWork())


async def test_accepts_an_edge_that_keeps_the_graph_acyclic() -> None:
    service = make_service([(2, 1)])  # B requiere A
    created = await service.create(TopicPrerequisite(topic_id=3, prerequisite_topic_id=2))
    assert created.id is not None


async def test_rejects_a_direct_cycle() -> None:
    service = make_service([(2, 1)])  # B requiere A
    with pytest.raises(PrerequisiteCycleError):
        await service.create(TopicPrerequisite(topic_id=1, prerequisite_topic_id=2))  # A requiere B


async def test_rejects_an_indirect_cycle() -> None:
    service = make_service([(2, 1), (3, 2)])  # C requiere B, B requiere A
    with pytest.raises(PrerequisiteCycleError):
        await service.create(TopicPrerequisite(topic_id=1, prerequisite_topic_id=3))  # A requiere C


async def test_rejects_prerequisites_from_another_course() -> None:
    service = make_service([])
    with pytest.raises(PrerequisiteAcrossCoursesError):
        await service.create(TopicPrerequisite(topic_id=1, prerequisite_topic_id=4))


async def test_rejects_unknown_topics() -> None:
    service = make_service([])
    with pytest.raises(NotFoundError):
        await service.create(TopicPrerequisite(topic_id=1, prerequisite_topic_id=99))
