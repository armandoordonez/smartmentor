"""Endpoints de contenido: recursos, ítems, videos y su calidad (instructor y admin), y la
calificación de videos del aprendiz."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_roles
from app.auth.policies import LEARNER, STAFF
from app.common.entities import require_id
from app.common.schemas import Page
from app.core.idempotency import IdempotencyDep
from app.domains.ai_gateway.entities import JobRef
from app.domains.ai_gateway.schemas import JobAccepted
from app.domains.content.contracts import TopicExplanationBody
from app.domains.content.dependencies import (
    get_item_service,
    get_resource_service,
    get_video_feedback_service,
    get_video_service,
)
from app.domains.content.entities import AssessmentItem, Resource
from app.domains.content.schemas import (
    ItemResponse,
    ItemUpdate,
    ResourceEditResponse,
    ResourceResponse,
    ResourceReview,
    VideoCreate,
    VideoFeedbackCreate,
    VideoFeedbackResponse,
    VideoListResponse,
    VideoPatch,
    VideoQualityItem,
    VideoQualityResponse,
    VideoResponse,
)
from app.domains.content.service import (
    ItemChanges,
    ItemService,
    ResourceService,
    VideoFeedbackService,
    VideoService,
    VideoView,
    version_label,
)
from app.domains.identity.authentication import CurrentUser

StaffUser = Annotated[CurrentUser, Depends(require_roles(*STAFF))]
LearnerUser = Annotated[CurrentUser, Depends(require_roles(*LEARNER))]
ResourceServiceDep = Annotated[ResourceService, Depends(get_resource_service)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]
FeedbackServiceDep = Annotated[VideoFeedbackService, Depends(get_video_feedback_service)]


def _content(resource: Resource) -> dict[str, Any] | None:
    if resource.content is None:
        return None
    try:
        parsed = json.loads(resource.content)
    except ValueError:
        return {"text": resource.content}
    return parsed if isinstance(parsed, dict) else {"text": resource.content}


def _resource(resource: Resource) -> ResourceResponse:
    return ResourceResponse(
        id=require_id(resource),
        topic_id=resource.topic_id,
        resource_type=resource.resource_type,
        kind=resource.kind,
        audience=resource.audience,
        version=resource.version,
        version_label=version_label(resource.version),
        review_status=resource.review_status,
        url=resource.url,
        content=_content(resource),
        faithfulness=resource.faithfulness,
        unsupported_claims=resource.unsupported_claims,
        sources=resource.sources,
        prompt_version=resource.prompt_version,
        edited_by_user_id=resource.edited_by_user_id,
        video_candidate_id=resource.video_candidate_id,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


def _item(item: AssessmentItem) -> ItemResponse:
    return ItemResponse(
        id=require_id(item),
        topic_id=item.topic_id,
        learning_outcome_id=item.learning_outcome_id,
        source=item.source,
        item_type=item.item_type,
        bloom_level=item.bloom_level,
        difficulty=item.difficulty,
        stem=item.stem,
        options=item.options,
        correct_option=int(item.correct_option) if item.correct_option else None,
        model_answer=item.model_answer,
        rubric=item.rubric,
        equivalence_group=item.equivalence_group,
        review_status=item.review_status,
        auto_review=item.auto_review,
        prompt_version=item.prompt_version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _video(view: VideoView) -> VideoResponse:
    video = view.video
    return VideoResponse(
        id=require_id(video),
        topic_id=video.topic_id,
        youtube_video_id=video.youtube_video_id,
        url=f"https://www.youtube.com/watch?v={video.youtube_video_id}",
        title=video.title,
        channel=video.channel,
        duration_seconds=video.duration_seconds,
        language=video.language,
        has_captions=video.has_captions,
        characterization=video.characterization,
        characterization_source=video.characterization_source,
        similarity=video.similarity,
        rank=video.rank,
        status=video.status,
        origin=video.origin,
        relevance_judgment=view.relevance_judgment,
    )


def _accepted(job: JobRef) -> JobAccepted:
    return JobAccepted.for_job(job.job_id)


router = APIRouter(tags=["content"])


@router.get("/topics/{topic_id}/resources", response_model=list[ResourceResponse])
async def list_resources(
    topic_id: int, user: StaffUser, service: ResourceServiceDep
) -> list[ResourceResponse]:
    """Todas las versiones de las explicaciones y videos del tema (D5)."""
    return [_resource(r) for r in await service.list_for_topic(user, topic_id)]


@router.patch("/resources/{resource_id}/review", response_model=ResourceResponse)
async def review_resource(
    resource_id: int, payload: ResourceReview, user: StaffUser, service: ResourceServiceDep
) -> ResourceResponse:
    """Aprueba o retira un recurso; aprobar una versión retira la aprobada anterior."""
    return _resource(await service.review(user, resource_id, payload.review_status))


@router.put("/resources/{resource_id}/content", response_model=ResourceEditResponse)
async def edit_resource_content(
    resource_id: int, payload: TopicExplanationBody, user: StaffUser, service: ResourceServiceDep
) -> ResourceEditResponse:
    """La edición crea una versión nueva en `pending_review` y pide `content.check_faithfulness`."""
    edit = await service.edit_content(user, resource_id, payload)
    return ResourceEditResponse(
        **_resource(edit.resource).model_dump(), faithfulness_job_id=edit.faithfulness_job_id
    )


@router.post("/resources/{resource_id}/regenerate", response_model=JobAccepted, status_code=202)
async def regenerate_resource(
    resource_id: int,
    request: Request,
    user: StaffUser,
    service: ResourceServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Pide a `ai/` una explicación nueva del tema; llega como versión nueva en revisión."""

    async def action() -> JobAccepted:
        return _accepted(await service.regenerate(user, resource_id))

    return await idempotency.run(
        user_id=user.id,
        request=request,
        body=str(resource_id).encode(),
        action=action,
        location=lambda accepted: accepted.poll_url if isinstance(accepted, JobAccepted) else None,
    )


@router.get("/topics/{topic_id}/items", response_model=Page[ItemResponse])
async def list_items(
    topic_id: int,
    user: StaffUser,
    service: ItemServiceDep,
    source: Annotated[
        str | None, Query(pattern="^(diagnostic|topic_quiz|final|retention)$")
    ] = None,
    review_status: Annotated[
        str | None, Query(pattern="^(auto_rejected|pending_review|approved|retired)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ItemResponse]:
    items, total = await service.list_for_topic(
        user, topic_id, source=source, review_status=review_status, limit=limit, offset=offset
    )
    return Page[ItemResponse](
        items=[_item(i) for i in items], total=total, limit=limit, offset=offset
    )


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int, payload: ItemUpdate, user: StaffUser, service: ItemServiceDep
) -> ItemResponse:
    """Aprueba, retira o edita un ítem; editar lo devuelve a `pending_review` (`items.review`)."""
    changes = ItemChanges(
        review_status=payload.review_status,
        stem=payload.stem,
        options=payload.options,
        correct_option=payload.correct_option,
        model_answer=payload.model_answer,
        rubric=[c.model_dump() for c in payload.rubric] if payload.rubric is not None else None,
    )
    return _item(await service.update(user, item_id, changes))


@router.get("/topics/{topic_id}/video-candidates", response_model=VideoListResponse)
async def list_video_candidates(
    topic_id: int, user: StaffUser, service: VideoServiceDep
) -> VideoListResponse:
    views = await service.list_for_topic(user, topic_id)
    return VideoListResponse(
        topic_id=topic_id,
        topic_name=await service.topic_name(user, topic_id),
        has_backup=any(v.video.status == "backup" for v in views),
        candidates=[_video(v) for v in views],
    )


@router.post("/topics/{topic_id}/video-candidates", response_model=VideoResponse, status_code=201)
async def add_video_candidate(
    topic_id: int, payload: VideoCreate, user: StaffUser, service: VideoServiceDep
) -> VideoResponse:
    """Agrega un video a mano como respaldo (`origin=instructor`)."""
    return _video(
        await service.add_manual(
            user,
            topic_id,
            youtube_video_id=payload.youtube_video_id,
            title=payload.title,
            channel=payload.channel,
            duration_seconds=payload.duration_seconds,
            language=payload.language,
        )
    )


@router.patch("/video-candidates/{video_id}", response_model=VideoResponse)
async def update_video_candidate(
    video_id: int, payload: VideoPatch, user: StaffUser, service: VideoServiceDep
) -> VideoResponse:
    """Juicio de pertinencia (P@3, nDCG@3), «usar este», respaldo o descarte (D5e)."""
    return _video(
        await service.update(user, video_id, status=payload.status, is_relevant=payload.is_relevant)
    )


@router.get("/learning-paths/{path_id}/video-quality", response_model=VideoQualityResponse)
async def video_quality(
    path_id: int, user: StaffUser, service: VideoServiceDep
) -> VideoQualityResponse:
    """Calidad de los videos de la ruta con las calificaciones de los aprendices (P2, D5f)."""
    rows = await service.quality(user, path_id)
    return VideoQualityResponse(
        learning_path_id=path_id,
        items=[
            VideoQualityItem(
                video=_video(VideoView(r.video, None)),
                topic_name=r.topic_name,
                ratings=r.ratings,
                by_rating=r.by_rating,
                watched_fully=r.watched_fully,
                useful_rate=r.useful_rate,
                quality_index=r.quality_index,
                measuring=r.measuring,
            )
            for r in rows
        ],
    )


@router.post("/me/video-feedback", response_model=VideoFeedbackResponse, status_code=201)
async def submit_video_feedback(
    payload: VideoFeedbackCreate,
    response: Response,
    user: LearnerUser,
    service: FeedbackServiceDep,
) -> VideoFeedbackResponse:
    """El aprendiz califica el video de su ruta; repetir la calificación la reemplaza (`200`)."""
    feedback, created = await service.submit(
        user,
        video_candidate_id=payload.video_candidate_id,
        enrollment_id=payload.enrollment_id,
        rating=payload.rating,
        comment=payload.comment,
        watched_fully=payload.watched_fully,
    )
    if not created:
        response.status_code = 200
    return VideoFeedbackResponse(
        video_candidate_id=feedback.video_candidate_id,
        enrollment_id=feedback.enrollment_id,
        rating=feedback.rating,
        comment=feedback.comment,
        watched_fully=feedback.watched_fully,
        created=created,
    )


routers: list[APIRouter] = [router]
