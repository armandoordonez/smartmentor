"""Repositorios SQLAlchemy de evaluaciones y lectura de contenido."""

import json
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.assessments.entities import (
    AssessmentAttempt,
    AssessmentItem,
    AttemptAnswer,
    Badge,
    Diagnostic,
)
from app.domains.assessments.models import (
    AssessmentAttemptModel,
    AssessmentItemModel,
    AttemptAnswerModel,
    BadgeModel,
    DiagnosticModel,
)


class SqlAlchemyItemRepository(SqlAlchemyCrudRepository[AssessmentItemModel, AssessmentItem]):
    model = AssessmentItemModel
    entity = AssessmentItem
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "assessment_items_shape_ck": ("VALIDATION_ERROR", "The item shape is not valid."),
    }

    async def by_ids(self, item_ids: list[int]) -> dict[int, AssessmentItem]:
        if not item_ids:
            return {}
        rows = (
            (await self._session.execute(select(AssessmentItemModel).where(AssessmentItemModel.id.in_(item_ids))))
            .scalars()
            .all()
        )
        return {row.id: self._to_entity(row) for row in rows}

    async def approved(self, topic_ids: list[int], source: str) -> list[AssessmentItem]:
        if not topic_ids:
            return []
        rows = (
            (
                await self._session.execute(
                    select(AssessmentItemModel)
                    .where(
                        AssessmentItemModel.topic_id.in_(topic_ids),
                        AssessmentItemModel.source == source,
                        AssessmentItemModel.review_status == "approved",
                        AssessmentItemModel.active.is_(True),
                    )
                    .order_by(AssessmentItemModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]

    async def count_for_topic(self, topic_id: int, source: str) -> int:
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(AssessmentItemModel)
                .where(AssessmentItemModel.topic_id == topic_id, AssessmentItemModel.source == source)
            )
        ).scalar_one()
        return int(total)

    async def stems_for_topic(self, topic_id: int, source: str) -> list[str]:
        rows = await self._session.execute(
            select(AssessmentItemModel.stem)
            .where(AssessmentItemModel.topic_id == topic_id, AssessmentItemModel.source == source)
            .order_by(AssessmentItemModel.id)
        )
        return [str(stem) for stem in rows.scalars().all()]

    async def exists_for_job(self, job_id: str) -> bool:
        found = await self._session.execute(
            select(AssessmentItemModel.id)
            .where(AssessmentItemModel.auto_review["job_id"].astext == job_id)
            .limit(1)
        )
        return found.first() is not None

    async def lock_job(self, job_id: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"items:{job_id}"}
        )


class SqlAlchemyDiagnosticRepository(SqlAlchemyCrudRepository[DiagnosticModel, Diagnostic]):
    model = DiagnosticModel
    entity = Diagnostic
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "diagnostics_enrollment_id_uq": (
            "DIAGNOSTIC_ALREADY_EXISTS",
            "The enrollment already has a diagnostic.",
        ),
    }

    async def by_enrollment(self, enrollment_id: int, *, for_update: bool = False) -> Diagnostic | None:
        query = select(DiagnosticModel).where(DiagnosticModel.enrollment_id == enrollment_id)
        if for_update:
            query = query.with_for_update()
        row = (
            await self._session.execute(query.execution_options(populate_existing=True))
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_by_status(self, status: str) -> list[Diagnostic]:
        rows = (
            (
                await self._session.execute(
                    select(DiagnosticModel)
                    .where(DiagnosticModel.status == status, DiagnosticModel.active.is_(True))
                    .order_by(DiagnosticModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyAttemptRepository(SqlAlchemyCrudRepository[AssessmentAttemptModel, AssessmentAttempt]):
    model = AssessmentAttemptModel
    entity = AssessmentAttempt
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "assessment_attempts_number_uq": (
            "ATTEMPT_IN_PROGRESS",
            "Another attempt was created at the same time.",
        ),
    }

    async def get(self, attempt_id: int, *, for_update: bool = False) -> AssessmentAttempt | None:  # type: ignore[override]
        query = select(AssessmentAttemptModel).where(AssessmentAttemptModel.id == attempt_id)
        if for_update:
            query = query.with_for_update()
        row = (
            await self._session.execute(query.execution_options(populate_existing=True))
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_for_enrollment(self, enrollment_id: int) -> list[AssessmentAttempt]:
        rows = (
            (
                await self._session.execute(
                    select(AssessmentAttemptModel)
                    .where(
                        AssessmentAttemptModel.enrollment_id == enrollment_id,
                        AssessmentAttemptModel.active.is_(True),
                    )
                    .order_by(AssessmentAttemptModel.id)
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]

    async def list_by_status(self, status: str) -> list[AssessmentAttempt]:
        rows = (
            (
                await self._session.execute(
                    select(AssessmentAttemptModel)
                    .where(
                        AssessmentAttemptModel.status == status,
                        AssessmentAttemptModel.active.is_(True),
                    )
                    .order_by(AssessmentAttemptModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyAnswerRepository(SqlAlchemyCrudRepository[AttemptAnswerModel, AttemptAnswer]):
    model = AttemptAnswerModel
    entity = AttemptAnswer
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "attempt_answers_attempt_item_uq": ("CONFLICT", "The answer already exists."),
    }

    async def list_for_attempt(self, attempt_id: int) -> list[AttemptAnswer]:
        rows = (
            (
                await self._session.execute(
                    select(AttemptAnswerModel)
                    .where(AttemptAnswerModel.assessment_attempt_id == attempt_id)
                    .order_by(AttemptAnswerModel.id)
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


class SqlAlchemyBadgeRepository(SqlAlchemyCrudRepository[BadgeModel, Badge]):
    model = BadgeModel
    entity = Badge
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "badges_enrollment_id_uq": ("CONFLICT", "The enrollment already has a badge."),
    }

    async def by_enrollment(self, enrollment_id: int) -> Badge | None:
        row = (
            await self._session.execute(
                select(BadgeModel).where(BadgeModel.enrollment_id == enrollment_id)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def by_public_id(self, public_id: UUID) -> Badge | None:
        row = (
            await self._session.execute(
                select(BadgeModel).where(
                    BadgeModel.public_id == public_id, BadgeModel.active.is_(True)
                )
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def for_enrollments(self, enrollment_ids: list[int]) -> list[Badge]:
        if not enrollment_ids:
            return []
        rows = (
            (
                await self._session.execute(
                    select(BadgeModel)
                    .where(BadgeModel.enrollment_id.in_(enrollment_ids), BadgeModel.active.is_(True))
                    .order_by(BadgeModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(row) for row in rows]


def _content(value: str | None) -> Any:
    """El contenido de un recurso: el JSON de `topic_explanation.v1` si lo es; si no, el texto."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return value


class SqlAlchemyContentReader:
    """Lee `resources`, `video_candidates` y `learning_outcomes` sin declarar sus modelos.

    Esas tablas son del dominio de contenido; aquí solo se consultan, con SQL explícito.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _resource(self, where: str, params: dict[str, Any]) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT id, version, prompt_version, content, faithfulness FROM resources "
                    f"WHERE active AND {where} ORDER BY version DESC, id DESC LIMIT 1"  # noqa: S608  (fragmento fijo, sin datos del usuario)
                ),
                params,
            )
        ).mappings().first()
        if row is None:
            return None
        return {
            "resource_id": int(row["id"]),
            "version": f"{int(row['version'])}.0",
            "prompt_version": row["prompt_version"],
            "content": _content(row["content"]),
            "faithfulness": float(row["faithfulness"]) if row["faithfulness"] is not None else None,
        }

    async def explanation(self, topic_id: int) -> dict[str, Any] | None:
        return await self._resource(
            "topic_id = :topic_id AND resource_type = 'text' AND kind = 'main' "
            "AND audience = 'all_learners' AND review_status = 'approved'",
            {"topic_id": topic_id},
        )

    async def personal_example(self, topic_id: int, enrollment_id: int) -> dict[str, Any] | None:
        return await self._resource(
            "topic_id = :topic_id AND kind = 'personal_example' AND enrollment_id = :enrollment_id "
            "AND review_status <> 'retired'",
            {"topic_id": topic_id, "enrollment_id": enrollment_id},
        )

    async def remedial_resource_id(self, topic_id: int, enrollment_id: int) -> int | None:
        found = await self._resource(
            "topic_id = :topic_id AND kind = 'remedial' AND enrollment_id = :enrollment_id "
            "AND review_status <> 'retired'",
            {"topic_id": topic_id, "enrollment_id": enrollment_id},
        )
        return None if found is None else int(found["resource_id"])

    async def video(self, topic_id: int) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT id, youtube_video_id, title, duration_seconds, status "
                    "FROM video_candidates WHERE active AND topic_id = :topic_id "
                    "AND status IN ('in_use', 'backup') "
                    "ORDER BY CASE status WHEN 'in_use' THEN 0 ELSE 1 END, rank NULLS LAST, id "
                    "LIMIT 1"
                ),
                {"topic_id": topic_id},
            )
        ).mappings().first()
        if row is None:
            return None
        return {
            "video_candidate_id": int(row["id"]),
            "youtube_video_id": row["youtube_video_id"],
            "title": row["title"],
            "duration_seconds": row["duration_seconds"],
            "is_backup": row["status"] == "backup",
        }

    async def outcomes(self, topic_id: int) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                text(
                    "SELECT id, statement, bloom_level FROM learning_outcomes "
                    "WHERE active AND topic_id = :topic_id ORDER BY id"
                ),
                {"topic_id": topic_id},
            )
        ).mappings().all()
        return [
            {"id": int(r["id"]), "statement": r["statement"], "bloom_level": r["bloom_level"]}
            for r in rows
        ]
