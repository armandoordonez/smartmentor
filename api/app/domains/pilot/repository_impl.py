"""Repositorios SQLAlchemy del piloto."""

from typing import ClassVar

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.pilot.entities import ContentFacts, PathSummary, Pilot, PilotEnrollment
from app.domains.pilot.models import PilotModel


class SqlAlchemyPilotRepository(SqlAlchemyCrudRepository[PilotModel, Pilot]):
    model = PilotModel
    entity = Pilot
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "pilots_learning_path_id_fk": ("NOT_FOUND", "The learning path does not exist."),
        "pilots_dates_ck": ("VALIDATION_ERROR", "ends_on must not be before starts_on."),
        "pilots_status_ck": ("VALIDATION_ERROR", "Invalid pilot status."),
    }

    async def get_for_update(self, pilot_id: int) -> Pilot | None:
        row = (
            await self._session.execute(
                select(PilotModel)
                .where(PilotModel.id == pilot_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def list_all(self, *, limit: int, offset: int) -> tuple[list[Pilot], int]:
        return await self.search(filters={}, active=True, limit=limit, offset=offset)

    async def open_for_path(self, learning_path_id: int, *, excluding: int | None) -> Pilot | None:
        query = select(PilotModel).where(
            PilotModel.learning_path_id == learning_path_id,
            PilotModel.active.is_(True),
            PilotModel.status != "closed",
        )
        if excluding is not None:
            query = query.where(PilotModel.id != excluding)
        row = (await self._session.execute(query.limit(1))).scalars().first()
        return None if row is None else self._to_entity(row)


class SqlAlchemyPilotPopulation:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def path_summary(self, learning_path_id: int) -> PathSummary | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT name, group_label, final_pass_threshold FROM learning_paths "
                    "WHERE id = :id AND active"
                ),
                {"id": learning_path_id},
            )
        ).first()
        if row is None:
            return None
        return PathSummary(name=str(row[0]), group_label=row[1], final_pass_threshold=float(row[2]))

    async def path_course(self, learning_path_id: int) -> tuple[int, float] | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT course_id, mastery_skip_threshold FROM learning_paths "
                    "WHERE id = :id AND active"
                ),
                {"id": learning_path_id},
            )
        ).first()
        return None if row is None else (int(row[0]), float(row[1]))

    async def enrollments(self, learning_path_id: int) -> list[PilotEnrollment]:
        rows = await self._session.execute(
            text(
                "SELECT e.id, e.user_id, e.pilot_arm, EXISTS ("
                "  SELECT 1 FROM consents c WHERE c.user_id = e.user_id AND c.active "
                "  AND c.consent_type = 'pilot_research' AND c.revoked_at IS NULL) AS consented "
                "FROM enrollments e WHERE e.learning_path_id = :p AND e.active "
                "AND e.status NOT IN ('withdrawn', 'abandoned') ORDER BY e.id"
            ),
            {"p": learning_path_id},
        )
        return [PilotEnrollment(int(r[0]), int(r[1]), bool(r[3]), r[2]) for r in rows.all()]

    async def assign_arms(self, learning_path_id: int, arms: dict[int, str]) -> None:
        await self.clear_arms(learning_path_id)
        for enrollment_id, arm in arms.items():
            await self._session.execute(
                text(
                    "UPDATE enrollments SET pilot_arm = :arm, analysis_included = true "
                    "WHERE id = :id AND learning_path_id = :p"
                ),
                {"arm": arm, "id": enrollment_id, "p": learning_path_id},
            )

    async def clear_arms(self, learning_path_id: int) -> None:
        await self._session.execute(
            text(
                "UPDATE enrollments SET pilot_arm = NULL, analysis_included = false "
                "WHERE learning_path_id = :p AND (pilot_arm IS NOT NULL OR analysis_included)"
            ),
            {"p": learning_path_id},
        )

    async def arm_counts(self, learning_path_id: int) -> dict[str, int]:
        rows = await self._session.execute(
            text(
                "SELECT pilot_arm, count(*) FROM enrollments WHERE learning_path_id = :p "
                "AND active AND pilot_arm IS NOT NULL GROUP BY pilot_arm"
            ),
            {"p": learning_path_id},
        )
        return {str(arm): int(count) for arm, count in rows.all()}

    async def content_facts(self, course_id: int) -> ContentFacts:
        topics = [
            int(r)
            for r in (
                await self._session.execute(
                    text("SELECT id FROM topics WHERE course_id = :c AND active ORDER BY id"),
                    {"c": course_id},
                )
            ).scalars()
        ]

        async def lacking(sql: str) -> list[int]:
            rows = await self._session.execute(text(sql), {"c": course_id})
            return [int(r) for r in rows.scalars()]

        base = "SELECT t.id FROM topics t WHERE t.course_id = :c AND t.active AND NOT EXISTS ("
        no_text = await lacking(
            base  # noqa: S608  (fragmentos fijos, sin entrada del usuario)
            + "SELECT 1 FROM resources r WHERE r.topic_id = t.id AND r.active "
            "AND r.resource_type = 'text' AND r.kind = 'main' AND r.audience = 'all_learners' "
            "AND r.review_status = 'approved') ORDER BY t.id"
        )
        no_items = await lacking(
            base  # noqa: S608  (fragmentos fijos, sin entrada del usuario)
            + "SELECT 1 FROM assessment_items i WHERE i.topic_id = t.id AND i.active "
            "AND i.source = 'topic_quiz' AND i.review_status = 'approved') ORDER BY t.id"
        )
        no_video = await lacking(
            base  # noqa: S608  (fragmentos fijos, sin entrada del usuario)
            + "SELECT 1 FROM video_candidates v WHERE v.topic_id = t.id AND v.active "
            "AND v.status = 'in_use') ORDER BY t.id"
        )
        no_backup = await lacking(
            base  # noqa: S608  (fragmentos fijos, sin entrada del usuario)
            + "SELECT 1 FROM video_candidates v WHERE v.topic_id = t.id AND v.active "
            "AND v.status = 'backup') ORDER BY t.id"
        )
        no_equivalents = await lacking(
            base  # noqa: S608  (fragmentos fijos, sin entrada del usuario)
            + "SELECT 1 FROM assessment_items i WHERE i.topic_id = t.id AND i.active "
            "AND i.source IN ('final', 'retention') AND i.equivalence_group IS NOT NULL "
            "GROUP BY i.equivalence_group HAVING count(*) >= 2) ORDER BY t.id"
        )
        counts = {
            str(source): int(count)
            for source, count in (
                await self._session.execute(
                    text(
                        "SELECT i.source, count(*) FROM assessment_items i "
                        "JOIN topics t ON t.id = i.topic_id WHERE t.course_id = :c AND i.active "
                        "AND i.review_status = 'approved' AND i.source IN ('diagnostic', 'final') "
                        "GROUP BY i.source"
                    ),
                    {"c": course_id},
                )
            ).all()
        }
        return ContentFacts(
            topic_ids=topics,
            topics_without_explanation=no_text,
            topics_without_items=no_items,
            topics_without_video=no_video,
            topics_without_backup=no_backup,
            topics_without_equivalents=no_equivalents,
            approved_diagnostic_items=counts.get("diagnostic", 0),
            approved_final_items=counts.get("final", 0),
        )
