"""Reglas de evaluación humana sobre repositorios en memoria."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import pytest

from app.common.entities import require_id
from app.common.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domains.content.entities import AssessmentItem
from app.domains.courses.entities import Course, Topic
from app.domains.evaluation.entities import (
    AnswerForGrading,
    CourseEvaluator,
    GradableAnswer,
    HumanGrading,
    ItemAnnotation,
    LlmGrade,
)
from app.domains.evaluation.service import (
    AnnotationInput,
    AnnotationService,
    EvaluatorAccess,
    EvaluatorAdminService,
    GradingInput,
    GradingService,
)
from tests.unit.conftest import World, current
from tests.unit.fakes import InMemoryRepository
from tests.unit.fakes_content import InMemoryItems


class InMemoryEvaluators(InMemoryRepository[CourseEvaluator]):
    def __init__(self, courses: InMemoryRepository[Course], instructors: set[int]) -> None:
        super().__init__()
        self._courses = courses
        self._instructors = instructors

    async def find(self, course_id: int, user_id: int) -> CourseEvaluator | None:
        return next(
            (e for e in self.items.values() if e.course_id == course_id and e.user_id == user_id),
            None,
        )

    async def list_for_course(self, course_id: int) -> list[CourseEvaluator]:
        return [e for e in self.items.values() if e.course_id == course_id and e.active]

    async def course_ids_of(self, user_id: int) -> list[int]:
        out = []
        for e in self.items.values():
            course = await self._courses.get(e.course_id)
            if e.user_id == user_id and e.active and course and course.owner_user_id != user_id:
                out.append(e.course_id)
        return out

    async def has_role(self, user_id: int, role_code: str) -> bool:
        return user_id in self._instructors


class InMemoryAnnotations(InMemoryRepository[ItemAnnotation]):
    def __init__(self, items: InMemoryItems) -> None:
        super().__init__()
        self._items = items

    async def find(self, item_id: int, annotator_user_id: int) -> ItemAnnotation | None:
        return next(
            (
                a
                for a in self.items.values()
                if a.assessment_item_id == item_id and a.annotator_user_id == annotator_user_id
            ),
            None,
        )

    async def slots_used(self, item_id: int) -> set[int]:
        return {a.evaluator_slot for a in self.items.values() if a.assessment_item_id == item_id}

    async def queue(
        self, *, course_ids: list[int], annotator_user_id: int, done: bool, limit: int, offset: int
    ) -> tuple[list[AssessmentItem], int]:
        found = []
        for item in self._items.items.values():
            mine = await self.find(require_id(item), annotator_user_id) is not None
            count = len(await self.slots_used(require_id(item)))
            if mine == done and (done or count < 2):
                found.append(item)
        return found[offset : offset + limit], len(found)

    async def own_annotations(
        self, annotator_user_id: int, item_ids: list[int]
    ) -> dict[int, ItemAnnotation]:
        return {
            a.assessment_item_id: a
            for a in self.items.values()
            if a.annotator_user_id == annotator_user_id and a.assessment_item_id in item_ids
        }


class InMemoryGradings(InMemoryRepository[HumanGrading]):
    def __init__(self) -> None:
        super().__init__()
        self.answers: dict[int, GradableAnswer] = {}

    async def find(self, answer_id: int, grader_user_id: int) -> HumanGrading | None:
        return next(
            (
                g
                for g in self.items.values()
                if g.attempt_answer_id == answer_id and g.grader_user_id == grader_user_id
            ),
            None,
        )

    async def queue(
        self, *, course_ids: list[int], grader_user_id: int, sample: str, limit: int, offset: int
    ) -> tuple[list[AnswerForGrading], int]:
        found = [
            g.answer
            for g in self.answers.values()
            if g.answer.course_id in course_ids
            and (sample == "random" or g.answer.review_requested_at is not None)
        ]
        return found[offset : offset + limit], len(found)

    async def graded_count(self, *, course_ids: list[int], grader_user_id: int, sample: str) -> int:
        del course_ids
        return sum(
            1
            for g in self.items.values()
            if g.grader_user_id == grader_user_id and g.sample_type == sample
        )

    async def answer(self, answer_id: int) -> GradableAnswer | None:
        return self.answers.get(answer_id)


OWNER, EVAL_A, EVAL_B, EVAL_C = 2, 10, 11, 12


@dataclass
class EvalWorld:
    base: World
    course_id: int
    item_id: int
    items: InMemoryItems
    evaluators: InMemoryEvaluators
    annotations: InMemoryAnnotations
    gradings: InMemoryGradings
    admin_service: EvaluatorAdminService
    annotation_service: AnnotationService
    grading_service: GradingService

    def user(self, user_id: int) -> Any:
        return current(user_id, "instructor")


@pytest.fixture
async def ew(world: World) -> EvalWorld:
    course = await world.courses.add(Course(owner_user_id=OWNER, name="Curso", status="published"))
    topic = await world.topics.add(Topic(course_id=require_id(course), name="Tema"))
    items = InMemoryItems()
    item = await items.add(
        AssessmentItem(
            topic_id=require_id(topic),
            source="topic_quiz",
            item_type="multiple_choice",
            bloom_level="apply",
            difficulty=2,
            stem="Pregunta",
            options=["a", "b", "c", "d"],
            correct_option="1",
        )
    )
    evaluators = InMemoryEvaluators(world.courses, {EVAL_A, EVAL_B, EVAL_C})
    annotations = InMemoryAnnotations(items)
    gradings = InMemoryGradings()
    access = EvaluatorAccess(evaluators)
    return EvalWorld(
        base=world,
        course_id=require_id(course),
        item_id=require_id(item),
        items=items,
        evaluators=evaluators,
        annotations=annotations,
        gradings=gradings,
        admin_service=EvaluatorAdminService(evaluators, world.courses, world.uow),
        annotation_service=AnnotationService(
            access, annotations, items, world.topics, world.courses, world.uow
        ),
        grading_service=GradingService(access, gradings, world.uow),
    )


ANNOTATION = AnnotationInput(True, True, True, True, "valid", None)


async def test_the_admin_assigns_evaluators_but_not_the_owner_nor_a_learner(ew: EvalWorld) -> None:
    from app.common.exceptions import BusinessRuleError

    admin = ew.base.admin
    created = await ew.admin_service.assign(admin, ew.course_id, EVAL_A)
    assert created.assigned_by_user_id == admin.id
    with pytest.raises(BusinessRuleError):
        await ew.admin_service.assign(admin, ew.course_id, OWNER)
    with pytest.raises(BusinessRuleError):
        await ew.admin_service.assign(admin, ew.course_id, 99)
    with pytest.raises(ConflictError):
        await ew.admin_service.assign(admin, ew.course_id, EVAL_A)
    await ew.admin_service.remove(admin, require_id(created))
    reassigned = await ew.admin_service.assign(admin, ew.course_id, EVAL_A)
    assert reassigned.active is True


async def test_an_instructor_that_does_not_own_the_course_cannot_assign_evaluators(
    ew: EvalWorld,
) -> None:
    with pytest.raises(NotFoundError):
        await ew.admin_service.assign(ew.base.other_instructor, ew.course_id, EVAL_A)


async def test_slots_follow_the_order_and_the_third_evaluator_is_refused(ew: EvalWorld) -> None:
    for evaluator in (EVAL_A, EVAL_B, EVAL_C):
        await ew.admin_service.assign(ew.base.admin, ew.course_id, evaluator)
    first = await ew.annotation_service.annotate(ew.user(EVAL_A), ew.item_id, ANNOTATION)
    second = await ew.annotation_service.annotate(ew.user(EVAL_B), ew.item_id, ANNOTATION)
    assert (first.evaluator_slot, second.evaluator_slot) == (1, 2)
    with pytest.raises(ConflictError) as full:
        await ew.annotation_service.annotate(ew.user(EVAL_C), ew.item_id, ANNOTATION)
    assert full.value.code == "EVALUATOR_SLOTS_FULL"
    with pytest.raises(ConflictError) as repeated:
        await ew.annotation_service.annotate(ew.user(EVAL_A), ew.item_id, ANNOTATION)
    assert repeated.value.code == "ANNOTATION_ALREADY_EXISTS"


async def test_the_queue_shows_only_the_evaluators_own_annotation(ew: EvalWorld) -> None:
    for evaluator in (EVAL_A, EVAL_B):
        await ew.admin_service.assign(ew.base.admin, ew.course_id, evaluator)
    await ew.annotation_service.annotate(
        ew.user(EVAL_A), ew.item_id, replace(ANNOTATION, comment="SECRETO", verdict="invalid")
    )
    entries, total = await ew.annotation_service.queue(
        ew.user(EVAL_B), course_id=None, done=False, limit=10, offset=0
    )
    assert total == 1
    assert entries[0].own_annotation is None
    done, _ = await ew.annotation_service.queue(
        ew.user(EVAL_A), course_id=None, done=True, limit=10, offset=0
    )
    assert done[0].own_annotation is not None
    assert done[0].own_annotation.comment == "SECRETO"


async def test_the_queue_brings_the_topic_the_slot_and_the_progress(ew: EvalWorld) -> None:
    for evaluator in (EVAL_A, EVAL_B):
        await ew.admin_service.assign(ew.base.admin, ew.course_id, evaluator)
    before, _ = await ew.annotation_service.queue(
        ew.user(EVAL_B), course_id=None, done=False, limit=10, offset=0
    )
    assert before[0].topic_name
    assert before[0].evaluator_slot == 1
    assert await ew.annotation_service.annotated_count(ew.user(EVAL_B), course_id=None) == 0

    await ew.annotation_service.annotate(ew.user(EVAL_A), ew.item_id, ANNOTATION)
    pending, _ = await ew.annotation_service.queue(
        ew.user(EVAL_B), course_id=None, done=False, limit=10, offset=0
    )
    assert pending[0].evaluator_slot == 2
    done, _ = await ew.annotation_service.queue(
        ew.user(EVAL_A), course_id=None, done=True, limit=10, offset=0
    )
    assert done[0].evaluator_slot == 1
    assert await ew.annotation_service.annotated_count(ew.user(EVAL_A), course_id=None) == 1


async def test_the_owner_an_admin_and_strangers_cannot_annotate(ew: EvalWorld) -> None:
    await ew.admin_service.assign(ew.base.admin, ew.course_id, EVAL_A)
    for who in (ew.user(OWNER), ew.base.admin):
        with pytest.raises(ForbiddenError) as denied:
            await ew.annotation_service.annotate(who, ew.item_id, ANNOTATION)
        assert denied.value.code == "EVALUATOR_NOT_ASSIGNED"
    with pytest.raises(NotFoundError) as unknown:
        await ew.annotation_service.annotate(ew.user(EVAL_C), ew.item_id, ANNOTATION)
    assert unknown.value.code == "ITEM_NOT_FOUND"
    with pytest.raises(ForbiddenError):
        await ew.annotation_service.queue(
            ew.user(EVAL_C), course_id=None, done=False, limit=1, offset=0
        )
    with pytest.raises(ForbiddenError):
        await ew.annotation_service.queue(
            ew.base.learner, course_id=None, done=False, limit=1, offset=0
        )
    with pytest.raises(ForbiddenError):
        await ew.annotation_service.queue(
            ew.user(EVAL_A), course_id=999, done=False, limit=1, offset=0
        )


def _answer(course_id: int, *, asked: bool = False, grader: str = "llm_judge") -> GradableAnswer:
    return GradableAnswer(
        answer=AnswerForGrading(
            answer_id=1,
            course_id=course_id,
            topic_id=1,
            item_id=1,
            stem="x",
            model_answer="y",
            rubric=[],
            text_answer="z",
            review_requested_at=datetime.now(UTC) if asked else None,
        ),
        grader=grader,
        llm=LlmGrade(score=66.0, is_correct=True, rubric_detail=[], feedback="Bien"),
    )


async def test_grading_returns_the_llm_grade_only_after_saving(ew: EvalWorld) -> None:
    from app.common.exceptions import BusinessRuleError

    await ew.admin_service.assign(ew.base.admin, ew.course_id, EVAL_A)
    ew.gradings.answers[1] = _answer(ew.course_id)
    queue, _ = await ew.grading_service.queue(ew.user(EVAL_A), sample="random", limit=5, offset=0)
    assert not hasattr(queue[0], "llm")
    assert not hasattr(queue[0], "score")
    data = GradingInput([{"criterion": "x", "met": True, "points_awarded": 1}], 80, "random")
    result = await ew.grading_service.grade(ew.user(EVAL_A), 1, data)
    assert result.llm.score == 66.0
    with pytest.raises(ConflictError) as repeated:
        await ew.grading_service.grade(ew.user(EVAL_A), 1, data)
    assert repeated.value.code == "HUMAN_GRADING_ALREADY_EXISTS"
    with pytest.raises(BusinessRuleError):
        await ew.grading_service.grade(
            ew.user(EVAL_A), 1, GradingInput(data.criteria, 80, "learner_request")
        )


async def test_grading_rules_for_owner_strangers_and_non_llm_answers(ew: EvalWorld) -> None:
    from app.common.exceptions import BusinessRuleError

    await ew.admin_service.assign(ew.base.admin, ew.course_id, EVAL_A)
    ew.gradings.answers[1] = _answer(ew.course_id)
    ew.gradings.answers[2] = _answer(ew.course_id, grader="rule")
    data = GradingInput([{"criterion": "x", "met": True, "points_awarded": 1}], 80, "random")
    with pytest.raises(ForbiddenError):
        await ew.grading_service.grade(ew.user(OWNER), 1, data)
    with pytest.raises(NotFoundError):
        await ew.grading_service.grade(ew.user(EVAL_A), 99, data)
    with pytest.raises(BusinessRuleError):
        await ew.grading_service.grade(ew.user(EVAL_A), 2, data)
