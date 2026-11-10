"""Puerto de lectura de observabilidad (todo es de solo lectura)."""

from typing import Protocol

from app.domains.observability.entities import (
    ItemValidityRow,
    LlmCallLog,
    LlmStats,
    LogFilters,
    LogSummary,
    PathScope,
    StepStats,
    VideoTopicRanking,
)


class ObservabilityRepository(Protocol):
    async def search_logs(
        self, filters: LogFilters, *, limit: int, offset: int
    ) -> tuple[list[LlmCallLog], int]: ...

    async def summarize_logs(self, filters: LogFilters) -> LogSummary: ...

    async def scope(
        self, *, owner_user_id: int | None, learning_path_id: int | None
    ) -> list[PathScope]:
        """Rutas visibles: todas (administrador) o las de los cursos del dueño."""
        ...

    async def item_validity(self, course_ids: list[int]) -> list[ItemValidityRow]: ...

    async def grading_pairs(self, course_ids: list[int]) -> list[tuple[float, float]]:
        """`(nota humana, nota del LLM)` de las respuestas con calificación humana."""
        ...

    async def faithfulness(self, course_ids: list[int]) -> tuple[float | None, int]:
        """Promedio de `resources.faithfulness` y cuántas versiones tienen medida."""
        ...

    async def video_rankings(self, course_ids: list[int]) -> list[VideoTopicRanking]: ...

    async def llm_stats(self, course_ids: list[int]) -> LlmStats: ...

    async def step_stats(self, path_ids: list[int]) -> StepStats: ...
