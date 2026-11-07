"""Interfaces (puertos) de los repositorios de cursos."""

from typing import Any, Protocol

from app.common.repository import CrudRepository
from app.domains.courses.entities import (
    Course,
    LearningOutcome,
    SyllabusDocument,
    SyllabusExtraction,
    Topic,
    TopicPrerequisite,
)
from app.domains.learning_paths.entities import LearningPath


class CourseRepository(CrudRepository[Course], Protocol):
    async def get_for_update(self, course_id: int) -> Course | None:
        """Lee el curso bloqueando la fila hasta el fin de la transacción."""
        ...

    async def list_by_status(self, status: str) -> list[Course]: ...


class LearningPathRepository(Protocol):
    async def add(self, path: LearningPath) -> LearningPath: ...

    async def get_by_course(self, course_id: int) -> LearningPath | None: ...

    async def by_course_ids(self, course_ids: list[int]) -> dict[int, LearningPath]: ...

    async def update(self, path_id: int, changes: dict[str, Any]) -> LearningPath | None: ...


class SyllabusRepository(Protocol):
    async def add_document(self, document: SyllabusDocument) -> SyllabusDocument: ...

    async def latest_document(self, course_id: int) -> SyllabusDocument | None: ...

    async def add_extraction(self, extraction: SyllabusExtraction) -> SyllabusExtraction:
        """Registra la extracción ingerida y marca como no vigentes las anteriores del curso."""
        ...

    async def current_extraction(self, course_id: int) -> SyllabusExtraction | None: ...

    async def resolve_ai_job_id(self, public_id: str) -> int | None:
        """`id` interno de `ai_jobs` para el `job_id` del contrato (solo lectura)."""
        ...


class TopicRepository(Protocol):
    async def add(self, topic: Topic) -> Topic: ...

    async def get(self, topic_id: int) -> Topic | None: ...

    async def list_for_course(
        self, course_id: int, *, include_inactive: bool = False
    ) -> list[Topic]:
        """Temas del curso por `position` e id. Con `include_inactive` trae también los borrados."""
        ...

    async def update(self, topic_id: int, changes: dict[str, Any]) -> Topic | None: ...

    async def set_active(self, topic_id: int, active: bool) -> Topic | None: ...


class OutcomeRepository(Protocol):
    async def add(self, outcome: LearningOutcome) -> LearningOutcome: ...

    async def list_for_topics(self, topic_ids: list[int]) -> dict[int, list[LearningOutcome]]:
        """Resultados activos agrupados por tema, en orden de creación."""
        ...

    async def next_code_number(self, topic_id: int) -> int:
        """Siguiente número libre para `lo_t<tema>_<n>`, contando también los inactivos."""
        ...

    async def update(self, outcome_id: int, changes: dict[str, Any]) -> LearningOutcome | None: ...

    async def set_active(self, outcome_id: int, active: bool) -> LearningOutcome | None: ...


class PrerequisiteRepository(Protocol):
    async def list_for_course(self, course_id: int) -> list[TopicPrerequisite]:
        """Aristas activas entre temas activos del curso."""
        ...

    async def upsert(
        self, topic_id: int, prerequisite_topic_id: int, origin: str
    ) -> TopicPrerequisite:
        """Crea la arista o la reactiva si estaba inactiva."""
        ...

    async def set_active(self, edge_id: int, active: bool) -> TopicPrerequisite | None: ...

    async def deactivate_touching(self, topic_id: int) -> None:
        """Inactiva las aristas donde el tema es destino u origen."""
        ...
