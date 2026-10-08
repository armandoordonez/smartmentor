"""Catálogo de rutas (E1): rutas publicadas y si el estudiante ya está inscrito en cada una."""

from dataclasses import dataclass

from clients.base import SmartMentorClient
from clients.models import Enrollment, LearningPath, Topic


@dataclass(frozen=True)
class PathCard:
    path: LearningPath
    enrollment: Enrollment | None


def active_enrollment(enrollments: list[Enrollment], path_id: int) -> Enrollment | None:
    """La inscripción vigente del estudiante en la ruta (la más reciente que no abandonó)."""
    candidates = [
        e for e in enrollments if e.learning_path_id == path_id and e.status != "abandoned"
    ]
    return max(candidates, key=lambda e: e.id, default=None)


class CatalogService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def list_path_cards(self) -> list[PathCard]:
        enrollments = self._client.list_my_enrollments()
        return [
            PathCard(path=path, enrollment=active_enrollment(enrollments, path.id))
            for path in self._client.list_learning_paths()
        ]

    def get_path(self, path_id: int) -> LearningPath:
        return self._client.get_learning_path(path_id)

    def list_topics(self, course_id: int) -> list[Topic]:
        return self._client.list_topics(course_id)
