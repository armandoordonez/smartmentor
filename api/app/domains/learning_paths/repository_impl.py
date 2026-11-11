"""Repositorios SQLAlchemy de rutas, inscripciones, pasos, intentos extra y alertas."""

from typing import Any, ClassVar

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import CourseStatus
from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.courses.entities import Course, Topic
from app.domains.courses.models import CourseModel, TopicPrerequisiteModel
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.identity.entities import User, UserProfile
from app.domains.identity.repository_impl import (
    SqlAlchemyConsentRepository,
    SqlAlchemyProfileRepository,
    SqlAlchemyUserRepository,
)
from app.domains.learning_paths.entities import (
    Alert,
    AttemptGrant,
    Enrollment,
    LearningPath,
    PathStep,
    TopicNode,
)
from app.domains.learning_paths.models import (
    AlertModel,
    AttemptGrantModel,
    EnrollmentModel,
    LearningPathModel,
    PathStepModel,
)


class SqlAlchemyPathRepository(SqlAlchemyLearningPathRepository):
    async def list_published(self, *, limit: int, offset: int) -> tuple[list[LearningPath], int]:
        # Un curso archivado sale del catálogo aunque su ruta siga publicada (estados.md).
        conditions = [
            LearningPathModel.status == "published",
            LearningPathModel.active.is_(True),
            LearningPathModel.course_id.in_(
                select(CourseModel.id).where(
                    CourseModel.status != CourseStatus.ARCHIVED, CourseModel.active.is_(True)
                )
            ),
        ]
        total = (
            await self._session.execute(
                select(func.count()).select_from(LearningPathModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(LearningPathModel)
                    .where(*conditions)
                    .order_by(LearningPathModel.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows], total


class SqlAlchemyEnrollmentRepository(SqlAlchemyCrudRepository[EnrollmentModel, Enrollment]):
    model = EnrollmentModel
    entity = Enrollment
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "enrollments_user_path_uq": (
            "ENROLLMENT_ALREADY_EXISTS",
            "The learner already has an enrollment in this learning path.",
        ),
        "enrollments_status_ck": ("INVALID_STATE_TRANSITION", "Invalid enrollment status."),
    }

    async def get_for_update(self, enrollment_id: int) -> Enrollment | None:
        row = (
            await self._session.execute(
                select(EnrollmentModel)
                .where(EnrollmentModel.id == enrollment_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def find(self, user_id: int, learning_path_id: int) -> Enrollment | None:
        row = (
            await self._session.execute(
                select(EnrollmentModel).where(
                    EnrollmentModel.user_id == user_id,
                    EnrollmentModel.learning_path_id == learning_path_id,
                )
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_for_user(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]:
        return await self.search_by(
            {"user_id": user_id, "active": True}, limit=limit, offset=offset
        )

    async def list_for_path(self, learning_path_id: int) -> list[Enrollment]:
        items, _ = await self.search_by(
            {"learning_path_id": learning_path_id, "active": True}, limit=10_000, offset=0
        )
        return items

    async def search(  # type: ignore[override]
        self,
        *,
        learning_path_id: int | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Enrollment], int]:
        filters: dict[str, Any] = {"active": True}
        if learning_path_id is not None:
            filters["learning_path_id"] = learning_path_id
        if status is not None:
            filters["status"] = status
        return await self.search_by(filters, limit=limit, offset=offset)

    async def search_by(
        self, filters: dict[str, Any], *, limit: int, offset: int
    ) -> tuple[list[Enrollment], int]:
        return await SqlAlchemyCrudRepository.search(
            self,
            filters={k: v for k, v in filters.items() if k != "active"},
            active=filters.get("active"),
            limit=limit,
            offset=offset,
        )


class SqlAlchemyPathStepRepository(SqlAlchemyCrudRepository[PathStepModel, PathStep]):
    model = PathStepModel
    entity = PathStep
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "path_steps_enrollment_topic_uq": ("CONFLICT", "The step already exists."),
    }

    async def list_for_enrollment(self, enrollment_id: int) -> list[PathStep]:
        return await self.list_for_enrollments([enrollment_id])

    async def list_for_enrollments(self, enrollment_ids: list[int]) -> list[PathStep]:
        if not enrollment_ids:
            return []
        rows = (
            (
                await self._session.execute(
                    select(PathStepModel)
                    .where(
                        PathStepModel.enrollment_id.in_(enrollment_ids),
                        PathStepModel.active.is_(True),
                    )
                    .order_by(PathStepModel.enrollment_id, PathStepModel.step_order)
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyAttemptGrantRepository(SqlAlchemyCrudRepository[AttemptGrantModel, AttemptGrant]):
    model = AttemptGrantModel
    entity = AttemptGrant
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "attempt_grants_attempts_ck": ("VALIDATION_ERROR", "attempts must be at least 1."),
    }

    async def final_attempts_granted(self, enrollment_id: int) -> int:
        total = (
            await self._session.execute(
                select(func.coalesce(func.sum(AttemptGrantModel.attempts), 0)).where(
                    AttemptGrantModel.enrollment_id == enrollment_id,
                    AttemptGrantModel.active.is_(True),
                )
            )
        ).scalar_one()
        return int(total)


class SqlAlchemyAlertRepository(SqlAlchemyCrudRepository[AlertModel, Alert]):
    model = AlertModel
    entity = Alert

    async def mark_review_read_for_answer(self, attempt_answer_id: int) -> None:
        """Marca leída la alerta `review_requested` de esa respuesta (ya se calificó a mano)."""
        await self._session.execute(
            text(
                "UPDATE alerts al SET read_at = now() FROM attempt_answers aa "
                "JOIN assessment_attempts at ON at.id = aa.assessment_attempt_id "
                "WHERE aa.id = :answer_id AND al.alert_type = 'review_requested' "
                "AND al.read_at IS NULL AND al.enrollment_id = at.enrollment_id "
                "AND al.path_step_id IS NOT DISTINCT FROM at.path_step_id"
            ),
            {"answer_id": attempt_answer_id},
        )

    async def list_for_recipient(
        self, user_id: int, *, unread: bool | None, limit: int, offset: int
    ) -> tuple[list[Alert], int]:
        conditions = [AlertModel.recipient_user_id == user_id, AlertModel.active.is_(True)]
        if unread is True:
            conditions.append(AlertModel.read_at.is_(None))
        elif unread is False:
            conditions.append(AlertModel.read_at.is_not(None))
        total = (
            await self._session.execute(
                select(func.count()).select_from(AlertModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(AlertModel)
                    .where(*conditions)
                    .order_by(AlertModel.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows], total


class SqlAlchemyPlatformReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._courses = SqlAlchemyCourseRepository(session)
        self._topics = SqlAlchemyTopicRepository(session)
        self._users = SqlAlchemyUserRepository(session)
        self._profiles = SqlAlchemyProfileRepository(session)
        self._consents = SqlAlchemyConsentRepository(session)

    async def course(self, course_id: int) -> Course | None:
        return await self._courses.get(course_id)

    async def topic(self, topic_id: int) -> Topic | None:
        return await self._topics.get(topic_id)

    async def topic_nodes(self, course_id: int) -> list[TopicNode]:
        topics = await self._topics.list_for_course(course_id)
        ids = [t.id for t in topics if t.id is not None]
        edges: dict[int, list[int]] = {}
        if ids:
            rows = await self._session.execute(
                select(
                    TopicPrerequisiteModel.topic_id, TopicPrerequisiteModel.prerequisite_topic_id
                )
                .where(
                    TopicPrerequisiteModel.topic_id.in_(ids),
                    TopicPrerequisiteModel.prerequisite_topic_id.in_(ids),
                    TopicPrerequisiteModel.active.is_(True),
                )
                .order_by(TopicPrerequisiteModel.id)
            )
            for topic_id, prerequisite_id in rows.all():
                edges.setdefault(int(topic_id), []).append(int(prerequisite_id))
        return [
            TopicNode(
                id=int(t.id),
                name=t.name,
                position=t.position,
                estimated_minutes=t.estimated_minutes,
                is_mandatory=t.is_mandatory,
                prerequisites=tuple(edges.get(int(t.id), [])),
            )
            for t in topics
            if t.id is not None
        ]

    async def user(self, user_id: int) -> User | None:
        return await self._users.get(user_id)

    async def profile(self, user_id: int) -> UserProfile | None:
        return await self._profiles.get_by_user_id(user_id)

    async def consent_in_force(self, user_id: int, consent_type: str) -> bool:
        latest = await self._consents.latest(user_id, consent_type)
        return latest is not None and latest.in_force

    async def pilot_running(self, learning_path_id: int) -> bool:
        # `pilots` es del dominio del piloto: aquí solo se lee si hay uno en curso.
        found = await self._session.execute(
            text(
                "SELECT 1 FROM pilots WHERE learning_path_id = :path_id "
                "AND status = 'running' AND active LIMIT 1"
            ),
            {"path_id": learning_path_id},
        )
        return found.first() is not None

    async def pilot_arm_for_new_enrollment(self, learning_path_id: int) -> str | None:
        found = await self._session.execute(
            text(
                "SELECT 1 FROM pilots WHERE learning_path_id = :path_id AND active "
                "AND status IN ('randomized', 'running') LIMIT 1"
            ),
            {"path_id": learning_path_id},
        )
        if found.first() is None:
            return None
        counts: dict[str, int] = dict(
            (
                await self._session.execute(
                    text(
                        "SELECT pilot_arm, count(*) FROM enrollments WHERE learning_path_id = "
                        ":path_id AND active AND pilot_arm IS NOT NULL GROUP BY pilot_arm"
                    ),
                    {"path_id": learning_path_id},
                )
            )
            .tuples()
            .all()
        )
        return "fixed" if counts.get("fixed", 0) < counts.get("personalized", 0) else "personalized"

    async def first_admin_id(self) -> int | None:
        found = await self._session.execute(
            text(
                "SELECT u.id FROM users u JOIN user_roles ur ON ur.user_id = u.id AND ur.active "
                "JOIN roles r ON r.id = ur.role_id AND r.code = 'admin' "
                "WHERE u.active ORDER BY u.id LIMIT 1"
            )
        )
        value = found.scalar_one_or_none()
        return None if value is None else int(value)
