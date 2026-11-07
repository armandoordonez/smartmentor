"""Endpoints de cursos, syllabus, temas y publicación (instructor y administrador)."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN, STAFF
from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.common.schemas import Page
from app.core.config import get_settings
from app.core.idempotency import IdempotencyDep
from app.domains.ai_gateway.entities import JobRef
from app.domains.ai_gateway.schemas import JobAccepted
from app.domains.courses.dependencies import (
    get_course_service,
    get_publication_service,
    get_syllabus_service,
    get_topic_service,
)
from app.domains.courses.schemas import (
    CourseCreate,
    CourseOwnerUpdate,
    CourseResponse,
    CourseUpdate,
    ExtractionMetricsResponse,
    ExtractionRequest,
    GraphEdge,
    GraphNode,
    LearningPathSummary,
    OutcomeResponse,
    ReviewCounts,
    ScoreResponse,
    SyllabusTextBody,
    TopicGraphResponse,
    TopicListResponse,
    TopicResponse,
    TopicWrite,
)
from app.domains.courses.service import (
    CourseService,
    CourseView,
    OutcomeDraft,
    PublicationService,
    Score,
    SyllabusService,
    TopicDraft,
    TopicService,
    TopicView,
)
from app.domains.courses.syllabus_text import (
    ExtractedSyllabus,
    extract_from_pdf,
    extract_from_text,
)
from app.domains.identity.authentication import CurrentUser

staff = Depends(require_roles(*STAFF))
StaffUser = Annotated[CurrentUser, Depends(require_roles(*STAFF))]
AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN))]
CourseServiceDep = Annotated[CourseService, Depends(get_course_service)]
SyllabusServiceDep = Annotated[SyllabusService, Depends(get_syllabus_service)]
TopicServiceDep = Annotated[TopicService, Depends(get_topic_service)]
PublicationServiceDep = Annotated[PublicationService, Depends(get_publication_service)]

# Margen sobre el límite del archivo para la cabecera multipart y el nombre del campo.
_MULTIPART_OVERHEAD_BYTES = 64 * 1024
_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}

SYLLABUS_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {"file": {"type": "string", "format": "binary"}},
                    "required": ["file"],
                }
            },
            "application/json": {"schema": SyllabusTextBody.model_json_schema()},
        },
    }
}


def _course_response(view: CourseView) -> CourseResponse:
    course, path = view.course, view.learning_path
    return CourseResponse(
        id=require_id(course),
        name=course.name,
        description=course.description,
        status=course.status,
        owner_user_id=course.owner_user_id,
        extraction_error_code=course.extraction_error_code,
        extraction_job_id=view.extraction_job_id,
        learning_path=(
            LearningPathSummary(
                id=require_id(path),
                name=path.name,
                group_label=path.group_label,
                status=path.status,
            )
            if path is not None
            else None
        ),
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


def _topic_response(view: TopicView) -> TopicResponse:
    topic = view.topic
    return TopicResponse(
        id=require_id(topic),
        course_id=topic.course_id,
        name=topic.name,
        description=topic.description,
        subtopics=[str(s) for s in topic.subtopics],
        position=topic.position,
        estimated_minutes=topic.estimated_minutes,
        is_mandatory=topic.is_mandatory,
        bloom_level=topic.bloom_level,
        origin=topic.origin,
        review_status=topic.review_status,
        extraction_key=topic.extraction_key,
        learning_outcomes=[
            OutcomeResponse(
                id=require_id(o), code=o.code, statement=o.statement, bloom_level=o.bloom_level
            )
            for o in view.learning_outcomes
        ],
        prerequisite_topic_ids=view.prerequisite_topic_ids,
    )


def _draft(payload: TopicWrite) -> TopicDraft:
    return TopicDraft(
        name=payload.name,
        description=payload.description,
        subtopics=payload.subtopics,
        position=payload.position,
        estimated_minutes=payload.estimated_minutes,
        is_mandatory=payload.is_mandatory,
        bloom_level=payload.bloom_level.value if payload.bloom_level else None,
        learning_outcomes=[
            OutcomeDraft(id=o.id, statement=o.statement, bloom_level=o.bloom_level.value)
            for o in payload.learning_outcomes
        ],
        prerequisite_topic_ids=payload.prerequisite_topic_ids,
    )


def _score(score: Score | None) -> ScoreResponse | None:
    return None if score is None else ScoreResponse(**score.__dict__)


def _accepted(job: JobRef) -> JobAccepted:
    return JobAccepted.for_job(job.job_id)


def _location(accepted: object) -> str | None:
    return accepted.poll_url if isinstance(accepted, JobAccepted) else None


async def _read_syllabus(request: Request) -> ExtractedSyllabus:
    """Lee el syllabus de la petición: PDF (multipart) o texto (JSON) y extrae su texto."""
    max_bytes = get_settings().syllabus_max_bytes
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "multipart/form-data":
        declared = request.headers.get("content-length")
        if (
            declared
            and declared.isdigit()
            and int(declared) > max_bytes + _MULTIPART_OVERHEAD_BYTES
        ):
            raise _too_large(max_bytes)
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise BusinessRuleError("The form needs a `file` field.", code="VALIDATION_ERROR")
        data = await upload.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise _too_large(max_bytes)
        name = upload.filename or ""
        declared_type = (upload.content_type or "").lower()
        if declared_type not in _PDF_CONTENT_TYPES and not name.lower().endswith(".pdf"):
            raise UnsupportedMediaTypeError(
                "Only PDF files or plain text are accepted.", code="SYLLABUS_UNSUPPORTED_TYPE"
            )
        return await extract_from_pdf(data, name or None)
    if content_type == "application/json":
        try:
            body = SyllabusTextBody.model_validate(json.loads(await request.body()))
        except (ValidationError, ValueError) as exc:
            raise BusinessRuleError(
                'The body must be {"text": "..."} with a non-empty text.', code="VALIDATION_ERROR"
            ) from exc
        return extract_from_text(body.text)
    raise UnsupportedMediaTypeError(
        "Send a PDF as multipart/form-data or the text as application/json.",
        code="SYLLABUS_UNSUPPORTED_TYPE",
    )


def _too_large(max_bytes: int) -> PayloadTooLargeError:
    return PayloadTooLargeError(
        f"The syllabus exceeds {max_bytes // (1024 * 1024)} MB.", code="SYLLABUS_TOO_LARGE"
    )


router = APIRouter(tags=["courses"])


@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course(
    payload: CourseCreate, user: StaffUser, service: CourseServiceDep
) -> CourseResponse:
    path = payload.learning_path
    return _course_response(
        await service.create(
            user,
            name=payload.name,
            description=payload.description,
            path_name=path.name if path else None,
            group_label=path.group_label if path else None,
        )
    )


@router.get("/courses", response_model=Page[CourseResponse])
async def list_courses(
    user: StaffUser,
    service: CourseServiceDep,
    mine: Annotated[bool, Query(description="Solo los míos (forzado para un instructor)")] = False,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CourseResponse]:
    views, total = await service.list_courses(
        user, mine=mine, status=status, limit=limit, offset=offset
    )
    return Page[CourseResponse](
        items=[_course_response(v) for v in views], total=total, limit=limit, offset=offset
    )


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, user: StaffUser, service: CourseServiceDep) -> CourseResponse:
    return _course_response(await service.get(user, course_id))


@router.patch("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int, payload: CourseUpdate, user: StaffUser, service: CourseServiceDep
) -> CourseResponse:
    changes = payload.model_dump(exclude_unset=True)
    return _course_response(await service.update(user, course_id, changes))


@router.patch("/courses/{course_id}/owner", response_model=CourseResponse)
async def assign_owner(
    course_id: int, payload: CourseOwnerUpdate, user: AdminUser, service: CourseServiceDep
) -> CourseResponse:
    """Asigna el instructor dueño del curso, o lo deja «Sin asignar» con `null` (AD5)."""
    return _course_response(await service.assign_owner(user, course_id, payload.owner_user_id))


@router.post(
    "/courses/{course_id}/syllabus",
    response_model=JobAccepted,
    status_code=202,
    openapi_extra=SYLLABUS_REQUEST_BODY,
)
async def upload_syllabus(
    course_id: int,
    request: Request,
    user: StaffUser,
    service: SyllabusServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Sube el syllabus (PDF ≤ 10 MB o texto), extrae su texto y encola `syllabus.structure`."""
    _ = idempotency.key  # 428 antes de leer el cuerpo
    extracted = await _read_syllabus(request)

    async def action() -> JobAccepted:
        return _accepted(await service.submit(user, course_id, extracted))

    return await idempotency.run(
        user_id=user.id,
        request=request,
        body=f"{course_id}:{extracted.sha256}".encode(),
        action=action,
        location=_location,
    )


@router.post("/courses/{course_id}/extractions", response_model=JobAccepted, status_code=202)
async def re_extract(
    course_id: int,
    payload: ExtractionRequest,
    request: Request,
    user: StaffUser,
    service: SyllabusServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Vuelve a extraer los temas del último syllabus; la revisión se reemplaza (D2c)."""

    async def action() -> JobAccepted:
        job = await service.re_extract(
            user, course_id, confirm_discard_review=payload.confirm_discard_review
        )
        return _accepted(job)

    return await idempotency.run(
        user_id=user.id, request=request, body=payload, action=action, location=_location
    )


@router.get("/courses/{course_id}/topics", response_model=TopicListResponse)
async def list_topics(
    course_id: int, user: StaffUser, service: TopicServiceDep
) -> TopicListResponse:
    result = await service.list_topics(user, course_id)
    counts = result.review_counts
    return TopicListResponse(
        topics=[_topic_response(v) for v in result.topics],
        review_counts=ReviewCounts(
            unchanged=counts["unchanged"],
            corrected=counts["corrected"],
            added=counts["added"],
            deleted=counts["deleted"],
        ),
    )


@router.get("/courses/{course_id}/topic-graph", response_model=TopicGraphResponse)
async def topic_graph(
    course_id: int, user: StaffUser, service: TopicServiceDep
) -> TopicGraphResponse:
    result = await service.graph(user, course_id)
    return TopicGraphResponse(
        nodes=[GraphNode(id=require_id(t), name=t.name, position=t.position) for t in result.nodes],
        edges=[
            GraphEdge(from_=e.prerequisite_topic_id, to=e.topic_id, origin=e.origin)
            for e in result.edges
        ],
    )


@router.post("/courses/{course_id}/topics", response_model=TopicResponse, status_code=201)
async def create_topic(
    course_id: int, payload: TopicWrite, user: StaffUser, service: TopicServiceDep
) -> TopicResponse:
    return _topic_response(await service.create(user, course_id, _draft(payload)))


@router.put("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: int, payload: TopicWrite, user: StaffUser, service: TopicServiceDep
) -> TopicResponse:
    """Actualiza el tema con sus resultados y prerrequisitos en una sola operación (D2b)."""
    return _topic_response(await service.update(user, topic_id, _draft(payload)))


@router.patch("/topics/{topic_id}/deactivate", response_model=TopicResponse)
async def deactivate_topic(
    topic_id: int, user: StaffUser, service: TopicServiceDep
) -> TopicResponse:
    return _topic_response(await service.deactivate(user, topic_id))


@router.post("/courses/{course_id}/publish", response_model=JobAccepted, status_code=202)
async def publish_course(
    course_id: int,
    request: Request,
    user: StaffUser,
    service: PublicationServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Valida el DAG y la revisión y dispara la generación del contenido (D2)."""

    async def action() -> JobAccepted:
        return _accepted(await service.publish(user, course_id))

    return await idempotency.run(
        user_id=user.id, request=request, body=b"", action=action, location=_location
    )


@router.get("/courses/{course_id}/extraction-metrics", response_model=ExtractionMetricsResponse)
async def extraction_metrics(
    course_id: int, user: StaffUser, service: SyllabusServiceDep
) -> ExtractionMetricsResponse:
    metrics = await service.metrics(user, course_id)
    return ExtractionMetricsResponse(
        topics=_score(metrics.topics),
        prerequisites=_score(metrics.prerequisites),
        corrections=metrics.corrections,
    )


routers: list[APIRouter] = [router]
