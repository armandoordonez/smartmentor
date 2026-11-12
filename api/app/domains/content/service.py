"""Casos de uso de contenido: recursos, ítems, videos y su calidad (D5, D5d, D5e, D5f, E6).

Propiedad (sección 18.2): el instructor solo ve el contenido de los temas de sus cursos y el
administrador el de todos. Lo ajeno responde 404, nunca 403.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from app.common.constants import RoleCode
from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.entities import JobRef, JobRefs
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.content.constants import (
    MULTIPLE_CHOICE_OPTIONS,
    RUBRIC_MAX_CRITERIA,
    RUBRIC_MIN_CRITERIA,
    RUBRIC_POINTS_TOLERANCE,
    VIDEO_QUALITY_MIN_RATINGS,
    VIDEO_QUALITY_OBSERVATION,
    VIDEO_QUALITY_RECOMMENDED,
    ContentJobType,
    ItemType,
    ResourceKind,
    ResourceType,
    ReviewStatus,
    VideoOrigin,
    VideoStatus,
)
from app.domains.content.contracts import TopicExplanationBody
from app.domains.content.entities import (
    AssessmentItem,
    RatingSummary,
    Resource,
    VideoCandidate,
    VideoFeedback,
)
from app.domains.content.repository import (
    EnrollmentLookup,
    FeedbackRepository,
    ItemRepository,
    PathLookup,
    ResourceRepository,
    VideoRepository,
)
from app.domains.courses.entities import Topic
from app.domains.courses.repository import CourseRepository, TopicRepository
from app.domains.courses.service import load_course
from app.domains.identity.authentication import CurrentUser


async def load_topic(
    topics: TopicRepository, courses: CourseRepository, user: CurrentUser, topic_id: int
) -> Topic:
    """Tema de un curso al que el usuario tiene acceso; si no, `404 TOPIC_NOT_FOUND`."""
    topic = await topics.get(topic_id)
    if topic is None or not topic.active:
        raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND")
    try:
        await load_course(courses, user, topic.course_id)
    except NotFoundError as exc:
        raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND") from exc
    return topic


def version_label(version: int) -> str:
    """La versión entera de la base se muestra como `1.n` (D5d): 1 -> «1.0», 2 -> «1.1»."""
    return f"1.{max(version - 1, 0)}"


def explanation_text(body: TopicExplanationBody) -> str:
    return "\n\n".join(f"{s.heading}\n{s.body}" for s in body.sections)


# --- Recursos ---------------------------------------------------------------------------------

_RESOURCE_TRANSITIONS: dict[str, frozenset[str]] = {
    ReviewStatus.PENDING_REVIEW: frozenset({ReviewStatus.APPROVED, ReviewStatus.RETIRED}),
    ReviewStatus.APPROVED: frozenset({ReviewStatus.RETIRED}),
    ReviewStatus.RETIRED: frozenset(),
}


@dataclass(frozen=True)
class ResourceEdit:
    resource: Resource
    faithfulness_job_id: str


class ResourceService:
    def __init__(
        self,
        resources: ResourceRepository,
        topics: TopicRepository,
        courses: CourseRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._resources = resources
        self._topics = topics
        self._courses = courses
        self._ai = ai
        self._uow = uow

    async def _load(self, user: CurrentUser, resource_id: int) -> tuple[Resource, Topic]:
        resource = await self._resources.get(resource_id)
        if resource is None or not resource.active or resource.audience != "all_learners":
            raise NotFoundError("Resource", resource_id, code="RESOURCE_NOT_FOUND")
        try:
            topic = await load_topic(self._topics, self._courses, user, resource.topic_id)
        except NotFoundError as exc:
            raise NotFoundError("Resource", resource_id, code="RESOURCE_NOT_FOUND") from exc
        return resource, topic

    async def list_for_topic(self, user: CurrentUser, topic_id: int) -> list[Resource]:
        await load_topic(self._topics, self._courses, user, topic_id)
        return await self._resources.list_for_topic(topic_id)

    async def review(self, user: CurrentUser, resource_id: int, status: str) -> Resource:
        resource, _ = await self._load(user, resource_id)
        if status not in _RESOURCE_TRANSITIONS.get(resource.review_status, frozenset()):
            raise InvalidStateTransitionError(
                f"A resource that is {resource.review_status} cannot become {status}."
            )
        updated = await self._resources.update(resource_id, {"review_status": status})
        if updated is None:
            raise NotFoundError("Resource", resource_id, code="RESOURCE_NOT_FOUND")
        if status == ReviewStatus.APPROVED:
            # Solo una versión aprobada por tema y clase: la nueva reemplaza a la anterior.
            await self._resources.retire_other_approved(updated)
        await self._uow.commit()
        return updated

    async def edit_content(
        self, user: CurrentUser, resource_id: int, body: TopicExplanationBody
    ) -> ResourceEdit:
        """La edición crea una versión nueva y pide `content.check_faithfulness` (D5d)."""
        resource, topic = await self._load(user, resource_id)
        if resource.resource_type != ResourceType.TEXT or resource.kind != ResourceKind.MAIN:
            raise BusinessRuleError(
                "Only the main text explanation can be edited.", code="VALIDATION_ERROR"
            )
        topic_id = require_id(topic)
        await self._resources.lock_topic(topic_id)
        version = await self._resources.max_version(topic_id) + 1
        created = await self._resources.add(
            Resource(
                topic_id=topic_id,
                resource_type=ResourceType.TEXT,
                kind=ResourceKind.MAIN,
                version=version,
                review_status=ReviewStatus.PENDING_REVIEW,
                content=json.dumps(body.model_dump(mode="json"), ensure_ascii=False),
                sources=[s.model_dump(mode="json") for s in body.sources],
                prompt_version=resource.prompt_version,
                edited_by_user_id=user.id,
            )
        )
        job = await self._ai.submit_job(
            ContentJobType.CHECK_FAITHFULNESS,
            {
                "topic_id": str(topic_id),
                "text": explanation_text(body),
                "source_ids": [s.source_id for s in body.sources],
            },
            f"{ContentJobType.CHECK_FAITHFULNESS}:resource:{require_id(created)}:v{version}",
            JobRefs(course_id=topic.course_id, topic_id=topic_id),
        )
        await self._uow.commit()
        return ResourceEdit(created, job.job_id)

    async def regenerate(self, user: CurrentUser, resource_id: int) -> JobRef:
        resource, topic = await self._load(user, resource_id)
        if resource.resource_type != ResourceType.TEXT or resource.kind != ResourceKind.MAIN:
            raise BusinessRuleError(
                "Only the main text explanation can be regenerated.", code="VALIDATION_ERROR"
            )
        topic_id = require_id(topic)
        version = await self._resources.max_version(topic_id) + 1
        return await self._ai.submit_job(
            ContentJobType.EXPLAIN_TOPIC,
            {"topic_id": str(topic_id)},
            f"{ContentJobType.EXPLAIN_TOPIC}:topic:{topic_id}:v{version}",
            JobRefs(course_id=topic.course_id, topic_id=topic_id),
        )


# --- Ítems ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemChanges:
    review_status: str | None = None
    stem: str | None = None
    options: list[str] | None = None
    correct_option: int | None = None
    model_answer: str | None = None
    rubric: list[dict[str, Any]] | None = None

    @property
    def has_edits(self) -> bool:
        return any(
            v is not None
            for v in (self.stem, self.options, self.correct_option, self.model_answer, self.rubric)
        )


def validate_item_shape(
    item_type: str,
    options: list[Any] | None,
    correct_option: str | None,
    rubric: list[Any] | None,
) -> None:
    """Misma forma que `AssessmentItem` de `ai/` (opción múltiple o respuesta corta)."""
    if item_type == ItemType.MULTIPLE_CHOICE:
        texts = [str(o).strip().casefold() for o in (options or [])]
        if len(texts) != MULTIPLE_CHOICE_OPTIONS or len(set(texts)) != MULTIPLE_CHOICE_OPTIONS:
            raise BusinessRuleError(
                "A multiple choice item needs exactly 4 different options.",
                code="VALIDATION_ERROR",
            )
        if correct_option is None or not correct_option.isdigit() or int(correct_option) > 3:
            raise BusinessRuleError(
                "correct_option must be an index between 0 and 3.", code="VALIDATION_ERROR"
            )
        if rubric:
            raise BusinessRuleError(
                "A multiple choice item has no rubric.", code="VALIDATION_ERROR"
            )
        return
    criteria = rubric or []
    if options or correct_option is not None:
        raise BusinessRuleError(
            "A short answer item has no options nor correct_option.", code="VALIDATION_ERROR"
        )
    if not RUBRIC_MIN_CRITERIA <= len(criteria) <= RUBRIC_MAX_CRITERIA:
        raise BusinessRuleError(
            "A short answer item needs 2 to 3 rubric criteria.", code="VALIDATION_ERROR"
        )
    total = math.fsum(float(c["points"]) for c in criteria)
    if abs(total - 1) > RUBRIC_POINTS_TOLERANCE:
        raise BusinessRuleError(
            f"The rubric points must add up to 1 (got {total}).", code="VALIDATION_ERROR"
        )


def item_digest(item: AssessmentItem) -> str:
    payload = [item.stem, item.options, item.correct_option, item.model_answer, item.rubric]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


class ItemService:
    def __init__(
        self,
        items: ItemRepository,
        topics: TopicRepository,
        courses: CourseRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._items = items
        self._topics = topics
        self._courses = courses
        self._ai = ai
        self._uow = uow

    async def list_for_topic(
        self,
        user: CurrentUser,
        topic_id: int,
        *,
        source: str | None,
        review_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AssessmentItem], int]:
        await load_topic(self._topics, self._courses, user, topic_id)
        return await self._items.search_topic(
            topic_id=topic_id,
            source=source,
            review_status=review_status,
            limit=limit,
            offset=offset,
        )

    async def update(self, user: CurrentUser, item_id: int, changes: ItemChanges) -> AssessmentItem:
        found = await self._items.get(item_id)
        if found is None or not found.active:
            raise NotFoundError("Item", item_id, code="ITEM_NOT_FOUND")
        try:
            topic = await load_topic(self._topics, self._courses, user, found.topic_id)
        except NotFoundError as exc:
            raise NotFoundError("Item", item_id, code="ITEM_NOT_FOUND") from exc
        item = await self._items.get_for_update(item_id) or found
        if changes.review_status is not None and changes.has_edits:
            raise BusinessRuleError(
                "Edit the item and review it in separate requests.", code="VALIDATION_ERROR"
            )
        if changes.has_edits:
            return await self._edit(item, topic, changes)
        if changes.review_status is None:
            raise BusinessRuleError("Nothing to change.", code="VALIDATION_ERROR")
        return await self._review(item, changes.review_status)

    async def _review(self, item: AssessmentItem, status: str) -> AssessmentItem:
        current = item.review_status
        allowed = (status == ReviewStatus.APPROVED and current == ReviewStatus.PENDING_REVIEW) or (
            status == ReviewStatus.RETIRED and current != ReviewStatus.RETIRED
        )
        if not allowed:
            raise InvalidStateTransitionError(f"An item that is {current} cannot become {status}.")
        updated = await self._items.update(require_id(item), {"review_status": status})
        await self._uow.commit()
        if updated is None:
            raise NotFoundError("Item", require_id(item), code="ITEM_NOT_FOUND")
        return updated

    async def _edit(
        self, item: AssessmentItem, topic: Topic, changes: ItemChanges
    ) -> AssessmentItem:
        if item.review_status == ReviewStatus.RETIRED:
            raise InvalidStateTransitionError("A retired item cannot be edited.")
        values: dict[str, Any] = {}
        if changes.stem is not None:
            values["stem"] = changes.stem
        if changes.options is not None:
            values["options"] = list(changes.options)
        if changes.correct_option is not None:
            values["correct_option"] = str(changes.correct_option)
        if changes.model_answer is not None:
            values["model_answer"] = changes.model_answer
        if changes.rubric is not None:
            values["rubric"] = list(changes.rubric)
        merged = AssessmentItem(
            **{**item.__dict__, **values}  # tipo y forma finales del ítem editado
        )
        validate_item_shape(merged.item_type, merged.options, merged.correct_option, merged.rubric)
        values["review_status"] = ReviewStatus.PENDING_REVIEW
        values["auto_review"] = None
        updated = await self._items.update(require_id(item), values)
        if updated is None:
            raise NotFoundError("Item", require_id(item), code="ITEM_NOT_FOUND")
        statements = await self._items.outcome_statements(updated.topic_id)
        await self._ai.submit_job(
            ContentJobType.ITEM_REVIEW,
            {
                "items": [
                    {
                        "item_id": str(require_id(updated)),
                        "item_type": updated.item_type,
                        "bloom_level": updated.bloom_level,
                        "stem": updated.stem,
                        "options": updated.options or [],
                        "correct_option": (
                            int(updated.correct_option) if updated.correct_option else None
                        ),
                        "rubric": updated.rubric or [],
                        "outcome": statements.get(updated.learning_outcome_id or 0, ""),
                    }
                ]
            },
            f"{ContentJobType.ITEM_REVIEW}:item:{require_id(updated)}:{item_digest(updated)}",
            JobRefs(course_id=topic.course_id, topic_id=require_id(topic)),
        )
        await self._uow.commit()
        return updated


# --- Videos -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class VideoView:
    video: VideoCandidate
    relevance_judgment: bool | None


@dataclass(frozen=True)
class VideoQualityRow:
    video: VideoCandidate
    topic_name: str
    ratings: int
    by_rating: dict[str, int]
    watched_fully: int
    useful_rate: float | None
    quality_index: float | None
    measuring: bool
    status: str = "measuring"
    """`measuring`, `recommended`, `observation` o `under_review` (D5f)."""


def quality_status(quality_index: float | None) -> str:
    """Estado del video según su índice; sin índice (pocas calificaciones) está midiéndose."""
    if quality_index is None:
        return "measuring"
    if quality_index >= VIDEO_QUALITY_RECOMMENDED:
        return "recommended"
    if quality_index >= VIDEO_QUALITY_OBSERVATION:
        return "observation"
    return "under_review"


def bayesian_quality(
    useful: int, total: int, prior_mean: float = 0.5, prior_weight: int = 5
) -> float:
    """Media bayesiana de «útil»: con pocas calificaciones se acerca a la media previa."""
    return (prior_weight * prior_mean + useful) / (prior_weight + total)


class VideoService:
    def __init__(
        self,
        videos: VideoRepository,
        resources: ResourceRepository,
        topics: TopicRepository,
        courses: CourseRepository,
        paths: PathLookup,
        feedback: FeedbackRepository,
        uow: UnitOfWork,
    ) -> None:
        self._videos = videos
        self._resources = resources
        self._topics = topics
        self._courses = courses
        self._paths = paths
        self._feedback = feedback
        self._uow = uow

    async def list_for_topic(self, user: CurrentUser, topic_id: int) -> list[VideoView]:
        await load_topic(self._topics, self._courses, user, topic_id)
        videos = await self._videos.list_for_topic(topic_id)
        judged = await self._videos.judgments_of(user.id, [require_id(v) for v in videos])
        return [VideoView(v, judged.get(require_id(v))) for v in videos]

    async def topic_name(self, user: CurrentUser, topic_id: int) -> str:
        return (await load_topic(self._topics, self._courses, user, topic_id)).name

    async def _load(self, user: CurrentUser, video_id: int) -> tuple[VideoCandidate, Topic]:
        video = await self._videos.get(video_id)
        if video is None or not video.active:
            raise NotFoundError("Video candidate", video_id, code="RESOURCE_NOT_FOUND")
        try:
            topic = await load_topic(self._topics, self._courses, user, video.topic_id)
        except NotFoundError as exc:
            raise NotFoundError("Video candidate", video_id, code="RESOURCE_NOT_FOUND") from exc
        return video, topic

    async def update(
        self, user: CurrentUser, video_id: int, *, status: str | None, is_relevant: bool | None
    ) -> VideoView:
        video, topic = await self._load(user, video_id)
        if status is None and is_relevant is None:
            raise BusinessRuleError("Nothing to change.", code="VALIDATION_ERROR")
        await self._resources.lock_topic(video.topic_id)
        if is_relevant is not None:
            await self._videos.save_judgment(video_id, user.id, is_relevant)
        if status is not None and status != video.status:
            if status == VideoStatus.IN_USE:
                await self._videos.demote_in_use(video.topic_id, video_id)
            video = await self._videos.update(video_id, {"status": status}) or video
            await self._sync_video_resource(video, topic, user)
        await self._uow.commit()
        judged = await self._videos.judgments_of(user.id, [video_id])
        return VideoView(video, judged.get(video_id))

    async def _sync_video_resource(
        self, video: VideoCandidate, topic: Topic, user: CurrentUser
    ) -> None:
        """El video en uso tiene su fila en `resources`; si deja de estarlo, se retira."""
        video_id = require_id(video)
        existing = await self._resources.video_resource(video_id)
        if video.status == VideoStatus.IN_USE:
            if existing is None:
                await self._resources.add(
                    Resource(
                        topic_id=video.topic_id,
                        resource_type=ResourceType.VIDEO,
                        review_status=ReviewStatus.APPROVED,
                        url=f"https://www.youtube.com/watch?v={video.youtube_video_id}",
                        video_candidate_id=video_id,
                        edited_by_user_id=user.id,
                    )
                )
            else:
                await self._resources.update(
                    require_id(existing), {"review_status": ReviewStatus.APPROVED}
                )
            current = await self._resources.video_resource(video_id)
            if current is not None:
                await self._resources.retire_other_approved(current)
        elif existing is not None:
            await self._resources.update(
                require_id(existing), {"review_status": ReviewStatus.RETIRED}
            )
        _ = topic

    async def add_manual(
        self,
        user: CurrentUser,
        topic_id: int,
        *,
        youtube_video_id: str,
        title: str,
        channel: str | None,
        duration_seconds: int | None,
        language: str | None,
    ) -> VideoView:
        await load_topic(self._topics, self._courses, user, topic_id)
        if await self._videos.get_by_youtube(topic_id, youtube_video_id) is not None:
            raise ConflictError("The video is already a candidate of the topic.")
        created = await self._videos.add(
            VideoCandidate(
                topic_id=topic_id,
                youtube_video_id=youtube_video_id,
                title=title,
                channel=channel,
                duration_seconds=duration_seconds,
                language=language,
                characterization_source=VideoOrigin.INSTRUCTOR.value,
                status=VideoStatus.BACKUP,
                origin=VideoOrigin.INSTRUCTOR,
            )
        )
        await self._uow.commit()
        return VideoView(created, None)

    async def quality(self, user: CurrentUser, path_id: int) -> list[VideoQualityRow]:
        path = await self._paths.get(path_id)
        if path is None or not path.active:
            raise NotFoundError("Learning path", path_id, code="NOT_FOUND")
        await load_course(self._courses, user, path.course_id)
        rows: list[VideoQualityRow] = []
        for topic in await self._topics.list_for_course(path.course_id):
            videos = [
                v
                for v in await self._videos.list_for_topic(require_id(topic))
                if v.status in (VideoStatus.IN_USE, VideoStatus.BACKUP)
            ]
            summaries = await self._feedback.summaries([require_id(v) for v in videos])
            for video in videos:
                rows.append(_quality_row(video, topic.name, summaries.get(require_id(video))))
        return rows


def _quality_row(
    video: VideoCandidate, topic_name: str, summary: RatingSummary | None
) -> VideoQualityRow:
    by_rating = dict(summary.ratings) if summary else {}
    total = sum(by_rating.values())
    useful = by_rating.get("useful", 0)
    measuring = total < VIDEO_QUALITY_MIN_RATINGS
    quality_index = None if measuring else round(bayesian_quality(useful, total), 4)
    return VideoQualityRow(
        video=video,
        topic_name=topic_name,
        ratings=total,
        by_rating=by_rating,
        watched_fully=summary.watched_fully if summary else 0,
        useful_rate=(useful / total) if total else None,
        quality_index=quality_index,
        measuring=measuring,
        status=quality_status(quality_index),
    )


class VideoFeedbackService:
    """`POST /me/video-feedback`: el aprendiz califica el video de su ruta (E6, CU-20)."""

    def __init__(
        self,
        videos: VideoRepository,
        feedback: FeedbackRepository,
        topics: TopicRepository,
        enrollments: EnrollmentLookup,
        uow: UnitOfWork,
    ) -> None:
        self._videos = videos
        self._feedback = feedback
        self._topics = topics
        self._enrollments = enrollments
        self._uow = uow

    async def submit(
        self,
        user: CurrentUser,
        *,
        video_candidate_id: int,
        enrollment_id: int,
        rating: str,
        comment: str | None,
        watched_fully: bool | None,
    ) -> tuple[VideoFeedback, bool]:
        """Devuelve la calificación y si es nueva (una repetida reemplaza a la anterior)."""
        course_id = await self._enrollments.course_of_learner_enrollment(enrollment_id, user.id)
        if course_id is None or not user.has_any_role(RoleCode.LEARNER):
            raise NotFoundError("Enrollment", enrollment_id, code="ENROLLMENT_NOT_FOUND")
        video = await self._videos.get(video_candidate_id)
        topic = await self._topics.get(video.topic_id) if video is not None else None
        if (
            video is None
            or not video.active
            or topic is None
            or topic.course_id != course_id
            or video.status not in (VideoStatus.IN_USE, VideoStatus.BACKUP)
        ):
            raise NotFoundError("Video candidate", video_candidate_id, code="RESOURCE_NOT_FOUND")
        existing = await self._feedback.find(video_candidate_id, enrollment_id)
        if existing is None:
            created = await self._feedback.add(
                VideoFeedback(
                    video_candidate_id=video_candidate_id,
                    enrollment_id=enrollment_id,
                    rating=rating,
                    comment=comment,
                    watched_fully=watched_fully,
                )
            )
            await self._uow.commit()
            return created, True
        updated = await self._feedback.update(
            require_id(existing),
            {"rating": rating, "comment": comment, "watched_fully": watched_fully},
        )
        await self._uow.commit()
        return updated or existing, False
