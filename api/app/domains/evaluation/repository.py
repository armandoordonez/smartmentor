"""Puertos de los repositorios de evaluación humana."""

from typing import Any, Protocol

from app.domains.content.entities import AssessmentItem
from app.domains.evaluation.entities import (
    AnswerForGrading,
    CourseEvaluator,
    GradableAnswer,
    HumanGrading,
    ItemAnnotation,
)


class EvaluatorRepository(Protocol):
    async def add(self, evaluator: CourseEvaluator) -> CourseEvaluator: ...

    async def get(self, evaluator_id: int) -> CourseEvaluator | None: ...

    async def find(self, course_id: int, user_id: int) -> CourseEvaluator | None:
        """La asignación (activa o no) de ese usuario en ese curso."""
        ...

    async def list_for_course(self, course_id: int) -> list[CourseEvaluator]: ...

    async def update(
        self, evaluator_id: int, changes: dict[str, Any]
    ) -> CourseEvaluator | None: ...

    async def course_ids_of(self, user_id: int) -> list[int]:
        """Cursos donde el usuario es evaluador activo (sin los que él mismo posee)."""
        ...

    async def has_role(self, user_id: int, role_code: str) -> bool: ...


class AnnotationRepository(Protocol):
    async def add(self, annotation: ItemAnnotation) -> ItemAnnotation: ...

    async def find(self, item_id: int, annotator_user_id: int) -> ItemAnnotation | None: ...

    async def slots_used(self, item_id: int) -> set[int]: ...

    async def queue(
        self, *, course_ids: list[int], annotator_user_id: int, done: bool, limit: int, offset: int
    ) -> tuple[list[AssessmentItem], int]:
        """Ítems por anotar (o ya anotados por el evaluador); nunca trae anotaciones ajenas."""
        ...

    async def own_annotations(
        self, annotator_user_id: int, item_ids: list[int]
    ) -> dict[int, ItemAnnotation]: ...


class GradingRepository(Protocol):
    async def add(self, grading: HumanGrading) -> HumanGrading: ...

    async def find(self, answer_id: int, grader_user_id: int) -> HumanGrading | None: ...

    async def queue(
        self,
        *,
        course_ids: list[int],
        grader_user_id: int,
        sample: str,
        limit: int,
        offset: int,
    ) -> tuple[list[AnswerForGrading], int]: ...

    async def graded_count(
        self, *, course_ids: list[int], grader_user_id: int, sample: str
    ) -> int: ...

    async def answer(self, answer_id: int) -> GradableAnswer | None: ...
