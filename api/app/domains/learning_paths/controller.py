"""Endpoints de rutas: catálogo, ajustes, tablero, detalle, intentos extra, alertas y AD5."""

from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN, ANY_ROLE, STAFF
from app.common.entities import require_id
from app.common.schemas import Page
from app.domains.identity.authentication import CurrentUser
from app.domains.learning_paths.dependencies import EnrollmentServiceDep, PathStaffServiceDep
from app.domains.learning_paths.entities import Alert, AttemptGrant, Enrollment, LearningPath
from app.domains.learning_paths.schemas import (
    AdminEnrollmentCreate,
    AdminEnrollmentResponse,
    AlertResponse,
    AttemptGrantCreate,
    AttemptGrantResponse,
    AttemptSummaryResponse,
    CourseSummary,
    CriticalTopic,
    DashboardKpi,
    DashboardLearner,
    DashboardPath,
    DashboardResponse,
    LearnerDetailResponse,
    LearningPathCard,
    MasteryCell,
    MasteryRow,
    MoveRequest,
    NextActionResponse,
    ObjectiveResponse,
    PathRef,
    PathSettingsResponse,
    PathSettingsUpdate,
    ProgressResponse,
    StepResponse,
    TopicSummary,
    WithdrawRequest,
)
from app.domains.learning_paths.service import EnrollmentService, EnrollmentView, StepView
from app.domains.learning_paths.states import DONE_STEPS, StepStatus

router = APIRouter(tags=["learning-paths"])
admin_router = APIRouter(tags=["enrollments-admin"], dependencies=[Depends(require_roles(*ADMIN))])

AnyUser = Annotated[CurrentUser, Depends(require_roles(*ANY_ROLE))]
StaffUser = Annotated[CurrentUser, Depends(require_roles(*STAFF))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


# --- conversiones compartidas con el controlador del aprendiz ---------------------------------


def objective_of(enrollment: Enrollment) -> ObjectiveResponse | None:
    verb, content, criterion = (
        enrollment.objective_bloom_verb,
        enrollment.objective_content,
        enrollment.objective_criterion,
    )
    if not (verb and content and criterion):
        return None
    return ObjectiveResponse(
        statement=f"{verb} {content} {criterion}",
        bloom_verb=verb,
        content=content,
        criterion=criterion,
        origin=enrollment.objective_origin,
    )


def enrollment_response(view: EnrollmentView) -> dict[str, object]:
    done, total, percent = view.progress
    enrollment, path, action = view.enrollment, view.path, view.next_action
    return {
        "id": require_id(enrollment),
        "learning_path": PathRef(id=require_id(path), name=path.name, group_label=path.group_label),
        "status": enrollment.status,
        "objective": objective_of(enrollment),
        "progress": ProgressResponse(steps_total=total, steps_done=done, percent=percent),
        "pilot_arm": enrollment.pilot_arm,
        "analysis_included": enrollment.analysis_included,
        "next_action": NextActionResponse(
            type=action.type,
            step_id=action.step_id,
            attempt_id=action.attempt_id,
            job_id=action.job_id,
            screen=action.screen,
        ),
        "created_at": enrollment.created_at,
        "completed_at": enrollment.completed_at,
    }


def step_response(view: StepView, path: LearningPath) -> StepResponse:
    step, topic = view.step, view.topic
    return StepResponse(
        step_id=require_id(step),
        step_order=step.step_order,
        topic_id=step.topic_id,
        name=topic.name if topic is not None else "",
        status=step.status,
        inclusion_reason=step.inclusion_reason,
        diagnostic_level=step.diagnostic_level,
        estimated_minutes=topic.estimated_minutes if topic is not None else None,
        attempts_used=step.attempts_used,
        max_attempts=path.max_attempts,
        extra_attempts_granted=step.extra_attempts_granted,
        best_score=step.best_score,
        last_score=step.last_score,
    )


def _settings(path: LearningPath) -> PathSettingsResponse:
    return PathSettingsResponse(
        learning_path_id=require_id(path),
        topic_pass_threshold=path.topic_pass_threshold,
        final_pass_threshold=path.final_pass_threshold,
        mastery_skip_threshold=path.mastery_skip_threshold,
        max_attempts=path.max_attempts,
        short_answer_min_ratio=path.short_answer_min_ratio,
        level_weights=path.weights,
        default_objective={
            "bloom_verb": path.default_objective_bloom_verb,
            "content": path.default_objective_content,
            "criterion": path.default_objective_criterion,
        },
    )


def _grant(grant: AttemptGrant) -> AttemptGrantResponse:
    return AttemptGrantResponse(
        id=require_id(grant),
        path_step_id=grant.path_step_id,
        enrollment_id=grant.enrollment_id,
        attempts=grant.attempts,
        note=grant.note,
        granted_by_user_id=grant.granted_by_user_id,
        created_at=grant.created_at,
    )


def _alert(alert: Alert) -> AlertResponse:
    return AlertResponse.model_validate(
        {
            "id": require_id(alert),
            "alert_type": alert.alert_type,
            "enrollment_id": alert.enrollment_id,
            "path_step_id": alert.path_step_id,
            "read_at": alert.read_at,
            "created_at": alert.created_at,
        }
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


# --- catálogo ----------------------------------------------------------------------------------


@router.get("/learning-paths", response_model=Page[LearningPathCard])
async def list_learning_paths(
    user: AnyUser, service: EnrollmentServiceDep, limit: Limit = 20, offset: Offset = 0
) -> Page[LearningPathCard]:
    """Catálogo (E1): solo rutas publicadas, con sus temas y minutos estimados."""
    cards, total = await service.catalog(user.id, limit=limit, offset=offset)
    return Page[LearningPathCard](
        items=[
            LearningPathCard(
                id=require_id(c.path),
                name=c.path.name,
                group_label=c.path.group_label,
                course=CourseSummary(
                    id=require_id(c.course), name=c.course.name, description=c.course.description
                ),
                topics=[
                    TopicSummary(
                        id=t.id,
                        name=t.name,
                        estimated_minutes=t.estimated_minutes,
                        is_mandatory=t.is_mandatory,
                    )
                    for t in c.topics
                ],
                topic_count=len(c.topics),
                estimated_minutes=sum(t.estimated_minutes or 0 for t in c.topics),
                enrolled=c.enrolled,
            )
            for c in cards
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# --- instructor --------------------------------------------------------------------------------


@router.patch("/learning-paths/{learning_path_id}/settings", response_model=PathSettingsResponse)
async def update_settings(
    learning_path_id: int,
    payload: PathSettingsUpdate,
    user: StaffUser,
    service: PathStaffServiceDep,
) -> PathSettingsResponse:
    """Umbrales y objetivo por defecto (D3b). `409 PILOT_RUNNING` sin `confirm_pilot_change`."""
    changes = payload.model_dump(
        exclude_none=True, exclude={"confirm_pilot_change", "default_objective"}
    )
    if payload.default_objective is not None:
        objective = payload.default_objective
        changes |= {
            "default_objective_bloom_verb": objective.bloom_verb,
            "default_objective_content": objective.content,
            "default_objective_criterion": objective.criterion,
        }
    path = await service.update_settings(
        user, learning_path_id, changes, confirm_pilot=payload.confirm_pilot_change
    )
    return _settings(path)


@router.get("/learning-paths/{learning_path_id}/dashboard", response_model=DashboardResponse)
async def dashboard(
    learning_path_id: int, user: StaffUser, service: PathStaffServiceDep
) -> DashboardResponse:
    """Tablero de la ruta (D3): KPI, aprendices, matriz de dominio y temas críticos."""
    data = await service.dashboard(user, learning_path_id)
    learners: list[DashboardLearner] = []
    matrix: list[MasteryRow] = []
    by_topic: dict[int, list[tuple[str, int]]] = defaultdict(list)
    progress_values: list[int] = []
    for row in data.rows:
        enrollment = row.enrollment
        done = sum(1 for s in row.steps if s.status in DONE_STEPS)
        total = len(row.steps)
        percent = round(100 * done / total) if total else 0
        progress_values.append(percent)
        learners.append(
            DashboardLearner(
                enrollment_id=require_id(enrollment),
                user_id=enrollment.user_id,
                full_name=row.full_name,
                status=enrollment.status,
                progress_percent=percent,
                steps_done=done,
                steps_total=total,
                analysis_included=enrollment.analysis_included,
                pilot_arm=enrollment.pilot_arm,
            )
        )
        matrix.append(
            MasteryRow(
                enrollment_id=require_id(enrollment),
                cells=[
                    MasteryCell(
                        topic_id=s.topic_id,
                        status=s.status,
                        diagnostic_level=s.diagnostic_level,
                        best_score=s.best_score,
                    )
                    for s in row.steps
                ],
            )
        )
        for step in row.steps:
            by_topic[step.topic_id].append((step.status, step.attempts_used))
    statuses = [r.enrollment.status for r in data.rows]
    attempted = [s for steps in by_topic.values() for s in steps if s[1] >= 1]
    first_pass = sum(1 for status, used in attempted if status == StepStatus.PASSED and used == 1)
    critical: list[CriticalTopic] = []
    for topic in data.topics:
        steps = by_topic.get(topic.id, [])
        tried = [s for s in steps if s[1] >= 1]
        exhausted = sum(1 for status, _ in steps if status == StepStatus.ATTEMPTS_EXHAUSTED)
        critical.append(
            CriticalTopic(
                topic_id=topic.id,
                name=topic.name,
                attempts_exhausted=exhausted,
                average_attempts=round(sum(u for _, u in tried) / len(tried), 2) if tried else None,
                first_attempt_pass_rate=_rate(
                    sum(1 for status, used in tried if status == StepStatus.PASSED and used == 1),
                    len(tried),
                ),
            )
        )
    stats = list(critical)
    critical.sort(key=lambda c: (-c.attempts_exhausted, -(c.average_attempts or 0)))
    counted = [s for s in statuses if s != "withdrawn"]
    path = data.path
    return DashboardResponse(
        learning_path_id=learning_path_id,
        course_id=path.course_id,
        learning_path=DashboardPath(
            id=require_id(path), name=path.name, group_label=path.group_label, status=path.status
        ),
        settings=_settings(path),
        pilot_running=data.pilot_running,
        kpi=DashboardKpi(
            learners=len(counted),
            active=sum(1 for s in counted if s not in ("completed", "abandoned")),
            completed=statuses.count("completed"),
            withdrawn=statuses.count("withdrawn"),
            completion_rate=_rate(statuses.count("completed"), len(counted)) or 0.0,
            average_progress=(
                round(sum(progress_values) / len(progress_values), 1) if progress_values else 0.0
            ),
            first_attempt_pass_rate=_rate(first_pass, len(attempted)),
            exhausted_steps=sum(c.attempts_exhausted for c in critical),
            attempts_per_topic=(
                round(sum(used for _, used in attempted) / len(attempted), 2) if attempted else None
            ),
        ),
        learners=learners,
        topics=[
            TopicSummary(
                id=t.id,
                name=t.name,
                estimated_minutes=t.estimated_minutes,
                is_mandatory=t.is_mandatory,
            )
            for t in data.topics
        ],
        mastery_matrix=matrix,
        critical_topics=[c for c in critical if c.attempts_exhausted or c.average_attempts],
        topic_stats=stats,
    )


@router.get(
    "/learning-paths/{learning_path_id}/learners/{enrollment_id}",
    response_model=LearnerDetailResponse,
)
async def learner_detail(
    learning_path_id: int, enrollment_id: int, user: StaffUser, service: PathStaffServiceDep
) -> LearnerDetailResponse:
    """Detalle del aprendiz (D4, D4b): perfil reducido, niveles, pasos e intentos."""
    detail = await service.learner_detail(user, learning_path_id, enrollment_id)
    path = detail.path
    return LearnerDetailResponse(
        enrollment_id=enrollment_id,
        learning_path=DashboardPath(
            id=require_id(path), name=path.name, group_label=path.group_label, status=path.status
        ),
        user_id=detail.enrollment.user_id,
        full_name=detail.full_name,
        profile=detail.profile,
        status=detail.enrollment.status,
        objective=objective_of(detail.enrollment),
        level_by_topic=detail.history.level_by_topic,
        steps=[step_response(s, detail.path) for s in detail.steps],
        attempts=[
            AttemptSummaryResponse(
                id=a.id,
                assessment_type=a.assessment_type,
                step_id=a.path_step_id,
                attempt_number=a.attempt_number,
                status=a.status,
                score=a.score,
                passed=a.passed,
                uses_extra_grant=a.uses_extra_grant,
                submitted_at=a.submitted_at,
            )
            for a in detail.history.attempts
        ],
        final_attempts_granted=detail.final_attempts_granted,
    )


@router.post(
    "/path-steps/{step_id}/attempt-grants", response_model=AttemptGrantResponse, status_code=201
)
async def grant_step_attempts(
    step_id: int, payload: AttemptGrantCreate, user: StaffUser, service: PathStaffServiceDep
) -> AttemptGrantResponse:
    """Intentos extra de un tema (D4c, CU-26); un paso agotado vuelve a `in_progress`."""
    return _grant(await service.grant_step_attempts(user, step_id, payload.attempts, payload.note))


@router.post(
    "/enrollments/{enrollment_id}/final-attempt-grants",
    response_model=AttemptGrantResponse,
    status_code=201,
)
async def grant_final_attempts(
    enrollment_id: int, payload: AttemptGrantCreate, user: StaffUser, service: PathStaffServiceDep
) -> AttemptGrantResponse:
    """Intentos extra de la evaluación final (D4c)."""
    return _grant(
        await service.grant_final_attempts(user, enrollment_id, payload.attempts, payload.note)
    )


@router.get("/alerts", response_model=Page[AlertResponse])
async def list_alerts(
    user: StaffUser,
    service: PathStaffServiceDep,
    unread: bool | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AlertResponse]:
    """Alertas del instructor (D3, D4): intentos agotados y revisiones pedidas."""
    items, total = await service.alerts(user, unread=unread, limit=limit, offset=offset)
    return Page[AlertResponse](
        items=[_alert(a) for a in items], total=total, limit=limit, offset=offset
    )


@router.patch("/alerts/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: int, user: StaffUser, service: PathStaffServiceDep
) -> AlertResponse:
    return _alert(await service.mark_read(user, alert_id))


# --- administración de inscripciones (AD5) -----------------------------------------------------


async def _admin(view: EnrollmentView, service: EnrollmentService) -> AdminEnrollmentResponse:
    user_id = view.enrollment.user_id
    full_name, pilot_consent = await service.learner_facts(user_id)
    return AdminEnrollmentResponse.model_validate(
        {
            **enrollment_response(view),
            "user_id": user_id,
            "full_name": full_name,
            "pilot_consent": pilot_consent,
        }
    )


@admin_router.get("/enrollments", response_model=Page[AdminEnrollmentResponse])
async def admin_list_enrollments(
    service: EnrollmentServiceDep,
    learning_path_id: int | None = None,
    status: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminEnrollmentResponse]:
    views, total = await service.admin_search(
        learning_path_id=learning_path_id, status=status, limit=limit, offset=offset
    )
    return Page[AdminEnrollmentResponse](
        items=[await _admin(v, service) for v in views],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_router.post("/enrollments", response_model=AdminEnrollmentResponse, status_code=201)
async def admin_enroll(
    payload: AdminEnrollmentCreate, service: EnrollmentServiceDep
) -> AdminEnrollmentResponse:
    """Inscribe a un aprendiz (exige su consentimiento de datos: `403 CONSENT_REQUIRED`)."""
    return await _admin(
        await service.admin_enroll(payload.user_id, payload.learning_path_id), service
    )


@admin_router.patch("/enrollments/{enrollment_id}/withdraw", response_model=AdminEnrollmentResponse)
async def withdraw_enrollment(
    enrollment_id: int,
    payload: WithdrawRequest,  # noqa: ARG001  (la nota no tiene columna en v2.0.0; ver bitácora F03b)
    service: EnrollmentServiceDep,
) -> AdminEnrollmentResponse:
    """Retira la inscripción (no se borra) y la saca del análisis."""
    return await _admin(await service.withdraw(enrollment_id), service)


@admin_router.patch("/enrollments/{enrollment_id}/move", response_model=AdminEnrollmentResponse)
async def move_enrollment(
    enrollment_id: int, payload: MoveRequest, service: EnrollmentServiceDep
) -> AdminEnrollmentResponse:
    """Mueve al aprendiz a otra ruta: la inscripción nueva queda fuera del análisis."""
    return await _admin(await service.move(enrollment_id, payload.learning_path_id), service)


routers: list[APIRouter] = [router, admin_router]
