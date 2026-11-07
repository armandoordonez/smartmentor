"""Repositorios SQLAlchemy de cursos."""

import uuid
from typing import Any, ClassVar

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.courses.entities import (
    Course,
    LearningOutcome,
    SyllabusDocument,
    SyllabusExtraction,
    Topic,
    TopicPrerequisite,
)
from app.domains.courses.models import (
    CourseModel,
    LearningOutcomeModel,
    SyllabusDocumentModel,
    SyllabusExtractionModel,
    TopicModel,
    TopicPrerequisiteModel,
)
from app.domains.learning_paths.entities import LearningPath
from app.domains.learning_paths.models import LearningPathModel


class SqlAlchemyCourseRepository(SqlAlchemyCrudRepository[CourseModel, Course]):
    model = CourseModel
    entity = Course
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "courses_owner_user_id_fk": ("OWNER_NOT_FOUND", "The owner user does not exist."),
        "courses_status_ck": ("INVALID_COURSE_STATUS", "Invalid course status."),
    }

    async def get_for_update(self, course_id: int) -> Course | None:
        row = (
            await self._session.execute(
                select(CourseModel)
                .where(CourseModel.id == course_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_by_status(self, status: str) -> list[Course]:
        rows = (
            (
                await self._session.execute(
                    select(CourseModel)
                    .where(CourseModel.status == status, CourseModel.active.is_(True))
                    .order_by(CourseModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyLearningPathRepository(SqlAlchemyCrudRepository[LearningPathModel, LearningPath]):
    model = LearningPathModel
    entity = LearningPath
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "learning_paths_course_id_fk": ("COURSE_NOT_FOUND", "The course does not exist."),
    }

    async def get_by_course(self, course_id: int) -> LearningPath | None:
        row = (
            (
                await self._session.execute(
                    select(LearningPathModel)
                    .where(LearningPathModel.course_id == course_id)
                    .order_by(LearningPathModel.id)
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def by_course_ids(self, course_ids: list[int]) -> dict[int, LearningPath]:
        if not course_ids:
            return {}
        rows = (
            (
                await self._session.execute(
                    select(LearningPathModel)
                    .where(LearningPathModel.course_id.in_(course_ids))
                    .order_by(LearningPathModel.id.desc())
                )
            )
            .scalars()
            .all()
        )
        # La primera ruta de cada curso gana (se recorre de la más nueva a la más antigua).
        return {row.course_id: self._to_entity(row) for row in rows}


class SqlAlchemySyllabusRepository:
    def __init__(self, session: Any) -> None:
        self._session = session
        self._documents = _DocumentRepository(session)
        self._extractions = _ExtractionRepository(session)

    async def add_document(self, document: SyllabusDocument) -> SyllabusDocument:
        return await self._documents.add(document)

    async def latest_document(self, course_id: int) -> SyllabusDocument | None:
        row = (
            (
                await self._session.execute(
                    select(SyllabusDocumentModel)
                    .where(SyllabusDocumentModel.course_id == course_id)
                    .order_by(SyllabusDocumentModel.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._documents._to_entity(row)

    async def add_extraction(self, extraction: SyllabusExtraction) -> SyllabusExtraction:
        await self._session.execute(
            update(SyllabusExtractionModel)
            .where(
                SyllabusExtractionModel.course_id == extraction.course_id,
                SyllabusExtractionModel.is_current.is_(True),
            )
            .values(is_current=False)
        )
        return await self._extractions.add(extraction)

    async def current_extraction(self, course_id: int) -> SyllabusExtraction | None:
        row = (
            (
                await self._session.execute(
                    select(SyllabusExtractionModel)
                    .where(
                        SyllabusExtractionModel.course_id == course_id,
                        SyllabusExtractionModel.is_current.is_(True),
                    )
                    .order_by(SyllabusExtractionModel.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._extractions.convert(row)

    async def count_extractions(self, document_id: int) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(SyllabusExtractionModel)
                    .where(SyllabusExtractionModel.syllabus_document_id == document_id)
                )
            ).scalar_one()
        )

    async def get_extraction_by_job(
        self, job_id: str, *, for_update: bool = False
    ) -> SyllabusExtraction | None:
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            return None
        query = select(SyllabusExtractionModel).where(SyllabusExtractionModel.ai_job_id == job_uuid)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = (await self._session.execute(query)).scalars().first()
        return None if row is None else self._extractions.convert(row)

    async def save_result(
        self, extraction_id: int, raw_output: dict[str, Any], prompt_version: str
    ) -> SyllabusExtraction | None:
        row = await self._session.get(SyllabusExtractionModel, extraction_id)
        if row is None:
            return None
        row.raw_output = raw_output
        row.prompt_version = prompt_version
        await self._session.flush()
        return self._extractions.convert(row)

    async def pending_extractions(self) -> list[SyllabusExtraction]:
        rows = (
            (
                await self._session.execute(
                    select(SyllabusExtractionModel)
                    .where(
                        SyllabusExtractionModel.is_current.is_(True),
                        SyllabusExtractionModel.ai_job_id.is_not(None),
                        SyllabusExtractionModel.raw_output.is_(None),
                    )
                    .order_by(SyllabusExtractionModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._extractions.convert(row) for row in rows]


class _DocumentRepository(SqlAlchemyCrudRepository[SyllabusDocumentModel, SyllabusDocument]):
    model = SyllabusDocumentModel
    entity = SyllabusDocument


class _ExtractionRepository(SqlAlchemyCrudRepository[SyllabusExtractionModel, SyllabusExtraction]):
    model = SyllabusExtractionModel
    entity = SyllabusExtraction

    def convert(self, row: SyllabusExtractionModel) -> SyllabusExtraction:
        return self._to_entity(row)

    def _to_entity(self, row: SyllabusExtractionModel) -> SyllabusExtraction:
        entity = super()._to_entity(row)
        if entity.ai_job_id is not None:
            entity.ai_job_id = str(entity.ai_job_id)
        return entity

    async def add(self, entity: SyllabusExtraction) -> SyllabusExtraction:
        row = SyllabusExtractionModel(
            course_id=entity.course_id,
            syllabus_document_id=entity.syllabus_document_id,
            ai_job_id=uuid.UUID(entity.ai_job_id) if entity.ai_job_id else None,
            is_current=entity.is_current,
        )
        self._session.add(row)
        await self._flush()
        return self._to_entity(row)


class SqlAlchemyTopicRepository(SqlAlchemyCrudRepository[TopicModel, Topic]):
    model = TopicModel
    entity = Topic
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "topics_course_id_fk": ("COURSE_NOT_FOUND", "The course does not exist."),
        "topics_bloom_level_ck": ("INVALID_BLOOM_LEVEL", "Invalid Bloom level."),
    }

    async def list_for_course(
        self, course_id: int, *, include_inactive: bool = False
    ) -> list[Topic]:
        query = select(TopicModel).where(TopicModel.course_id == course_id)
        if not include_inactive:
            query = query.where(TopicModel.active.is_(True))
        rows = (
            (await self._session.execute(query.order_by(TopicModel.position, TopicModel.id)))
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyOutcomeRepository(SqlAlchemyCrudRepository[LearningOutcomeModel, LearningOutcome]):
    model = LearningOutcomeModel
    entity = LearningOutcome

    async def list_for_topics(self, topic_ids: list[int]) -> dict[int, list[LearningOutcome]]:
        if not topic_ids:
            return {}
        rows = (
            (
                await self._session.execute(
                    select(LearningOutcomeModel)
                    .where(
                        LearningOutcomeModel.topic_id.in_(topic_ids),
                        LearningOutcomeModel.active.is_(True),
                    )
                    .order_by(LearningOutcomeModel.id)
                )
            )
            .scalars()
            .all()
        )
        grouped: dict[int, list[LearningOutcome]] = {}
        for row in rows:
            grouped.setdefault(row.topic_id, []).append(self._to_entity(row))
        return grouped


class SqlAlchemyPrerequisiteRepository(
    SqlAlchemyCrudRepository[TopicPrerequisiteModel, TopicPrerequisite]
):
    model = TopicPrerequisiteModel
    entity = TopicPrerequisite
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "topic_prerequisites_uq": (
            "PREREQUISITE_ALREADY_EXISTS",
            "This prerequisite already exists.",
        ),
        "topic_prerequisites_not_self_ck": (
            "PREREQUISITE_SELF",
            "A topic cannot be its own prerequisite.",
        ),
        "topic_prerequisites_topic_id_fk": ("TOPIC_NOT_FOUND", "The topic does not exist."),
        "topic_prerequisites_prerequisite_topic_id_fk": (
            "PREREQUISITE_TOPIC_NOT_FOUND",
            "The prerequisite topic does not exist.",
        ),
    }

    async def list_for_course(self, course_id: int) -> list[TopicPrerequisite]:
        topic = TopicModel.__table__.alias("t")
        prerequisite = TopicModel.__table__.alias("p")
        rows = (
            (
                await self._session.execute(
                    select(TopicPrerequisiteModel)
                    .join(topic, topic.c.id == TopicPrerequisiteModel.topic_id)
                    .join(
                        prerequisite,
                        prerequisite.c.id == TopicPrerequisiteModel.prerequisite_topic_id,
                    )
                    .where(
                        topic.c.course_id == course_id,
                        topic.c.active.is_(True),
                        prerequisite.c.active.is_(True),
                        TopicPrerequisiteModel.active.is_(True),
                    )
                    .order_by(TopicPrerequisiteModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]

    async def upsert(
        self, topic_id: int, prerequisite_topic_id: int, origin: str
    ) -> TopicPrerequisite:
        row = (
            await self._session.execute(
                pg_insert(TopicPrerequisiteModel)
                .values(
                    topic_id=topic_id, prerequisite_topic_id=prerequisite_topic_id, origin=origin
                )
                .on_conflict_do_update(
                    index_elements=["topic_id", "prerequisite_topic_id"],
                    set_={"active": True, "origin": origin},
                )
                .returning(TopicPrerequisiteModel)
            )
        ).scalar_one()
        return self._to_entity(row)

    async def deactivate_touching(self, topic_id: int) -> None:
        await self._session.execute(
            update(TopicPrerequisiteModel)
            .where(
                (TopicPrerequisiteModel.topic_id == topic_id)
                | (TopicPrerequisiteModel.prerequisite_topic_id == topic_id)
            )
            .values(active=False)
        )
