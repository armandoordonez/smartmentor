"""Ingestores de los trabajos de contenido que llegan de `ai/` (modelo pull, plan 5.3.3).

Cada ingestor es idempotente sin tabla propia: decide si ya ingirió el trabajo mirando el estado de
su entidad con el tema bloqueado (`SELECT ... FOR NO KEY UPDATE`), de modo que dos consultas
simultáneas, o una consulta y el barrido, no duplican nada:

- explicaciones: un texto principal creado en o después del `created_at` del trabajo ya lo ingiere;
- calidad de la explicación (`content.check_faithfulness`): solo si la versión aún no tiene medida;
- bancos de ítems: cada ítem se identifica por (tema, banco, enunciado); no se repite;
- revisión de ítems (`items.review`): solo ítems en `pending_review` sin revisión automática;
- videos: (tema, `youtube_video_id`) es único; un candidato existente conserva su estado.
"""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.common.constants import CourseStatus, RoleCode
from app.common.entities import require_id
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.entities import JobRefs, JobStatus, PendingJob
from app.domains.ai_gateway.exceptions import AiResultInvalidError
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.content.constants import (
    ContentJobType,
    ResourceKind,
    ResourceType,
    ReviewStatus,
    VideoStatus,
)
from app.domains.content.contracts import (
    AssessmentItemBankV1,
    FaithfulnessCheckV1,
    ItemReviewEntry,
    ItemReviewResultV1,
    TopicExplanationV1,
    VideoResourceV1,
)
from app.domains.content.entities import AssessmentItem, Resource, VideoCandidate
from app.domains.content.repository import ItemRepository, ResourceRepository, VideoRepository
from app.domains.courses.entities import Topic
from app.domains.courses.repository import CourseRepository, TopicRepository
from app.domains.identity.authentication import CurrentUser

EPOCH = datetime.min.replace(tzinfo=UTC)
PENDING_WINDOW_DAYS = 7
_STATUSES_WITH_CONTENT = (CourseStatus.GENERATING_CONTENT, CourseStatus.PUBLISHED)


class _ContentIngestor:
    """Base: propiedad del trabajo, búsqueda de pendientes y regla del trabajo más reciente."""

    job_type: str
    progress_label: str

    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._topics_repo = topics
        self._ai = ai
        self._uow = uow

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        if refs.course_id is None or not user.has_any_role(RoleCode.INSTRUCTOR):
            return False
        course = await self._courses.get(refs.course_id)
        return course is not None and course.owner_user_id == user.id

    async def on_failed(self, job: JobStatus, error_code: str) -> None:  # noqa: ARG002
        # Un trabajo de contenido que falla no deja nada a medias: el instructor lo reintenta.
        await self._uow.commit()

    async def _topic_for(self, job: JobStatus, claimed: str | None) -> Topic:
        """El tema del trabajo (de `refs`, o del resultado) y que sea del curso del trabajo."""
        raw = job.refs.topic_id if job.refs.topic_id is not None else claimed
        if raw is None or not str(raw).isdigit():
            raise AiResultInvalidError(job.job_id)
        topic = await self._topics_repo.get(int(raw))
        if topic is None or not topic.active:
            raise AiResultInvalidError(job.job_id)
        if job.refs.course_id is not None and topic.course_id != job.refs.course_id:
            raise AiResultInvalidError(job.job_id)
        return topic

    async def _recent_finished(self) -> list[JobStatus]:
        found: list[JobStatus] = []
        cutoff = datetime.now(UTC).timestamp() - PENDING_WINDOW_DAYS * 86400
        for status in _STATUSES_WITH_CONTENT:
            for course in await self._courses.list_by_status(status):
                for job in await self._ai.list_jobs(
                    job_type=self.job_type, course_id=require_id(course), limit=100
                ):
                    when = job.finished_at or job.created_at or EPOCH
                    if job.status == "succeeded" and when.timestamp() >= cutoff:
                        found.append(job)
        return found

    async def _is_latest_for_topic(self, job: JobStatus) -> bool:
        if job.refs.course_id is None:
            return True
        same = [
            j
            for j in await self._ai.list_jobs(
                job_type=self.job_type, course_id=job.refs.course_id, limit=100
            )
            if j.refs.topic_id == job.refs.topic_id
        ]
        if not same:
            return True
        newest = max(enumerate(same), key=lambda p: (p[1].created_at or EPOCH, p[0]))[1]
        return newest.job_id == job.job_id

    async def _is_pending(self, job: JobStatus) -> bool:
        raise NotImplementedError

    async def pending_jobs(self) -> list[PendingJob]:
        return [
            PendingJob(job_id=j.job_id, job_type=self.job_type)
            for j in await self._recent_finished()
            if await self._is_pending(j)
        ]


def _digits(value: str | None) -> int | None:
    return int(value) if value is not None and value.isdigit() else None


# --- content.explain_topic --------------------------------------------------------------------


class ExplanationIngestor(_ContentIngestor):
    """`content.explain_topic` → una versión nueva del texto principal en `pending_review`."""

    job_type = ContentJobType.EXPLAIN_TOPIC.value
    result_model: type[BaseModel] = TopicExplanationV1
    progress_label = "Redactando la explicación del tema"

    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        resources: ResourceRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(courses, topics, ai, uow)
        self._resources = resources

    async def _is_pending(self, job: JobStatus) -> bool:
        if job.refs.topic_id is None:
            return False
        return not await self._resources.exists_main_text_since(
            job.refs.topic_id, job.created_at or EPOCH
        )

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, TopicExplanationV1):
            raise TypeError("ExplanationIngestor expects a TopicExplanationV1 result.")
        if result.kind != "main" or result.audience != "all_learners":
            raise AiResultInvalidError(job.job_id)
        topic = await self._topic_for(job, result.topic_id)
        topic_id = require_id(topic)
        await self._resources.lock_topic(topic_id)
        if await self._resources.exists_main_text_since(
            topic_id, job.created_at or EPOCH
        ) or not await self._is_latest_for_topic(job):
            await self._uow.commit()
            return False
        body = result.model_dump(
            mode="json",
            include={"title", "sections", "worked_example", "summary", "reflection_questions"}
            | {"gaps_detected", "sources"},
        )
        await self._resources.add(
            Resource(
                topic_id=topic_id,
                resource_type=ResourceType.TEXT,
                kind=ResourceKind.MAIN,
                version=await self._resources.max_version(topic_id) + 1,
                review_status=ReviewStatus.PENDING_REVIEW,
                content=json.dumps(body, ensure_ascii=False),
                faithfulness=result.faithfulness,
                unsupported_claims=list(result.unsupported_claims),
                sources=[s.model_dump(mode="json") for s in result.sources],
                prompt_version=f"{result.meta.prompt_id} {result.meta.prompt_version}",
            )
        )
        await self._uow.commit()
        return True


# --- content.check_faithfulness ---------------------------------------------------------------


class FaithfulnessIngestor(_ContentIngestor):
    """`content.check_faithfulness` → fidelidad de la versión editada (D5d)."""

    job_type = ContentJobType.CHECK_FAITHFULNESS.value
    result_model: type[BaseModel] = FaithfulnessCheckV1
    progress_label = "Comprobando la fidelidad de la explicación"

    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        resources: ResourceRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(courses, topics, ai, uow)
        self._resources = resources

    async def _awaiting(self, topic_id: int) -> Resource | None:
        latest = await self._resources.latest_main_text(topic_id)
        if (
            latest is not None
            and latest.edited_by_user_id is not None
            and latest.faithfulness is None
        ):
            return latest
        return None

    async def _is_pending(self, job: JobStatus) -> bool:
        return job.refs.topic_id is not None and await self._awaiting(job.refs.topic_id) is not None

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, FaithfulnessCheckV1):
            raise TypeError("FaithfulnessIngestor expects a FaithfulnessCheckV1 result.")
        topic = await self._topic_for(job, None)
        topic_id = require_id(topic)
        await self._resources.lock_topic(topic_id)
        target = await self._awaiting(topic_id)
        if target is None or not await self._is_latest_for_topic(job):
            await self._uow.commit()
            return False
        await self._resources.update(
            require_id(target),
            {
                "faithfulness": result.faithfulness,
                "unsupported_claims": list(result.unsupported_claims),
            },
        )
        await self._uow.commit()
        return True


# --- bancos de ítems --------------------------------------------------------------------------


def _review_dict(entry: ItemReviewEntry) -> dict[str, Any]:
    return entry.model_dump(mode="json")


class ItemBankIngestor(_ContentIngestor):
    """Bancos `assessment_item_bank.v1` (diagnóstico, quiz del tema y final): ítems al banco.

    Los ítems sin una sola respuesta correcta (`discarded_item_ids`) quedan `auto_rejected` (L-03);
    el resto, `pending_review` para que el instructor los apruebe (ADR 0015).
    """

    result_model: type[BaseModel] = AssessmentItemBankV1

    def __init__(
        self,
        job_type: ContentJobType,
        label: str,
        courses: CourseRepository,
        topics: TopicRepository,
        items: ItemRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(courses, topics, ai, uow)
        self.job_type = job_type.value
        self.progress_label = label
        self._items = items

    async def _is_pending(self, job: JobStatus) -> bool:
        public = await self._items.resolve_ai_job_id(job.job_id)
        return public is None or await self._items.count_for_job(public) == 0

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, AssessmentItemBankV1):
            raise TypeError("ItemBankIngestor expects an AssessmentItemBankV1 result.")
        ai_job_id = await self._items.resolve_ai_job_id(job.job_id)
        if ai_job_id is not None and await self._items.count_for_job(ai_job_id) > 0:
            await self._uow.commit()
            return False
        reviews = {r.item_id: r for r in result.item_reviews}
        discarded = set(result.discarded_item_ids)
        topics: dict[int, Topic] = {}
        outcomes: dict[int, dict[int, str]] = {}
        created = 0
        for raw in result.items:
            topic_id = _digits(raw.topic_id)
            if topic_id is None:
                raise AiResultInvalidError(job.job_id)
            if topic_id not in topics:
                topics[topic_id] = await self._topic_for(
                    JobStatus(
                        job_id=job.job_id,
                        job_type=job.job_type,
                        status=job.status,
                        refs=JobRefs(course_id=job.refs.course_id, topic_id=topic_id),
                    ),
                    None,
                )
                outcomes[topic_id] = await self._items.outcome_statements(topic_id)
                await self._lock(topic_id)
            if await self._exists(topic_id, raw.source, raw.stem):
                continue
            outcome_id = _digits(raw.outcome_id)
            review = reviews.get(raw.id)
            await self._items.add(
                AssessmentItem(
                    topic_id=topic_id,
                    learning_outcome_id=outcome_id if outcome_id in outcomes[topic_id] else None,
                    source=raw.source,
                    item_type=raw.item_type,
                    bloom_level=raw.bloom_level,
                    difficulty=raw.difficulty,
                    stem=raw.stem,
                    options=list(raw.options) if raw.item_type == "multiple_choice" else None,
                    correct_option=(
                        str(raw.correct_option) if raw.correct_option is not None else None
                    ),
                    model_answer=raw.model_answer,
                    rubric=[c.model_dump() for c in raw.rubric] or None,
                    equivalence_group=raw.equivalence_group,
                    review_status=(
                        ReviewStatus.AUTO_REJECTED
                        if raw.id in discarded
                        else ReviewStatus.PENDING_REVIEW
                    ),
                    auto_review=_review_dict(review) if review is not None else None,
                    prompt_version=f"{result.meta.prompt_id} {result.meta.prompt_version}",
                    ai_job_id=ai_job_id,
                )
            )
            created += 1
        await self._uow.commit()
        return created > 0

    async def _lock(self, topic_id: int) -> None:
        # El bloqueo del tema serializa dos ingestas del mismo banco (consulta + barrido).
        await self._items.lock_topic(topic_id)

    async def _exists(self, topic_id: int, source: str, stem: str) -> bool:
        return await self._items.exists(topic_id, source, stem)


class ItemReviewIngestor(_ContentIngestor):
    """`items.review` → revisión automática de ítems editados por el instructor (D5)."""

    job_type = ContentJobType.ITEM_REVIEW.value
    result_model: type[BaseModel] = ItemReviewResultV1
    progress_label = "Revisando los ítems editados"

    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        items: ItemRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(courses, topics, ai, uow)
        self._items = items

    async def _is_pending(self, job: JobStatus) -> bool:
        # No sabemos qué ítems revisó sin su resultado: se deja a la consulta directa.
        _ = job
        return False

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, ItemReviewResultV1):
            raise TypeError("ItemReviewIngestor expects an ItemReviewResultV1 result.")
        discarded = set(result.discarded_item_ids)
        changed = False
        for review in result.reviews:
            item_id = _digits(review.item_id)
            item = await self._items.get_for_update(item_id) if item_id is not None else None
            if (
                item is None
                or not item.active
                or item.review_status != ReviewStatus.PENDING_REVIEW
                or item.auto_review is not None
                or (job.refs.topic_id is not None and item.topic_id != job.refs.topic_id)
            ):
                continue
            changes: dict[str, Any] = {"auto_review": _review_dict(review)}
            if review.item_id in discarded:
                changes["review_status"] = ReviewStatus.AUTO_REJECTED
            await self._items.update(require_id(item), changes)
            changed = True
        await self._uow.commit()
        return changed


# --- video.collect_candidates -----------------------------------------------------------------


class VideoIngestor(_ContentIngestor):
    """`video.collect_candidates` → candidatos de video del tema (D5e).

    Un candidato que ya existe conserva el estado que le dio el instructor; solo se actualizan sus
    metadatos y su puesto. Solo hay un video `in_use` por tema: si ya hay uno, el seleccionado por
    `ai/` queda como candidato.
    """

    job_type = ContentJobType.VIDEO_CANDIDATES.value
    result_model: type[BaseModel] = VideoResourceV1
    progress_label = "Buscando videos del tema"

    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        videos: VideoRepository,
        resources: ResourceRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(courses, topics, ai, uow)
        self._videos = videos
        self._resources = resources

    async def _is_pending(self, job: JobStatus) -> bool:
        return job.refs.topic_id is not None and not await self._videos.list_for_topic(
            job.refs.topic_id
        )

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, VideoResourceV1):
            raise TypeError("VideoIngestor expects a VideoResourceV1 result.")
        topic = await self._topic_for(job, result.topic_id)
        topic_id = require_id(topic)
        await self._resources.lock_topic(topic_id)
        existing = await self._videos.list_for_topic(topic_id)
        has_in_use = any(v.status == VideoStatus.IN_USE for v in existing)
        created = 0
        for candidate in result.candidates:
            status = VideoStatus.CANDIDATE
            if candidate.youtube_video_id == result.selected_video_id and not has_in_use:
                status = VideoStatus.IN_USE
            elif candidate.youtube_video_id in result.backup_video_ids:
                status = VideoStatus.BACKUP
            values: dict[str, Any] = {
                "title": candidate.title,
                "channel": candidate.channel or None,
                "duration_seconds": candidate.duration_seconds,
                "language": candidate.language,
                "has_captions": candidate.has_captions,
                "characterization": candidate.characterization,
                "characterization_source": candidate.characterization_source,
                "similarity": candidate.similarity,
                "rank": candidate.rank,
            }
            known = await self._videos.get_by_youtube(topic_id, candidate.youtube_video_id)
            if known is not None:
                await self._videos.update(require_id(known), values)
                continue
            video = await self._videos.add(
                VideoCandidate(
                    topic_id=topic_id,
                    youtube_video_id=candidate.youtube_video_id,
                    status=status,
                    origin=candidate.origin,
                    **values,
                )
            )
            created += 1
            if status == VideoStatus.IN_USE:
                has_in_use = True
                await self._resources.add(
                    Resource(
                        topic_id=topic_id,
                        resource_type=ResourceType.VIDEO,
                        review_status=ReviewStatus.APPROVED,
                        url=candidate.url,
                        video_candidate_id=require_id(video),
                    )
                )
        await self._uow.commit()
        return created > 0
