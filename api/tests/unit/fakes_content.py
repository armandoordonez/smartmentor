"""Repositorios en memoria del dominio de contenido (pruebas unitarias)."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.common.entities import require_id
from app.domains.content.entities import (
    AssessmentItem,
    RatingSummary,
    Resource,
    VideoCandidate,
    VideoFeedback,
    VideoRelevanceJudgment,
)
from tests.unit.fakes import InMemoryRepository


class InMemoryResources(InMemoryRepository[Resource]):
    async def add(self, entity: Resource) -> Resource:
        return await super().add(replace(entity, created_at=entity.created_at or datetime.now(UTC)))

    def _shared_text(self, topic_id: int) -> list[Resource]:
        return [
            r
            for r in self.items.values()
            if r.topic_id == topic_id
            and r.resource_type == "text"
            and r.kind == "main"
            and r.audience == "all_learners"
            and r.active
        ]

    async def list_for_topic(self, topic_id: int) -> list[Resource]:
        found = [
            r
            for r in self.items.values()
            if r.topic_id == topic_id and r.audience == "all_learners" and r.active
        ]
        return sorted(found, key=lambda r: (r.resource_type, r.version, require_id(r)))

    async def latest_main_text(self, topic_id: int) -> Resource | None:
        found = [r for r in self._shared_text(topic_id) if r.review_status != "retired"]
        return max(found, key=lambda r: (r.version, require_id(r)), default=None)

    async def max_version(self, topic_id: int) -> int:
        return max((r.version for r in self._shared_text(topic_id)), default=0)

    async def exists_main_text_since(self, topic_id: int, moment: datetime) -> bool:
        return any((r.created_at or moment) >= moment for r in self._shared_text(topic_id))

    async def retire_other_approved(self, resource: Resource) -> None:
        for key, other in list(self.items.items()):
            if (
                other.id != resource.id
                and other.topic_id == resource.topic_id
                and other.resource_type == resource.resource_type
                and other.kind == resource.kind
                and other.review_status == "approved"
            ):
                self.items[key] = replace(other, review_status="retired")

    async def video_resource(self, video_candidate_id: int) -> Resource | None:
        return next(
            (r for r in self.items.values() if r.video_candidate_id == video_candidate_id), None
        )

    async def lock_topic(self, topic_id: int) -> None:
        return None


class InMemoryItems(InMemoryRepository[AssessmentItem]):
    def __init__(self) -> None:
        super().__init__()
        self.outcomes: dict[int, dict[int, str]] = {}

    async def get_for_update(self, item_id: int) -> AssessmentItem | None:
        return await self.get(item_id)

    async def search_topic(
        self,
        *,
        topic_id: int,
        source: str | None,
        review_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AssessmentItem], int]:
        found = [
            i
            for i in self.items.values()
            if i.topic_id == topic_id
            and i.active
            and (source is None or i.source == source)
            and (review_status is None or i.review_status == review_status)
        ]
        return found[offset : offset + limit], len(found)

    async def count_for_job(self, ai_job_id: int) -> int:
        return sum(1 for i in self.items.values() if i.ai_job_id == ai_job_id)

    async def resolve_ai_job_id(self, public_id: str) -> int | None:
        return None

    async def lock_topic(self, topic_id: int) -> None:
        return None

    async def exists(self, topic_id: int, source: str, stem: str) -> bool:
        return any(
            i.topic_id == topic_id and i.source == source and i.stem == stem
            for i in self.items.values()
        )

    async def outcome_statements(self, topic_id: int) -> dict[int, str]:
        return self.outcomes.get(topic_id, {})


class InMemoryVideos(InMemoryRepository[VideoCandidate]):
    def __init__(self) -> None:
        super().__init__()
        self.judgments: list[VideoRelevanceJudgment] = []

    async def get_by_youtube(self, topic_id: int, youtube_video_id: str) -> VideoCandidate | None:
        return next(
            (
                v
                for v in self.items.values()
                if v.topic_id == topic_id and v.youtube_video_id == youtube_video_id
            ),
            None,
        )

    async def list_for_topic(self, topic_id: int) -> list[VideoCandidate]:
        found = [v for v in self.items.values() if v.topic_id == topic_id and v.active]
        return sorted(found, key=lambda v: (v.rank is None, v.rank or 0, require_id(v)))

    async def demote_in_use(self, topic_id: int, except_id: int) -> None:
        for key, video in list(self.items.items()):
            if video.topic_id == topic_id and video.status == "in_use" and video.id != except_id:
                self.items[key] = replace(video, status="backup")

    async def get_judgment(
        self, video_id: int, judge_user_id: int
    ) -> VideoRelevanceJudgment | None:
        return next(
            (
                j
                for j in self.judgments
                if j.video_candidate_id == video_id and j.judge_user_id == judge_user_id
            ),
            None,
        )

    async def save_judgment(
        self, video_id: int, judge_user_id: int, is_relevant: bool
    ) -> VideoRelevanceJudgment:
        self.judgments = [
            j
            for j in self.judgments
            if not (j.video_candidate_id == video_id and j.judge_user_id == judge_user_id)
        ]
        saved = VideoRelevanceJudgment(
            video_candidate_id=video_id, judge_user_id=judge_user_id, is_relevant=is_relevant
        )
        self.judgments.append(saved)
        return saved

    async def judgments_of(self, judge_user_id: int, video_ids: list[int]) -> dict[int, bool]:
        return {
            j.video_candidate_id: j.is_relevant
            for j in self.judgments
            if j.judge_user_id == judge_user_id and j.video_candidate_id in video_ids
        }


class InMemoryFeedback(InMemoryRepository[VideoFeedback]):
    async def find(self, video_id: int, enrollment_id: int) -> VideoFeedback | None:
        return next(
            (
                f
                for f in self.items.values()
                if f.video_candidate_id == video_id and f.enrollment_id == enrollment_id
            ),
            None,
        )

    async def summaries(self, video_ids: list[int]) -> dict[int, RatingSummary]:
        result: dict[int, RatingSummary] = {}
        for feedback in self.items.values():
            if feedback.video_candidate_id not in video_ids:
                continue
            current = result.setdefault(
                feedback.video_candidate_id, RatingSummary(feedback.video_candidate_id)
            )
            current.ratings[feedback.rating] = current.ratings.get(feedback.rating, 0) + 1
        return result


class InMemoryEnrollments:
    """Inscripciones de aprendices: `{enrollment_id: (user_id, course_id)}`."""

    def __init__(self, rows: dict[int, tuple[int, int]] | None = None) -> None:
        self.rows = rows or {}

    async def course_of_learner_enrollment(self, enrollment_id: int, user_id: int) -> int | None:
        row = self.rows.get(enrollment_id)
        return row[1] if row is not None and row[0] == user_id else None


def changes_of(entity: Any, **values: Any) -> Any:
    return replace(entity, **values)
