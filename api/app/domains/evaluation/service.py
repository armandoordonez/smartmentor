"""Evaluación humana: evaluadores por curso, anotación ciega de ítems y calificación a mano.

Reglas (DEF-15, DEF-24, D5b, D5c):

- Evaluador = instructor asignado en `course_evaluators` a un curso que **no** es suyo. El dueño del
  curso no evalúa sus propios ítems y un administrador sin esa asignación tampoco.
- Anotación ciega: la cola y las respuestas solo traen la anotación del propio evaluador.
- La nota del LLM se devuelve solo después de guardar la calificación humana.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.common.constants import RoleCode
from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.domains.content.constants import ReviewStatus
from app.domains.content.entities import AssessmentItem
from app.domains.content.repository import ItemRepository
from app.domains.courses.repository import CourseRepository, TopicRepository
from app.domains.courses.service import load_course
from app.domains.evaluation.entities import (
    AnswerForGrading,
    CourseEvaluator,
    HumanGrading,
    ItemAnnotation,
    LlmGrade,
)
from app.domains.evaluation.repository import (
    AnnotationRepository,
    EvaluatorRepository,
    GradingRepository,
)
from app.domains.identity.authentication import CurrentUser

MAX_EVALUATORS_PER_ITEM = 2


class EvaluatorAccess:
    """Quién puede evaluar qué: los cursos donde el usuario es evaluador asignado."""

    def __init__(self, evaluators: EvaluatorRepository) -> None:
        self._evaluators = evaluators

    async def courses_of(self, user: CurrentUser, course_id: int | None = None) -> list[int]:
        if not user.has_any_role(RoleCode.INSTRUCTOR):
            raise ForbiddenError("Only instructors can evaluate.", code="EVALUATOR_NOT_ASSIGNED")
        courses = await self._evaluators.course_ids_of(user.id)
        if course_id is not None:
            courses = [c for c in courses if c == course_id]
        if not courses:
            raise ForbiddenError(
                "You are not assigned as an evaluator of any course.",
                code="EVALUATOR_NOT_ASSIGNED",
            )
        return courses


# --- Evaluadores por curso (admin) -------------------------------------------------------------


class EvaluatorAdminService:
    def __init__(
        self,
        evaluators: EvaluatorRepository,
        courses: CourseRepository,
        uow: UnitOfWork,
    ) -> None:
        self._evaluators = evaluators
        self._courses = courses
        self._uow = uow

    async def list_for_course(self, user: CurrentUser, course_id: int) -> list[CourseEvaluator]:
        await load_course(self._courses, user, course_id)
        return await self._evaluators.list_for_course(course_id)

    async def assign(
        self, user: CurrentUser, course_id: int, evaluator_user_id: int
    ) -> CourseEvaluator:
        course = await load_course(self._courses, user, course_id)
        if course.owner_user_id == evaluator_user_id:
            raise BusinessRuleError(
                "The course owner cannot be an evaluator of the same course.",
                code="BUSINESS_RULE_VIOLATION",
            )
        if not await self._evaluators.has_role(evaluator_user_id, RoleCode.INSTRUCTOR):
            raise BusinessRuleError(
                "An evaluator must be an active instructor.", code="BUSINESS_RULE_VIOLATION"
            )
        existing = await self._evaluators.find(course_id, evaluator_user_id)
        if existing is not None and existing.active:
            raise ConflictError("The user is already an evaluator of the course.")
        if existing is not None:
            reactivated = await self._evaluators.update(
                require_id(existing), {"active": True, "assigned_by_user_id": user.id}
            )
            await self._uow.commit()
            return reactivated or existing
        created = await self._evaluators.add(
            CourseEvaluator(
                course_id=course_id, user_id=evaluator_user_id, assigned_by_user_id=user.id
            )
        )
        await self._uow.commit()
        return created

    async def remove(self, user: CurrentUser, evaluator_id: int) -> CourseEvaluator:
        found = await self._evaluators.get(evaluator_id)
        if found is None or not found.active:
            raise NotFoundError("Course evaluator", evaluator_id)
        await load_course(self._courses, user, found.course_id)
        updated = await self._evaluators.update(evaluator_id, {"active": False})
        await self._uow.commit()
        return updated or found


# --- Anotación ciega (D5b) --------------------------------------------------------------------


@dataclass(frozen=True)
class AnnotationQueueEntry:
    item: AssessmentItem
    own_annotation: ItemAnnotation | None


@dataclass(frozen=True)
class AnnotationInput:
    single_correct: bool | None
    clear_stem: bool | None
    bloom_ok: bool | None
    plausible_distractors: bool | None
    verdict: str
    comment: str | None


class AnnotationService:
    def __init__(
        self,
        access: EvaluatorAccess,
        annotations: AnnotationRepository,
        items: ItemRepository,
        topics: TopicRepository,
        courses: CourseRepository,
        uow: UnitOfWork,
    ) -> None:
        self._access = access
        self._annotations = annotations
        self._items = items
        self._topics = topics
        self._courses = courses
        self._uow = uow

    async def queue(
        self,
        user: CurrentUser,
        *,
        course_id: int | None,
        done: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[AnnotationQueueEntry], int]:
        courses = await self._access.courses_of(user, course_id)
        items, total = await self._annotations.queue(
            course_ids=courses, annotator_user_id=user.id, done=done, limit=limit, offset=offset
        )
        own = await self._annotations.own_annotations(user.id, [require_id(i) for i in items])
        return [AnnotationQueueEntry(i, own.get(require_id(i))) for i in items], total

    async def annotate(
        self, user: CurrentUser, item_id: int, data: AnnotationInput
    ) -> ItemAnnotation:
        item = await self._items.get(item_id)
        topic = await self._topics.get(item.topic_id) if item is not None else None
        course = await self._courses.get(topic.course_id) if topic is not None else None
        if item is None or not item.active or topic is None or course is None:
            raise NotFoundError("Item", item_id, code="ITEM_NOT_FOUND")
        assigned = require_id(course) in await self._evaluator_courses(user)
        if not assigned:
            if course.owner_user_id == user.id or user.has_any_role(RoleCode.ADMIN):
                # Quien ve el ítem por ser suyo sabe que existe: se le dice por qué no puede.
                raise ForbiddenError(
                    "You cannot evaluate the items of your own course.",
                    code="EVALUATOR_NOT_ASSIGNED",
                )
            raise NotFoundError("Item", item_id, code="ITEM_NOT_FOUND")
        locked = await self._items.get_for_update(item_id) or item
        if locked.review_status not in (ReviewStatus.PENDING_REVIEW, ReviewStatus.APPROVED):
            raise InvalidStateTransitionError(
                f"An item that is {locked.review_status} cannot be annotated."
            )
        if await self._annotations.find(item_id, user.id) is not None:
            raise ConflictError(
                "You already annotated this item.", code="ANNOTATION_ALREADY_EXISTS"
            )
        used = await self._annotations.slots_used(item_id)
        free = [s for s in (1, 2) if s not in used]
        if not free or len(used) >= MAX_EVALUATORS_PER_ITEM:
            raise ConflictError(
                "The item already has its two evaluators.", code="EVALUATOR_SLOTS_FULL"
            )
        created = await self._annotations.add(
            ItemAnnotation(
                assessment_item_id=item_id,
                annotator_user_id=user.id,
                evaluator_slot=free[0],
                single_correct=data.single_correct,
                clear_stem=data.clear_stem,
                bloom_ok=data.bloom_ok,
                plausible_distractors=data.plausible_distractors,
                verdict=data.verdict,
                comment=data.comment,
            )
        )
        await self._uow.commit()
        return created

    async def _evaluator_courses(self, user: CurrentUser) -> list[int]:
        try:
            return await self._access.courses_of(user)
        except ForbiddenError:
            return []


# --- Calificación humana (D5c) ----------------------------------------------------------------


@dataclass(frozen=True)
class GradingInput:
    criteria: list[dict[str, Any]]
    score: float
    sample_type: str


@dataclass(frozen=True)
class GradingResult:
    grading: HumanGrading
    llm: LlmGrade


class ReviewAlerts(Protocol):
    """Lo implementa el dominio de rutas: cierra la alerta `review_requested` ya atendida."""

    async def mark_review_read_for_answer(self, attempt_answer_id: int) -> None: ...


class GradingService:
    def __init__(
        self,
        access: EvaluatorAccess,
        gradings: GradingRepository,
        uow: UnitOfWork,
        review_alerts: ReviewAlerts | None = None,
    ) -> None:
        self._access = access
        self._gradings = gradings
        self._uow = uow
        self._review_alerts = review_alerts

    async def queue(
        self, user: CurrentUser, *, sample: str, limit: int, offset: int
    ) -> tuple[list[AnswerForGrading], int]:
        courses = await self._access.courses_of(user)
        return await self._gradings.queue(
            course_ids=courses, grader_user_id=user.id, sample=sample, limit=limit, offset=offset
        )

    async def grade(self, user: CurrentUser, answer_id: int, data: GradingInput) -> GradingResult:
        try:
            courses = await self._access.courses_of(user)
        except ForbiddenError:
            courses = []
        found = await self._gradings.answer(answer_id)
        if found is None or found.answer.course_id not in courses:
            if not courses:
                raise ForbiddenError(
                    "You are not assigned as an evaluator.", code="EVALUATOR_NOT_ASSIGNED"
                )
            raise NotFoundError("Attempt answer", answer_id)
        if found.grader != "llm_judge":
            raise BusinessRuleError(
                "Only short answers graded by the LLM can be graded by hand.",
                code="BUSINESS_RULE_VIOLATION",
            )
        if data.sample_type == "learner_request" and found.answer.review_requested_at is None:
            raise BusinessRuleError(
                "The learner did not ask for a review of this answer.",
                code="BUSINESS_RULE_VIOLATION",
            )
        if await self._gradings.find(answer_id, user.id) is not None:
            raise ConflictError(
                "You already graded this answer.", code="HUMAN_GRADING_ALREADY_EXISTS"
            )
        created = await self._gradings.add(
            HumanGrading(
                attempt_answer_id=answer_id,
                grader_user_id=user.id,
                sample_type=data.sample_type,
                criteria=data.criteria,
                score=data.score,
            )
        )
        if data.sample_type == "learner_request" and self._review_alerts is not None:
            await self._review_alerts.mark_review_read_for_answer(answer_id)
        await self._uow.commit()
        return GradingResult(created, found.llm)
