"""Repositorios SQLAlchemy de contenido."""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.ai_gateway.models import AiJobModel
from app.domains.content.entities import (
    AssessmentItem,
    RatingSummary,
    Resource,
    VideoCandidate,
    VideoFeedback,
    VideoRelevanceJudgment,
)
from app.domains.content.models import (
    AssessmentItemModel,
    ResourceModel,
    VideoCandidateModel,
    VideoFeedbackModel,
    VideoRelevanceJudgmentModel,
)
from app.domains.courses.models import LearningOutcomeModel


class SqlAlchemyResourceRepository(SqlAlchemyCrudRepository[ResourceModel, Resource]):
    model = ResourceModel
    entity = Resource
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "resources_topic_id_fk": ("TOPIC_NOT_FOUND", "The topic does not exist."),
    }

    def _shared_text(self) -> list[Any]:
        return [
            ResourceModel.resource_type == "text",
            ResourceModel.kind == "main",
            ResourceModel.audience == "all_learners",
            ResourceModel.active.is_(True),
        ]

    async def list_for_topic(self, topic_id: int) -> list[Resource]:
        rows = (
            (
                await self._session.execute(
                    select(ResourceModel)
                    .where(
                        ResourceModel.topic_id == topic_id,
                        ResourceModel.audience == "all_learners",
                        ResourceModel.active.is_(True),
                    )
                    .order_by(ResourceModel.resource_type, ResourceModel.version, ResourceModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows]

    async def latest_main_text(self, topic_id: int) -> Resource | None:
        row = (
            (
                await self._session.execute(
                    select(ResourceModel)
                    .where(
                        ResourceModel.topic_id == topic_id,
                        ResourceModel.review_status != "retired",
                        *self._shared_text(),
                    )
                    .order_by(ResourceModel.version.desc(), ResourceModel.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def max_version(self, topic_id: int) -> int:
        value = (
            await self._session.execute(
                select(func.max(ResourceModel.version)).where(
                    ResourceModel.topic_id == topic_id, *self._shared_text()
                )
            )
        ).scalar_one()
        return int(value or 0)

    async def exists_main_text_since(self, topic_id: int, moment: datetime) -> bool:
        found = (
            await self._session.execute(
                select(ResourceModel.id)
                .where(
                    ResourceModel.topic_id == topic_id,
                    ResourceModel.created_at >= moment,
                    *self._shared_text(),
                )
                .limit(1)
            )
        ).first()
        return found is not None

    async def retire_other_approved(self, resource: Resource) -> None:
        await self._session.execute(
            update(ResourceModel)
            .where(
                ResourceModel.topic_id == resource.topic_id,
                ResourceModel.resource_type == resource.resource_type,
                ResourceModel.kind == resource.kind,
                ResourceModel.audience == "all_learners",
                ResourceModel.review_status == "approved",
                ResourceModel.id != resource.id,
            )
            .values(review_status="retired")
        )

    async def video_resource(self, video_candidate_id: int) -> Resource | None:
        row = (
            (
                await self._session.execute(
                    select(ResourceModel)
                    .where(
                        ResourceModel.video_candidate_id == video_candidate_id,
                        ResourceModel.active.is_(True),
                    )
                    .order_by(ResourceModel.id.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def lock_topic(self, topic_id: int) -> None:
        await self._session.execute(
            text("SELECT id FROM topics WHERE id = :id FOR UPDATE"), {"id": topic_id}
        )


class SqlAlchemyItemRepository(SqlAlchemyCrudRepository[AssessmentItemModel, AssessmentItem]):
    model = AssessmentItemModel
    entity = AssessmentItem
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "assessment_items_shape_ck": ("VALIDATION_ERROR", "The item shape is not valid."),
        "assessment_items_review_status_ck": ("VALIDATION_ERROR", "Invalid review status."),
    }

    async def get_for_update(self, item_id: int) -> AssessmentItem | None:
        row = (
            await self._session.execute(
                select(AssessmentItemModel)
                .where(AssessmentItemModel.id == item_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_entity(row)

    async def search_topic(
        self,
        *,
        topic_id: int,
        source: str | None,
        review_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AssessmentItem], int]:
        conditions = [
            AssessmentItemModel.topic_id == topic_id,
            AssessmentItemModel.active.is_(True),
        ]
        if source:
            conditions.append(AssessmentItemModel.source == source)
        if review_status:
            conditions.append(AssessmentItemModel.review_status == review_status)
        total = (
            await self._session.execute(
                select(func.count()).select_from(AssessmentItemModel).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    select(AssessmentItemModel)
                    .where(*conditions)
                    .order_by(AssessmentItemModel.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows], total

    async def count_for_job(self, ai_job_id: int) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(AssessmentItemModel)
                    .where(AssessmentItemModel.ai_job_id == ai_job_id)
                )
            ).scalar_one()
        )

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

    async def lock_topic(self, topic_id: int) -> None:
        await self._session.execute(
            text("SELECT id FROM topics WHERE id = :id FOR UPDATE"), {"id": topic_id}
        )

    async def exists(self, topic_id: int, source: str, stem: str) -> bool:
        found = (
            await self._session.execute(
                select(AssessmentItemModel.id)
                .where(
                    AssessmentItemModel.topic_id == topic_id,
                    AssessmentItemModel.source == source,
                    AssessmentItemModel.stem == stem,
                    AssessmentItemModel.active.is_(True),
                )
                .limit(1)
            )
        ).first()
        return found is not None

    async def outcome_statements(self, topic_id: int) -> dict[int, str]:
        rows = await self._session.execute(
            select(LearningOutcomeModel.id, LearningOutcomeModel.statement).where(
                LearningOutcomeModel.topic_id == topic_id, LearningOutcomeModel.active.is_(True)
            )
        )
        return {int(i): str(t) for i, t in rows.all()}


class _JudgmentRepository(
    SqlAlchemyCrudRepository[VideoRelevanceJudgmentModel, VideoRelevanceJudgment]
):
    model = VideoRelevanceJudgmentModel
    entity = VideoRelevanceJudgment

    async def find(self, video_id: int, judge_user_id: int) -> VideoRelevanceJudgment | None:
        row = (
            (
                await self._session.execute(
                    select(VideoRelevanceJudgmentModel).where(
                        VideoRelevanceJudgmentModel.video_candidate_id == video_id,
                        VideoRelevanceJudgmentModel.judge_user_id == judge_user_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)


class SqlAlchemyVideoRepository(SqlAlchemyCrudRepository[VideoCandidateModel, VideoCandidate]):
    model = VideoCandidateModel
    entity = VideoCandidate
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "video_candidates_topic_video_uq": (
            "CONFLICT",
            "The video is already a candidate of the topic.",
        ),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._judgments = _JudgmentRepository(session)

    async def get_by_youtube(self, topic_id: int, youtube_video_id: str) -> VideoCandidate | None:
        row = (
            (
                await self._session.execute(
                    select(VideoCandidateModel).where(
                        VideoCandidateModel.topic_id == topic_id,
                        VideoCandidateModel.youtube_video_id == youtube_video_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def list_for_topic(self, topic_id: int) -> list[VideoCandidate]:
        rows = (
            (
                await self._session.execute(
                    select(VideoCandidateModel)
                    .where(
                        VideoCandidateModel.topic_id == topic_id,
                        VideoCandidateModel.active.is_(True),
                    )
                    .order_by(VideoCandidateModel.rank.asc().nulls_last(), VideoCandidateModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows]

    async def demote_in_use(self, topic_id: int, except_id: int) -> None:
        await self._session.execute(
            update(VideoCandidateModel)
            .where(
                VideoCandidateModel.topic_id == topic_id,
                VideoCandidateModel.status == "in_use",
                VideoCandidateModel.id != except_id,
            )
            .values(status="backup")
        )

    async def get_judgment(
        self, video_id: int, judge_user_id: int
    ) -> VideoRelevanceJudgment | None:
        return await self._judgments.find(video_id, judge_user_id)

    async def save_judgment(
        self, video_id: int, judge_user_id: int, is_relevant: bool
    ) -> VideoRelevanceJudgment:
        existing = await self._judgments.find(video_id, judge_user_id)
        if existing is None:
            return await self._judgments.add(
                VideoRelevanceJudgment(
                    video_candidate_id=video_id,
                    judge_user_id=judge_user_id,
                    is_relevant=is_relevant,
                )
            )
        updated = await self._judgments.update(
            existing.id or 0, {"is_relevant": is_relevant, "active": True}
        )
        if updated is None:
            raise RuntimeError("The judgment disappeared during the update.")
        return updated

    async def judgments_of(self, judge_user_id: int, video_ids: list[int]) -> dict[int, bool]:
        if not video_ids:
            return {}
        rows = await self._session.execute(
            select(
                VideoRelevanceJudgmentModel.video_candidate_id,
                VideoRelevanceJudgmentModel.is_relevant,
            ).where(
                VideoRelevanceJudgmentModel.judge_user_id == judge_user_id,
                VideoRelevanceJudgmentModel.video_candidate_id.in_(video_ids),
                VideoRelevanceJudgmentModel.active.is_(True),
            )
        )
        return {int(v): bool(r) for v, r in rows.all()}


class SqlAlchemyFeedbackRepository(SqlAlchemyCrudRepository[VideoFeedbackModel, VideoFeedback]):
    model = VideoFeedbackModel
    entity = VideoFeedback

    async def find(self, video_id: int, enrollment_id: int) -> VideoFeedback | None:
        row = (
            (
                await self._session.execute(
                    select(VideoFeedbackModel).where(
                        VideoFeedbackModel.video_candidate_id == video_id,
                        VideoFeedbackModel.enrollment_id == enrollment_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_entity(row)

    async def summaries(self, video_ids: list[int]) -> dict[int, RatingSummary]:
        if not video_ids:
            return {}
        rows = await self._session.execute(
            select(
                VideoFeedbackModel.video_candidate_id,
                VideoFeedbackModel.rating,
                func.count(),
                func.count().filter(VideoFeedbackModel.watched_fully.is_(True)),
            )
            .where(
                VideoFeedbackModel.video_candidate_id.in_(video_ids),
                VideoFeedbackModel.active.is_(True),
            )
            .group_by(VideoFeedbackModel.video_candidate_id, VideoFeedbackModel.rating)
        )
        ratings: dict[int, dict[str, int]] = {}
        watched: dict[int, int] = {}
        for video_id, rating, count, watched_count in rows.all():
            ratings.setdefault(int(video_id), {})[str(rating)] = int(count)
            watched[int(video_id)] = watched.get(int(video_id), 0) + int(watched_count)
        return {v: RatingSummary(v, r, watched.get(v, 0)) for v, r in ratings.items()}


class SqlAlchemyEnrollmentLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def course_of_learner_enrollment(self, enrollment_id: int, user_id: int) -> int | None:
        found = (
            await self._session.execute(
                text(
                    "SELECT lp.course_id FROM enrollments e "
                    "JOIN learning_paths lp ON lp.id = e.learning_path_id "
                    "WHERE e.id = :id AND e.user_id = :user AND e.active"
                ),
                {"id": enrollment_id, "user": user_id},
            )
        ).scalar_one_or_none()
        return None if found is None else int(found)
