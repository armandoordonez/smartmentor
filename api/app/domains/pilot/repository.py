"""Puertos de los repositorios del piloto."""

from typing import Any, Protocol

from app.domains.pilot.entities import ContentFacts, Pilot, PilotEnrollment


class PilotRepository(Protocol):
    async def add(self, pilot: Pilot) -> Pilot: ...

    async def get(self, pilot_id: int) -> Pilot | None: ...

    async def get_for_update(self, pilot_id: int) -> Pilot | None: ...

    async def update(self, pilot_id: int, changes: dict[str, Any]) -> Pilot | None: ...

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[Pilot], int]: ...

    async def open_for_path(self, learning_path_id: int, *, excluding: int | None) -> Pilot | None:
        """Otro piloto de la ruta que aún no cerró."""
        ...


class PilotPopulation(Protocol):
    """Lectura y asignación de brazos sobre las inscripciones de la ruta (tabla `enrollments`)."""

    async def path_course(self, learning_path_id: int) -> tuple[int, float] | None:
        """`(course_id, mastery_skip_threshold)` de la ruta, o `None` si no existe."""
        ...

    async def enrollments(self, learning_path_id: int) -> list[PilotEnrollment]:
        """Inscripciones vigentes (no retiradas ni abandonadas) con su consentimiento de piloto."""
        ...

    async def assign_arms(self, learning_path_id: int, arms: dict[int, str]) -> None:
        """Deja `pilot_arm` y `analysis_included` según `arms`; el resto de la ruta, sin brazo."""
        ...

    async def clear_arms(self, learning_path_id: int) -> None: ...

    async def arm_counts(self, learning_path_id: int) -> dict[str, int]: ...

    async def content_facts(self, course_id: int) -> ContentFacts: ...
