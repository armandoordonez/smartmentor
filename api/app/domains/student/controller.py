"""Endpoints del estudiante sobre sus propios datos: /me/enrollments y lo que cuelga de ellas.

Cualquier usuario autenticado con un rol puede usarlos (un docente también puede inscribirse), pero
solo ve y modifica lo suyo. El CRUD genérico de enrollments, path-steps, diagnostics, attempts y
badges sigue reservado al personal (admin y teacher).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentUserDep, require_roles
from app.auth.policies import ANY_ROLE
from app.common.schemas import Page
from app.domains.assessments.schemas import (
    AssessmentAttemptResponse,
    BadgeResponse,
    DiagnosticResponse,
)
from app.domains.learning_paths.schemas import EnrollmentResponse, PathStepResponse
from app.domains.student.dependencies import get_student_service
from app.domains.student.schemas import EnrollRequest, ProfileUpdate, SubmitAnswers
from app.domains.student.service import StudentService

router = APIRouter(
    prefix="/me",
    tags=["student"],
    dependencies=[Depends(require_roles(*ANY_ROLE))],
)

ServiceDep = Annotated[StudentService, Depends(get_student_service)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]


@router.get("/enrollments", response_model=Page[EnrollmentResponse])
async def list_my_enrollments(
    user: CurrentUserDep, service: ServiceDep, limit: LimitQuery = 20, offset: OffsetQuery = 0
) -> Page[EnrollmentResponse]:
    """Mis inscripciones activas."""
    items, total = await service.list_enrollments(user.id, limit=limit, offset=offset)
    return Page[EnrollmentResponse](
        items=[EnrollmentResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201)
async def enroll(
    payload: EnrollRequest, user: CurrentUserDep, service: ServiceDep
) -> EnrollmentResponse:
    """Me inscribo en una ruta. El usuario es siempre el del token."""
    enrollment = await service.enroll(
        user.id, payload.learning_path_id, payload.profile_description, payload.personal_objective
    )
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
async def get_my_enrollment(
    enrollment_id: int, user: CurrentUserDep, service: ServiceDep
) -> EnrollmentResponse:
    return EnrollmentResponse.model_validate(await service.get_enrollment(user.id, enrollment_id))


@router.patch("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
async def update_my_profile(
    enrollment_id: int, payload: ProfileUpdate, user: CurrentUserDep, service: ServiceDep
) -> EnrollmentResponse:
    """Actualizo la descripción de mi perfil y mi objetivo personal."""
    updated = await service.update_profile(
        user.id, enrollment_id, payload.model_dump(exclude_unset=True)
    )
    return EnrollmentResponse.model_validate(updated)


@router.patch("/enrollments/{enrollment_id}/abandon", response_model=EnrollmentResponse)
async def abandon_my_enrollment(
    enrollment_id: int, user: CurrentUserDep, service: ServiceDep
) -> EnrollmentResponse:
    """Dejo la ruta. Una inscripción completada no se puede abandonar."""
    return EnrollmentResponse.model_validate(await service.abandon(user.id, enrollment_id))


@router.get("/enrollments/{enrollment_id}/steps", response_model=Page[PathStepResponse])
async def list_my_steps(
    enrollment_id: int,
    user: CurrentUserDep,
    service: ServiceDep,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> Page[PathStepResponse]:
    """Mi ruta personalizada, en orden."""
    items, total = await service.list_steps(user.id, enrollment_id, limit=limit, offset=offset)
    return Page[PathStepResponse](
        items=[PathStepResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/enrollments/{enrollment_id}/diagnostic", response_model=DiagnosticResponse)
async def get_my_diagnostic(
    enrollment_id: int, user: CurrentUserDep, service: ServiceDep
) -> DiagnosticResponse:
    return DiagnosticResponse.model_validate(await service.get_diagnostic(user.id, enrollment_id))


@router.patch("/enrollments/{enrollment_id}/diagnostic/answers", response_model=DiagnosticResponse)
async def submit_my_diagnostic(
    enrollment_id: int, payload: SubmitAnswers, user: CurrentUserDep, service: ServiceDep
) -> DiagnosticResponse:
    """Entrego las respuestas del diagnóstico. Solo se puede una vez."""
    diagnostic = await service.submit_diagnostic(user.id, enrollment_id, payload.answers)
    return DiagnosticResponse.model_validate(diagnostic)


@router.get("/enrollments/{enrollment_id}/attempts", response_model=Page[AssessmentAttemptResponse])
async def list_my_attempts(
    enrollment_id: int,
    user: CurrentUserDep,
    service: ServiceDep,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
) -> Page[AssessmentAttemptResponse]:
    """Mis intentos de evaluación (quizzes de tema y evaluación final)."""
    items, total = await service.list_attempts(user.id, enrollment_id, limit=limit, offset=offset)
    return Page[AssessmentAttemptResponse](
        items=[AssessmentAttemptResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/enrollments/{enrollment_id}/attempts/{attempt_id}/submit",
    response_model=AssessmentAttemptResponse,
)
async def submit_my_attempt(
    enrollment_id: int,
    attempt_id: int,
    payload: SubmitAnswers,
    user: CurrentUserDep,
    service: ServiceDep,
) -> AssessmentAttemptResponse:
    """Entrego las respuestas de un intento. El puntaje y la aprobación los calcula el sistema."""
    attempt = await service.submit_attempt(user.id, enrollment_id, attempt_id, payload.answers)
    return AssessmentAttemptResponse.model_validate(attempt)


@router.get("/enrollments/{enrollment_id}/badge", response_model=BadgeResponse)
async def get_my_badge(
    enrollment_id: int, user: CurrentUserDep, service: ServiceDep
) -> BadgeResponse:
    """Mi badge, si ya aprobé la evaluación final."""
    return BadgeResponse.model_validate(await service.get_badge(user.id, enrollment_id))


routers: list[APIRouter] = [router]
