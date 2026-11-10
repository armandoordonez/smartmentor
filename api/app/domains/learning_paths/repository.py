"""Puertos de los repositorios de rutas, inscripciones, pasos, intentos extra y alertas."""

from typing import Any, Protocol

from app.domains.courses.entities import Course, Topic
from app.domains.identity.entities import User, UserProfile
from app.domains.learning_paths.entities import (
    Alert,
    AttemptGrant,
    Enrollment,
    LearningPath,
    PathStep,
    TopicNode,
)


class PathRepository(Protocol):
    async def get(self, path_id: int) -> LearningPath | None: ...

    async def update(self, path_id: int, changes: dict[str, Any]) -> LearningPath | None: ...

    async def list_published(self, *, limit: int, offset: int) -> tuple[list[LearningPath], int]:
        """Rutas publicadas y activas, por id."""
        ...


class EnrollmentRepository(Protocol):
    async def add(self, enrollment: Enrollment) -> Enrollment: ...

    async def get(self, enrollment_id: int) -> Enrollment | None: ...

    async def get_for_update(self, enrollment_id: int) -> Enrollment | None:
        """Lee la inscripción bloqueando la fila hasta el fin de la transacción."""
        ...

    async def update(self, enrollment_id: int, changes: dict[str, Any]) -> Enrollment | None: ...

    async def find(self, user_id: int, learning_path_id: int) -> Enrollment | None: ...

    async def list_for_user(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]: ...

    async def list_for_path(self, learning_path_id: int) -> list[Enrollment]: ...

    async def search(
        self,
        *,
        learning_path_id: int | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Enrollment], int]: ...


class PathStepRepository(Protocol):
    async def add(self, step: PathStep) -> PathStep: ...

    async def get(self, step_id: int) -> PathStep | None: ...

    async def update(self, step_id: int, changes: dict[str, Any]) -> PathStep | None: ...

    async def list_for_enrollment(self, enrollment_id: int) -> list[PathStep]:
        """Pasos activos por `step_order`."""
        ...

    async def list_for_enrollments(self, enrollment_ids: list[int]) -> list[PathStep]: ...


class AttemptGrantRepository(Protocol):
    async def add(self, grant: AttemptGrant) -> AttemptGrant: ...

    async def final_attempts_granted(self, enrollment_id: int) -> int:
        """Suma de intentos extra de la evaluación final de la inscripción."""
        ...


class AlertRepository(Protocol):
    async def add(self, alert: Alert) -> Alert: ...

    async def get(self, alert_id: int) -> Alert | None: ...

    async def update(self, alert_id: int, changes: dict[str, Any]) -> Alert | None: ...

    async def list_for_recipient(
        self, user_id: int, *, unread: bool | None, limit: int, offset: int
    ) -> tuple[list[Alert], int]: ...


class PlatformReader(Protocol):
    """Lecturas de otros dominios que necesita la ruta (cursos, temas, usuarios, piloto)."""

    async def course(self, course_id: int) -> Course | None: ...

    async def topic(self, topic_id: int) -> Topic | None: ...

    async def topic_nodes(self, course_id: int) -> list[TopicNode]:
        """Temas activos del curso por `position`, con sus prerrequisitos activos."""
        ...

    async def user(self, user_id: int) -> User | None: ...

    async def profile(self, user_id: int) -> UserProfile | None: ...

    async def consent_in_force(self, user_id: int, consent_type: str) -> bool: ...

    async def pilot_running(self, learning_path_id: int) -> bool: ...

    async def first_admin_id(self) -> int | None:
        """Un administrador activo (destinatario de alertas de cursos «Sin asignar»)."""
        ...
