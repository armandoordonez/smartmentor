"""Endpoints de evaluación humana: evaluadores por curso, anotación ciega y calificación a mano."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN, INSTRUCTOR
from app.common.entities import require_id
from app.domains.evaluation.dependencies import (
    get_annotation_service,
    get_evaluator_admin_service,
    get_grading_service,
)
from app.domains.evaluation.entities import CourseEvaluator, ItemAnnotation
from app.domains.evaluation.schemas import (
    AnnotationCreate,
    AnnotationQueuePage,
    AnnotationResponse,
    EvaluatorCreate,
    EvaluatorResponse,
    GradingQueueEntry,
    GradingQueuePage,
    HumanGradingCreate,
    HumanGradingResponse,
    LlmGradeResponse,
    QueueItem,
)
from app.domains.evaluation.service import (
    AnnotationInput,
    AnnotationQueueEntry,
    AnnotationService,
    EvaluatorAdminService,
    GradingInput,
    GradingService,
)
from app.domains.identity.authentication import CurrentUser

AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN))]
InstructorUser = Annotated[CurrentUser, Depends(require_roles(*INSTRUCTOR))]
AdminServiceDep = Annotated[EvaluatorAdminService, Depends(get_evaluator_admin_service)]
AnnotationServiceDep = Annotated[AnnotationService, Depends(get_annotation_service)]
GradingServiceDep = Annotated[GradingService, Depends(get_grading_service)]


def _evaluator(evaluator: CourseEvaluator) -> EvaluatorResponse:
    return EvaluatorResponse(
        id=require_id(evaluator),
        course_id=evaluator.course_id,
        user_id=evaluator.user_id,
        assigned_by_user_id=evaluator.assigned_by_user_id,
        created_at=evaluator.created_at,
    )


def _annotation(annotation: ItemAnnotation) -> AnnotationResponse:
    return AnnotationResponse(
        id=require_id(annotation),
        assessment_item_id=annotation.assessment_item_id,
        evaluator_slot=annotation.evaluator_slot,
        single_correct=annotation.single_correct,
        clear_stem=annotation.clear_stem,
        bloom_ok=annotation.bloom_ok,
        plausible_distractors=annotation.plausible_distractors,
        verdict=annotation.verdict,
        comment=annotation.comment,
        created_at=annotation.created_at,
    )


def _queue_item(entry: AnnotationQueueEntry) -> QueueItem:
    item = entry.item
    return QueueItem(
        id=require_id(item),
        topic_id=item.topic_id,
        topic_name=entry.topic_name,
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
        review_status=item.review_status,
        own_annotation=(
            _annotation(entry.own_annotation) if entry.own_annotation is not None else None
        ),
        evaluator_slot=entry.evaluator_slot,
    )


router = APIRouter(tags=["evaluation"])


@router.get("/courses/{course_id}/evaluators", response_model=list[EvaluatorResponse])
async def list_evaluators(
    course_id: int, user: AdminUser, service: AdminServiceDep
) -> list[EvaluatorResponse]:
    return [_evaluator(e) for e in await service.list_for_course(user, course_id)]


@router.post("/courses/{course_id}/evaluators", response_model=EvaluatorResponse, status_code=201)
async def assign_evaluator(
    course_id: int, payload: EvaluatorCreate, user: AdminUser, service: AdminServiceDep
) -> EvaluatorResponse:
    """Asigna un instructor (que no es el dueño) como evaluador del curso (DEF-24)."""
    return _evaluator(await service.assign(user, course_id, payload.user_id))


@router.patch("/course-evaluators/{evaluator_id}/deactivate", response_model=EvaluatorResponse)
async def remove_evaluator(
    evaluator_id: int, user: AdminUser, service: AdminServiceDep
) -> EvaluatorResponse:
    return _evaluator(await service.remove(user, evaluator_id))


@router.get("/evaluation/annotation-queue", response_model=AnnotationQueuePage)
async def annotation_queue(
    user: InstructorUser,
    service: AnnotationServiceDep,
    course_id: Annotated[int | None, Query(gt=0)] = None,
    done: Annotated[bool, Query(description="Los ya anotados por mí (solo mi anotación)")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnnotationQueuePage:
    """Ítems por anotar. La anotación del otro evaluador nunca se devuelve (anotación ciega)."""
    entries, total = await service.queue(
        user, course_id=course_id, done=done, limit=limit, offset=offset
    )
    return AnnotationQueuePage(
        annotated=await service.annotated_count(user, course_id=course_id),
        items=[_queue_item(e) for e in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/items/{item_id}/annotations", response_model=AnnotationResponse, status_code=201)
async def annotate_item(
    item_id: int, payload: AnnotationCreate, user: InstructorUser, service: AnnotationServiceDep
) -> AnnotationResponse:
    created = await service.annotate(user, item_id, AnnotationInput(**payload.model_dump()))
    return _annotation(created)


@router.get("/evaluation/grading-queue", response_model=GradingQueuePage)
async def grading_queue(
    user: InstructorUser,
    service: GradingServiceDep,
    sample: Annotated[Literal["random", "learner_request"], Query()] = "random",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GradingQueuePage:
    """Respuestas cortas por calificar a mano. La nota del LLM no se devuelve aquí."""
    answers, total = await service.queue(user, sample=sample, limit=limit, offset=offset)
    return GradingQueuePage(
        graded=await service.graded_count(user, sample=sample),
        items=[
            GradingQueueEntry(
                attempt_answer_id=a.answer_id,
                item_id=a.item_id,
                topic_id=a.topic_id,
                topic_name=a.topic_name,
                stem=a.stem,
                model_answer=a.model_answer,
                rubric=a.rubric,
                text_answer=a.text_answer,
                review_requested_at=a.review_requested_at,
            )
            for a in answers
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/attempt-answers/{answer_id}/human-gradings",
    response_model=HumanGradingResponse,
    status_code=201,
)
async def grade_answer(
    answer_id: int, payload: HumanGradingCreate, user: InstructorUser, service: GradingServiceDep
) -> HumanGradingResponse:
    """Guarda la calificación humana y recién entonces devuelve la nota del LLM para comparar."""
    result = await service.grade(
        user,
        answer_id,
        GradingInput(
            criteria=[c.model_dump() for c in payload.criteria],
            score=payload.score,
            sample_type=payload.sample_type,
        ),
    )
    grading = result.grading
    return HumanGradingResponse(
        id=require_id(grading),
        attempt_answer_id=grading.attempt_answer_id,
        sample_type=grading.sample_type,
        criteria=grading.criteria,
        score=grading.score,
        llm_grading=LlmGradeResponse(
            score=result.llm.score,
            is_correct=result.llm.is_correct,
            rubric_detail=result.llm.rubric_detail,
            feedback=result.llm.feedback,
        ),
        created_at=grading.created_at,
    )


routers: list[APIRouter] = [router]
