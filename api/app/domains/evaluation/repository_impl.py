"""Repositorios SQLAlchemy de evaluación humana."""

from typing import Any, ClassVar

from sqlalchemy import bindparam, func, select, text

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.content.entities import AssessmentItem
from app.domains.content.models import AssessmentItemModel
from app.domains.content.repository_impl import SqlAlchemyItemRepository
from app.domains.courses.models import CourseModel, TopicModel
from app.domains.evaluation.entities import (
    AnswerForGrading,
    CourseEvaluator,
    GradableAnswer,
    HumanGrading,
    ItemAnnotation,
    LlmGrade,
)
from app.domains.evaluation.models import (
    CourseEvaluatorModel,
    HumanGradingModel,
    ItemAnnotationModel,
)

_ANNOTATABLE = ("pending_review", "approved")


class SqlAlchemyEvaluatorRepository(
    SqlAlchemyCrudRepository[CourseEvaluatorModel, CourseEvaluator]
):
    model = CourseEvaluatorModel
    entity = CourseEvaluator
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "course_evaluators_course_user_uq": (
            "CONFLICT",
            "The user is already an evaluator of the course.",
        ),
        "course_evaluators_user_id_fk": ("USER_NOT_FOUND", "The user does not exist."),
    }

    async def find(self, course_id: int, user_id: int) -> CourseEvaluator | None:
        row = (
            (
                await self._session.execute(
                    select(CourseEvaluatorModel).where(
                        CourseEvaluatorModel.course_id == course_id,
                        CourseEvaluatorModel.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def list_for_course(self, course_id: int) -> list[CourseEvaluator]:
        rows = (
            (
                await self._session.execute(
                    select(CourseEvaluatorModel)
                    .where(
                        CourseEvaluatorModel.course_id == course_id,
                        CourseEvaluatorModel.active.is_(True),
                    )
                    .order_by(CourseEvaluatorModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows]

    async def course_ids_of(self, user_id: int) -> list[int]:
        rows = await self._session.execute(
            select(CourseEvaluatorModel.course_id)
            .join(CourseModel, CourseModel.id == CourseEvaluatorModel.course_id)
            .where(
                CourseEvaluatorModel.user_id == user_id,
                CourseEvaluatorModel.active.is_(True),
                CourseModel.active.is_(True),
                CourseModel.owner_user_id.is_distinct_from(user_id),
            )
            .order_by(CourseEvaluatorModel.course_id)
        )
        return [int(r) for r in rows.scalars()]

    async def has_role(self, user_id: int, role_code: str) -> bool:
        found = (
            await self._session.execute(
                text(
                    "SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
                    "JOIN users u ON u.id = ur.user_id "
                    "WHERE ur.user_id = :u AND r.code = :code AND ur.active AND r.active "
                    "AND u.active LIMIT 1"
                ),
                {"u": user_id, "code": role_code},
            )
        ).first()
        return found is not None


class SqlAlchemyAnnotationRepository(SqlAlchemyCrudRepository[ItemAnnotationModel, ItemAnnotation]):
    model = ItemAnnotationModel
    entity = ItemAnnotation
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "item_annotations_item_annotator_uq": (
            "ANNOTATION_ALREADY_EXISTS",
            "The evaluator already annotated the item.",
        ),
    }

    async def find(self, item_id: int, annotator_user_id: int) -> ItemAnnotation | None:
        row = (
            (
                await self._session.execute(
                    select(ItemAnnotationModel).where(
                        ItemAnnotationModel.assessment_item_id == item_id,
                        ItemAnnotationModel.annotator_user_id == annotator_user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def slots_used(self, item_id: int) -> set[int]:
        rows = await self._session.execute(
            select(ItemAnnotationModel.evaluator_slot).where(
                ItemAnnotationModel.assessment_item_id == item_id,
                ItemAnnotationModel.active.is_(True),
            )
        )
        return {int(r) for r in rows.scalars()}

    async def queue(
        self, *, course_ids: list[int], annotator_user_id: int, done: bool, limit: int, offset: int
    ) -> tuple[list[AssessmentItem], int]:
        mine = (
            select(ItemAnnotationModel.id)
            .where(
                ItemAnnotationModel.assessment_item_id == AssessmentItemModel.id,
                ItemAnnotationModel.annotator_user_id == annotator_user_id,
                ItemAnnotationModel.active.is_(True),
            )
            .exists()
        )
        total_annotations = (
            select(func.count())
            .select_from(ItemAnnotationModel)
            .where(
                ItemAnnotationModel.assessment_item_id == AssessmentItemModel.id,
                ItemAnnotationModel.active.is_(True),
            )
            .scalar_subquery()
        )
        conditions: list[Any] = [
            TopicModel.course_id.in_(course_ids),
            AssessmentItemModel.active.is_(True),
            AssessmentItemModel.review_status.in_(_ANNOTATABLE),
            mine if done else ~mine,
        ]
        if not done:
            conditions.append(total_annotations < 2)
        base = (
            select(AssessmentItemModel)
            .join(TopicModel, TopicModel.id == AssessmentItemModel.topic_id)
            .where(*conditions)
        )
        total = (
            await self._session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    base.order_by(AssessmentItemModel.id).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        converter = SqlAlchemyItemRepository(self._session)
        return [converter.to_entity(r) for r in rows], int(total)

    async def own_annotations(
        self, annotator_user_id: int, item_ids: list[int]
    ) -> dict[int, ItemAnnotation]:
        if not item_ids:
            return {}
        rows = (
            (
                await self._session.execute(
                    select(ItemAnnotationModel).where(
                        ItemAnnotationModel.annotator_user_id == annotator_user_id,
                        ItemAnnotationModel.assessment_item_id.in_(item_ids),
                        ItemAnnotationModel.active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        return {r.assessment_item_id: self._to_entity(r) for r in rows}


_QUEUE_FROM = """
FROM attempt_answers aa
JOIN assessment_items i ON i.id = aa.assessment_item_id
JOIN topics t ON t.id = i.topic_id
WHERE t.course_id IN :courses
  AND aa.active AND i.item_type = 'short_answer'
  AND aa.grader = 'llm_judge' AND aa.text_answer IS NOT NULL
  AND (:sample = 'random' OR aa.review_requested_at IS NOT NULL)
  AND NOT EXISTS (
      SELECT 1 FROM human_gradings h
      WHERE h.attempt_answer_id = aa.id AND h.grader_user_id = :me AND h.active)
"""


class SqlAlchemyGradingRepository(SqlAlchemyCrudRepository[HumanGradingModel, HumanGrading]):
    model = HumanGradingModel
    entity = HumanGrading
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "human_gradings_answer_grader_uq": (
            "HUMAN_GRADING_ALREADY_EXISTS",
            "The evaluator already graded the answer.",
        ),
    }

    async def find(self, answer_id: int, grader_user_id: int) -> HumanGrading | None:
        row = (
            (
                await self._session.execute(
                    select(HumanGradingModel).where(
                        HumanGradingModel.attempt_answer_id == answer_id,
                        HumanGradingModel.grader_user_id == grader_user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def queue(
        self,
        *,
        course_ids: list[int],
        grader_user_id: int,
        sample: str,
        limit: int,
        offset: int,
    ) -> tuple[list[AnswerForGrading], int]:
        params = {"courses": course_ids, "sample": sample, "me": grader_user_id}
        count = text("SELECT count(*) " + _QUEUE_FROM).bindparams(
            bindparam("courses", expanding=True)
        )
        total = (await self._session.execute(count, params)).scalar_one()
        # La muestra aleatoria es reproducible: el mismo orden para todos los evaluadores del
        # curso (hash del id de la respuesta y del curso), sin sembrar nada en la base.
        order = (
            "md5(aa.id::text || t.course_id::text), aa.id"
            if sample == "random"
            else "aa.review_requested_at, aa.id"
        )
        select_sql = text(
            "SELECT aa.id AS answer_id, t.course_id, t.id AS topic_id, i.id AS item_id, "
            "i.stem, i.model_answer, i.rubric, aa.text_answer, aa.review_requested_at "
            + _QUEUE_FROM
            + f" ORDER BY {order} LIMIT :limit OFFSET :offset"
        ).bindparams(bindparam("courses", expanding=True))
        rows = (
            await self._session.execute(select_sql, {**params, "limit": limit, "offset": offset})
        ).mappings()
        return [_answer(r) for r in rows], int(total)

    async def answer(self, answer_id: int) -> GradableAnswer | None:
        row = (
            (
                await self._session.execute(
                    text(
                        "SELECT aa.id AS answer_id, t.course_id, t.id AS topic_id, "
                        "i.id AS item_id, i.stem, i.model_answer, i.rubric, i.item_type, "
                        "aa.text_answer, aa.review_requested_at, aa.grader, aa.score, "
                        "aa.is_correct, aa.rubric_detail, aa.feedback "
                        "FROM attempt_answers aa "
                        "JOIN assessment_items i ON i.id = aa.assessment_item_id "
                        "JOIN topics t ON t.id = i.topic_id "
                        "WHERE aa.id = :id AND aa.active AND i.item_type = 'short_answer'"
                    ),
                    {"id": answer_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return GradableAnswer(
            answer=_answer(row),
            grader=row["grader"],
            llm=LlmGrade(
                score=float(row["score"]) if row["score"] is not None else None,
                is_correct=row["is_correct"],
                rubric_detail=row["rubric_detail"],
                feedback=row["feedback"],
            ),
        )


def _answer(row: Any) -> AnswerForGrading:
    return AnswerForGrading(
        answer_id=int(row["answer_id"]),
        course_id=int(row["course_id"]),
        topic_id=int(row["topic_id"]),
        item_id=int(row["item_id"]),
        stem=row["stem"],
        model_answer=row["model_answer"],
        rubric=list(row["rubric"] or []),
        text_answer=row["text_answer"],
        review_requested_at=row["review_requested_at"],
    )
