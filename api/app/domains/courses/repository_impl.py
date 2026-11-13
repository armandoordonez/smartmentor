"""Repositorios SQLAlchemy de cursos."""

import uuid
from typing import ClassVar

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.ai_gateway.models import AiJobModel
from app.domains.courses.entities import (
    Course,
    CourseCounts,
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
from app.domains.learning_paths.models import EnrollmentModel, LearningPathModel
from app.domains.learning_paths.states import EnrollmentStatus


class SqlAlchemyCourseRepository(SqlAlchemyCrudRepository[CourseModel, Course]):
    model = CourseModel
    entity = Course
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "courses_owner_user_id_fk": ("OWNER_NOT_FOUND", "The owner user does not exist."),
        "courses_status_ck": ("INVALID_COURSE_STATUS", "Invalid course status."),
    }

    async def get_for_update(self, course_id: int) -> Course | None:
        # FOR NO KEY UPDATE (y no FOR UPDATE): serializa los cambios de la fila igual, pero deja que
        # `ai/` valide la llave foránea de `ai_jobs` desde su conexión mientras la API espera su
        # respuesta. Con FOR UPDATE se bloquean entre sí y la API responde 503 a los 10 s.
        row = (
            await self._session.execute(
                select(CourseModel)
                .where(CourseModel.id == course_id)
                .with_for_update(key_share=True)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def counts(self, course_ids: list[int]) -> dict[int, CourseCounts]:
        if not course_ids:
            return {}
        topics = (
            await self._session.execute(
                select(TopicModel.course_id, func.count())
                .where(TopicModel.course_id.in_(course_ids), TopicModel.active.is_(True))
                .group_by(TopicModel.course_id)
            )
        ).all()
        enrolled = (
            await self._session.execute(
                select(LearningPathModel.course_id, func.count(EnrollmentModel.id))
                .join(EnrollmentModel, EnrollmentModel.learning_path_id == LearningPathModel.id)
                .where(
                    LearningPathModel.course_id.in_(course_ids),
                    LearningPathModel.active.is_(True),
                    EnrollmentModel.active.is_(True),
                    EnrollmentModel.status != EnrollmentStatus.WITHDRAWN,
                )
                .group_by(LearningPathModel.course_id)
            )
        ).all()
        by_topics = {int(course_id): int(n) for course_id, n in topics}
        by_enrolled = {int(course_id): int(n) for course_id, n in enrolled}
        return {
            course_id: CourseCounts(by_topics.get(course_id, 0), by_enrolled.get(course_id, 0))
            for course_id in by_topics.keys() | by_enrolled.keys()
        }

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


class _DocumentRepository(SqlAlchemyCrudRepository[SyllabusDocumentModel, SyllabusDocument]):
    model = SyllabusDocumentModel
    entity = SyllabusDocument


class _ExtractionRepository(SqlAlchemyCrudRepository[SyllabusExtractionModel, SyllabusExtraction]):
    model = SyllabusExtractionModel
    entity = SyllabusExtraction


class SqlAlchemySyllabusRepository:
    def __init__(self, session: AsyncSession) -> None:
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
        return None if row is None else self._documents.to_entity(row)

    async def add_extraction(self, extraction: SyllabusExtraction) -> SyllabusExtraction:
        # Un solo vigente por curso (índice único parcial): se retira el anterior primero.
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
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._extractions.to_entity(row)

    async def resolve_ai_job_id(self, public_id: str) -> int | None:
        try:
            job_uuid = uuid.UUID(public_id)
        except ValueError:
            return None
        found = (
            await self._session.execute(
                select(AiJobModel.id).where(AiJobModel.public_id == job_uuid)
            )
        ).scalar_one_or_none()
        return None if found is None else int(found)


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

    async def next_code_number(self, topic_id: int) -> int:
        codes = (
            (
                await self._session.execute(
                    select(LearningOutcomeModel.code).where(
                        LearningOutcomeModel.topic_id == topic_id
                    )
                )
            )
            .scalars()
            .all()
        )
        used = [int(c.rsplit("_", 1)[1]) for c in codes if c.rsplit("_", 1)[-1].isdigit()]
        return max(used, default=0) + 1

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
