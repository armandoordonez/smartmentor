"""Rutas `/me` del aprendiz: inscripciones, diagnóstico, objetivo, ruta, quiz, final, badge,
encuesta y eventos (docs/contracts/api-v2.md, sección 4)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import require_roles
from app.auth.policies import LEARNER
from app.common.entities import require_id
from app.common.schemas import Page
from app.core.idempotency import IdempotencyDep
from app.domains.ai_gateway.entities import JobRef
from app.domains.ai_gateway.schemas import JobAccepted
from app.domains.assessments import badges
from app.domains.assessments.dependencies import (
    AttemptServiceDep,
    BadgeServiceDep,
    DiagnosticServiceDep,
)
from app.domains.assessments.entities import AssessmentItem, AttemptAnswer
from app.domains.assessments.service import (
    AttemptHistoryEntry,
    AttemptOutcome,
    AttemptResultView,
    AttemptView,
    BadgeView,
    LearnerAnswerInput,
)
from app.domains.identity.authentication import CurrentUser
from app.domains.learner.dependencies import (
    EventServiceDep,
    StudyGoalServiceDep,
    SurveyServiceDep,
)
from app.domains.learner.entities import InteractionEvent, StudyGoals
from app.domains.learner.schemas import (
    AnswersBody,
    AttemptCounters,
    AttemptCreate,
    AttemptHistoryItem,
    AttemptResponse,
    AttemptResultResponse,
    BadgeSummary,
    DiagnosticResponse,
    DiagnosticResultResponse,
    EventsAccepted,
    EventsBody,
    GradedAnswer,
    ItemForLearner,
    LearnerAnswerResponse,
    LearningOutcomeBrief,
    ProposedObjective,
    QuizRules,
    ReviewPlanResponse,
    ReviewRequestBody,
    ReviewRequestResponse,
    SavedResponse,
    StepContentResponse,
    StepTopic,
    StudyGoalsBody,
    StudyGoalsResponse,
    SurveyBody,
    SurveyResponseBody,
    TopicLevelResponse,
    WeakTopicResponse,
)
from app.domains.learning_paths.controller import enrollment_response, objective_of, step_response
from app.domains.learning_paths.dependencies import EnrollmentServiceDep
from app.domains.learning_paths.schemas import (
    EnrollmentCreate,
    EnrollmentResponse,
    FinalLockResponse,
    NextActionResponse,
    ObjectiveUpdate,
    PathResponse,
    SavingsResponse,
)
from app.domains.learning_paths.service import EnrollmentView

router = APIRouter(prefix="/me", tags=["learner"])

LearnerUser = Annotated[CurrentUser, Depends(require_roles(*LEARNER))]
ITEMS_PER_ATTEMPT = 5


def _enrollment(view: EnrollmentView) -> EnrollmentResponse:
    return EnrollmentResponse.model_validate(enrollment_response(view))


def _accepted(job: JobRef) -> JobAccepted:
    return JobAccepted.for_job(job.job_id)


def _location(result: BaseModel) -> str | None:
    return result.poll_url if isinstance(result, JobAccepted) else None


def _answers(body: AnswersBody) -> list[LearnerAnswerInput]:
    return [
        LearnerAnswerInput(
            item_id=a.item_id,
            selected_option=a.selected_option,
            dont_know=a.dont_know,
            text_answer=a.text_answer,
        )
        for a in body.answers
    ]


def _rubric_summary(item: AssessmentItem) -> str | None:
    """Rúbrica visible de una respuesta corta («Cómo se califica», E6c), sin la respuesta modelo."""
    if item.item_type != "short_answer" or not item.rubric:
        return None
    return " · ".join(
        f"{c.get('criterion', '')} ({round(float(c.get('points', 0)) * 100)} %)"
        for c in item.rubric
    )


def _item(item: AssessmentItem, names: dict[int, str] | None = None) -> ItemForLearner:
    return ItemForLearner(
        item_id=require_id(item),
        topic_id=item.topic_id,
        stem=item.stem,
        item_type=item.item_type,
        options=[str(o) for o in item.options or []],
        topic_name=(names or {}).get(item.topic_id),
        bloom_level=item.bloom_level,
        rubric_summary=_rubric_summary(item),
    )


def _answer(answer: AttemptAnswer) -> LearnerAnswerResponse:
    return LearnerAnswerResponse(
        item_id=answer.assessment_item_id,
        selected_option=answer.selected_index,
        dont_know=answer.dont_know,
        text_answer=answer.text_answer,
    )


def _attempt(view: AttemptView, names: dict[int, str] | None = None) -> AttemptResponse:
    attempt = view.attempt
    return AttemptResponse(
        id=require_id(attempt),
        assessment_type=attempt.assessment_type,
        status=attempt.status,
        step_id=attempt.path_step_id,
        attempt_number=attempt.attempt_number,
        items=[_item(i, names) for i in view.items],
        answers=[_answer(a) for a in view.answers],
        uses_extra_grant=attempt.uses_extra_grant,
        created_at=attempt.created_at,
    )


def _result(view: AttemptResultView) -> AttemptResultResponse:
    attempt, action = view.attempt, view.next_action
    return AttemptResultResponse(
        attempt_id=require_id(attempt),
        assessment_type=attempt.assessment_type,
        status=attempt.status,
        score=attempt.score,
        passed=attempt.passed,
        pass_threshold=view.pass_threshold,
        answers=[
            GradedAnswer(
                attempt_answer_id=require_id(answer),
                item_id=answer.assessment_item_id,
                grading=answer.rubric_detail,
                review_requested=answer.review_requested_at is not None,
            )
            for answer, _item_ in view.answers
        ],
        remedial_resource_id=view.remedial_resource_id,
        attempts=AttemptCounters(
            used=view.attempts_used,
            max=view.attempts_max,
            remaining=max(view.attempts_max - view.attempts_used, 0),
        ),
        next_action=NextActionResponse(
            type=action.type,
            step_id=action.step_id,
            attempt_id=action.attempt_id,
            job_id=action.job_id,
            screen=action.screen,
        ),
    )


def _outcome(outcome: AttemptOutcome, names: dict[int, str] | None = None) -> BaseModel:
    if outcome.job is not None:
        return _accepted(outcome.job)
    if outcome.result is not None:
        return _result(outcome.result)
    assert outcome.view is not None  # noqa: S101
    return _attempt(outcome.view, names)


def _status_created(result: BaseModel) -> int:
    return 202 if isinstance(result, JobAccepted) else 201


def _status_graded(result: BaseModel) -> int:
    return 202 if isinstance(result, JobAccepted) else 200


def _badge(view: BadgeView) -> BadgeSummary:
    badge = view.badge
    public_id = str(badge.public_id)
    return BadgeSummary(
        public_id=public_id,
        enrollment_id=badge.enrollment_id,
        name=view.course.name,
        course_name=view.course.name,
        learning_path_name=view.path.name,
        issued_at=badge.issued_at,
        assertion_url=badges.ASSERTION_PATH.format(public_id=public_id),
        image_url=badges.IMAGE_PATH.format(public_id=public_id),
    )


# --- inscripciones -----------------------------------------------------------------------------


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201)
async def enroll(
    payload: EnrollmentCreate, user: LearnerUser, service: EnrollmentServiceDep
) -> EnrollmentResponse:
    """Inscribe al aprendiz en una ruta publicada (`403 CONSENT_REQUIRED` sin consentimiento)."""
    return _enrollment(await service.enroll(user.id, payload.learning_path_id))


@router.get("/enrollments", response_model=Page[EnrollmentResponse])
async def list_enrollments(
    user: LearnerUser, service: EnrollmentServiceDep, limit: int = 20, offset: int = 0
) -> Page[EnrollmentResponse]:
    limit, offset = min(max(limit, 1), 100), max(offset, 0)
    views, total = await service.list_own(user, limit=limit, offset=offset)
    return Page[EnrollmentResponse](
        items=[_enrollment(v) for v in views], total=total, limit=limit, offset=offset
    )


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: int, user: LearnerUser, service: EnrollmentServiceDep
) -> EnrollmentResponse:
    """La inscripción con su `next_action` (la app navega con ella; nunca deduce el estado)."""
    return _enrollment(await service.view(user, enrollment_id))


# --- diagnóstico y objetivo --------------------------------------------------------------------


@router.post(
    "/enrollments/{enrollment_id}/diagnostic", response_model=DiagnosticResponse, status_code=201
)
async def start_diagnostic(
    enrollment_id: int, user: LearnerUser, service: DiagnosticServiceDep
) -> DiagnosticResponse:
    """Arma el diagnóstico desde el banco aprobado (sin LLM)."""
    view = await service.start(user, enrollment_id)
    names = await service.topic_names(enrollment_id)
    return DiagnosticResponse(
        id=require_id(view.diagnostic),
        status=view.diagnostic.status,
        items=[_item(i, names) for i in view.items],
        answers=[],
        submitted_at=None,
    )


@router.get("/enrollments/{enrollment_id}/diagnostic", response_model=DiagnosticResponse)
async def get_diagnostic(
    enrollment_id: int, user: LearnerUser, service: DiagnosticServiceDep
) -> DiagnosticResponse:
    view = await service.get(user, enrollment_id)
    stored: dict[str, Any] = view.diagnostic.answers or {}
    names = await service.topic_names(enrollment_id)
    return DiagnosticResponse(
        id=require_id(view.diagnostic),
        status=view.diagnostic.status,
        items=[_item(i, names) for i in view.items],
        answers=[
            LearnerAnswerResponse(
                item_id=int(item_id),
                selected_option=value.get("selected_option"),
                dont_know=bool(value.get("dont_know", False)),
                text_answer=value.get("text_answer"),
            )
            for item_id, value in stored.items()
        ],
        submitted_at=view.diagnostic.submitted_at,
    )


@router.put("/enrollments/{enrollment_id}/diagnostic/answers", response_model=SavedResponse)
async def save_diagnostic_answers(
    enrollment_id: int, payload: AnswersBody, user: LearnerUser, service: DiagnosticServiceDep
) -> SavedResponse:
    """Guardado parcial (reemplaza por `item_id`)."""
    return SavedResponse(saved=await service.save_answers(user, enrollment_id, _answers(payload)))


@router.post(
    "/enrollments/{enrollment_id}/diagnostic/submit", response_model=JobAccepted, status_code=202
)
async def submit_diagnostic(
    enrollment_id: int,
    request: Request,
    user: LearnerUser,
    service: DiagnosticServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Entrega el diagnóstico: `202` con el trabajo `diagnostic.finalize` (U1a)."""

    async def action() -> BaseModel:
        return _accepted(await service.submit(user, enrollment_id))

    return await idempotency.run(
        user_id=user.id, request=request, body=b"", action=action, location=_location
    )


@router.get(
    "/enrollments/{enrollment_id}/diagnostic/result", response_model=DiagnosticResultResponse
)
async def diagnostic_result(
    enrollment_id: int, user: LearnerUser, service: DiagnosticServiceDep
) -> DiagnosticResultResponse:
    """Niveles por tema, clasificación y objetivo propuesto (E4)."""
    view = await service.result(user, enrollment_id)
    data = view.diagnostic.level_by_topic or {}
    objective = objective_of(view.enrollment)
    return DiagnosticResultResponse(
        status=view.diagnostic.status,
        level_by_topic=[
            TopicLevelResponse(
                topic_id=int(t["topic_id"]),
                name=view.topic_names.get(int(t["topic_id"]), ""),
                test_score=t.get("test_score"),
                profile_prior=t.get("profile_prior"),
                resume_prior=t.get("resume_prior"),
                weights=t.get("weights", {}),
                level=t["level"],
                classification=t["classification"],
            )
            for t in data.get("level_by_topic", [])
            if str(t.get("topic_id", "")).isdigit()
        ],
        overall_score=float(data.get("overall_score", 0)),
        proposed_objective=(
            ProposedObjective(**objective.model_dump()) if objective is not None else None
        ),
    )


@router.put("/enrollments/{enrollment_id}/objective", response_model=EnrollmentResponse)
async def confirm_objective(
    enrollment_id: int,
    payload: ObjectiveUpdate,
    user: LearnerUser,
    service: DiagnosticServiceDep,
    enrollments: EnrollmentServiceDep,
) -> EnrollmentResponse:
    """Objetivo en tres partes (E4, E4b): `path.sequence` (síncrono) crea los pasos."""
    await service.confirm_objective(user, enrollment_id, payload.model_dump())
    return _enrollment(await enrollments.view(user, enrollment_id))


# --- ruta y pasos ------------------------------------------------------------------------------


@router.get("/enrollments/{enrollment_id}/path", response_model=PathResponse)
async def get_path(
    enrollment_id: int,
    user: LearnerUser,
    service: EnrollmentServiceDep,
    attempts: AttemptServiceDep,
) -> PathResponse:
    """Pasos con estado y motivo, ahorro por temas omitidos y estado de la final (E5, E5b)."""
    used, maximum = await attempts.final_counters(user, enrollment_id)
    view = await service.path_view(user, enrollment_id, used, maximum)
    skipped, minutes = view.savings
    return PathResponse(
        enrollment_id=enrollment_id,
        steps=[step_response(s, view.path) for s in view.steps],
        savings=SavingsResponse(skipped_topics=skipped, skipped_minutes=minutes),
        final=FinalLockResponse(
            locked=view.final_locked or view.enrollment.status != "final_ready",
            attempts_used=used,
            max_attempts=maximum,
            pass_threshold=view.path.final_pass_threshold,
        ),
    )


@router.get(
    "/enrollments/{enrollment_id}/steps/{step_id}/content", response_model=StepContentResponse
)
async def step_content(
    enrollment_id: int, step_id: int, user: LearnerUser, service: AttemptServiceDep
) -> StepContentResponse:
    """Explicación aprobada, video en uso (o respaldo), reglas del quiz e intentos (E6)."""
    view = await service.step_content(user, enrollment_id, step_id)
    step = view.step
    maximum = view.max_attempts + step.extra_attempts_granted
    return StepContentResponse(
        step_id=require_id(step),
        status=step.status,
        topic=StepTopic(
            id=view.topic.id,
            name=view.topic.name,
            learning_outcomes=[LearningOutcomeBrief(**o) for o in view.outcomes],
        ),
        explanation=view.explanation,
        personal_example=view.personal_example,
        video=view.video,
        quiz_rules=QuizRules(
            pass_threshold=view.pass_threshold,
            items_per_attempt=ITEMS_PER_ATTEMPT,
            short_answer_min_criteria_ratio=view.short_answer_ratio,
        ),
        attempts={
            "used": step.attempts_used,
            "max": view.max_attempts,
            "extra_granted": step.extra_attempts_granted,
            "remaining": max(maximum - step.attempts_used, 0),
        },
    )


@router.post(
    "/enrollments/{enrollment_id}/steps/{step_id}/attempts",
    response_model=AttemptResponse,
    status_code=201,
    responses={202: {"model": JobAccepted, "description": "Hay que generar más preguntas (U1b)"}},
)
async def start_attempt(
    enrollment_id: int,
    step_id: int,
    payload: AttemptCreate,
    request: Request,
    user: LearnerUser,
    service: AttemptServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Intento del quiz con ítems no vistos; `202` solo si hay que generar más."""

    async def action() -> BaseModel:
        return _outcome(
            await service.start_topic(user, enrollment_id, step_id, payload.assessment_type),
            await service.topic_names(enrollment_id),
        )

    return await idempotency.run(
        user_id=user.id,
        request=request,
        body=payload,
        action=action,
        location=_location,
        status_of=_status_created,
    )


# --- intentos ----------------------------------------------------------------------------------


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(
    attempt_id: int, user: LearnerUser, service: AttemptServiceDep
) -> AttemptResponse:
    """Ítems (sin solución) y respuestas guardadas."""
    view = await service.get(user, attempt_id)
    return _attempt(view, await service.topic_names(view.attempt.enrollment_id))


@router.put("/attempts/{attempt_id}/answers", response_model=SavedResponse)
async def save_attempt_answers(
    attempt_id: int, payload: AnswersBody, user: LearnerUser, service: AttemptServiceDep
) -> SavedResponse:
    return SavedResponse(saved=await service.save_answers(user, attempt_id, _answers(payload)))


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=AttemptResultResponse,
    responses={202: {"model": JobAccepted, "description": "Calificando respuestas cortas"}},
)
async def submit_attempt(
    attempt_id: int,
    request: Request,
    user: LearnerUser,
    service: AttemptServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Opción múltiple por regla (`200`); con respuesta corta, `202` y `grading.short_answer`."""

    async def action() -> BaseModel:
        return _outcome(await service.submit(user, attempt_id))

    return await idempotency.run(
        user_id=user.id,
        request=request,
        body=b"",
        action=action,
        location=_location,
        status_of=_status_graded,
    )


@router.get("/attempts/{attempt_id}/result", response_model=AttemptResultResponse)
async def attempt_result(
    attempt_id: int, user: LearnerUser, service: AttemptServiceDep
) -> AttemptResultResponse:
    """Resultado, rúbrica, explicación alterna (si existe) y siguiente acción (E7, E9)."""
    return _result(await service.result(user, attempt_id))


@router.post(
    "/attempt-answers/{answer_id}/review-request",
    response_model=ReviewRequestResponse,
    status_code=201,
)
async def request_review(
    answer_id: int,
    payload: ReviewRequestBody,  # noqa: ARG001  (el comentario no tiene columna en v2.0.0)
    user: LearnerUser,
    service: AttemptServiceDep,
) -> ReviewRequestResponse:
    """Pide la revisión humana de una respuesta corta (crea una alerta para el instructor)."""
    return ReviewRequestResponse(alert_id=await service.request_review(user, answer_id))


@router.post(
    "/enrollments/{enrollment_id}/final-attempts",
    response_model=AttemptResponse,
    status_code=201,
    responses={
        202: {"model": JobAccepted, "description": "Hay que generar más preguntas (U1d, B-011)"}
    },
)
async def start_final_attempt(
    enrollment_id: int,
    request: Request,
    user: LearnerUser,
    service: AttemptServiceDep,
    idempotency: IdempotencyDep,
) -> JSONResponse:
    """Intento de la final: solo con todos los pasos `passed` o `skipped` (E8).

    `202` si un reintento no tiene suficientes preguntas no vistas: se generan más bajo demanda.
    """

    async def action() -> BaseModel:
        return _outcome(
            await service.start_final(user, enrollment_id),
            await service.topic_names(enrollment_id),
        )

    return await idempotency.run(
        user_id=user.id,
        request=request,
        body=b"",
        action=action,
        location=_location,
        status_of=_status_created,
    )


@router.get("/enrollments/{enrollment_id}/review-plan", response_model=ReviewPlanResponse)
async def review_plan(
    enrollment_id: int, user: LearnerUser, service: AttemptServiceDep
) -> ReviewPlanResponse:
    """Temas débiles del último intento final (E9)."""
    weak = await service.review_plan(user, enrollment_id)
    return ReviewPlanResponse(
        weak_topics=[
            WeakTopicResponse(
                topic_id=w.topic_id, name=w.name, score=w.score, resource_id=w.resource_id
            )
            for w in weak
        ]
    )


# --- badges, encuesta y eventos ----------------------------------------------------------------


@router.get("/badges", response_model=list[BadgeSummary])
async def my_badges(user: LearnerUser, service: BadgeServiceDep) -> list[BadgeSummary]:
    return [_badge(v) for v in await service.mine(user)]


@router.get("/enrollments/{enrollment_id}/badge", response_model=BadgeSummary)
async def enrollment_badge(
    enrollment_id: int, user: LearnerUser, service: BadgeServiceDep
) -> BadgeSummary:
    return _badge(await service.for_enrollment(user, enrollment_id))


@router.post(
    "/enrollments/{enrollment_id}/surveys/final",
    response_model=SurveyResponseBody,
    status_code=201,
)
async def final_survey(
    enrollment_id: int, payload: SurveyBody, user: LearnerUser, service: SurveyServiceDep
) -> SurveyResponseBody:
    """Encuesta final y SUS (E13a, E13b): calcula `sus_score`."""
    created = await service.submit_final(
        user,
        enrollment_id,
        likert=payload.likert,
        sus_items=payload.sus_items,
        comment=payload.comment,
    )
    return SurveyResponseBody(id=require_id(created), sus_score=created.sus_score or 0.0)


@router.post("/events", response_model=EventsAccepted, status_code=202)
async def record_events(
    payload: EventsBody, user: LearnerUser, service: EventServiceDep
) -> EventsAccepted:
    """Lote de eventos para el tiempo en tarea (hasta 100)."""
    events = [
        InteractionEvent(
            enrollment_id=e.enrollment_id,
            event_type=e.event_type,
            topic_id=e.topic_id,
            occurred_at=e.occurred_at,
            payload=e.payload,
        )
        for e in payload.events
    ]
    return EventsAccepted(accepted=await service.record(user, events))


# --- historial de intentos y metas personales (rutas que pidió la app, F07b) --------------------


def _history(entries: list[AttemptHistoryEntry]) -> list[AttemptHistoryItem]:
    return [
        AttemptHistoryItem(
            attempt_id=e.attempt_id,
            number=e.number,
            score=e.score,
            correct=e.correct,
            total=e.total,
            extra_grant=e.extra_grant,
            passed=e.passed,
        )
        for e in entries
    ]


@router.get(
    "/enrollments/{enrollment_id}/steps/{step_id}/attempts",
    response_model=list[AttemptHistoryItem],
)
async def step_attempt_history(
    enrollment_id: int, step_id: int, user: LearnerUser, service: AttemptServiceDep
) -> list[AttemptHistoryItem]:
    """Intentos calificados del tema (E7c): número, puntaje, aciertos y si fue extra."""
    return _history(await service.history(user, enrollment_id, step_id))


@router.get("/enrollments/{enrollment_id}/final/attempts", response_model=list[AttemptHistoryItem])
async def final_attempt_history(
    enrollment_id: int, user: LearnerUser, service: AttemptServiceDep
) -> list[AttemptHistoryItem]:
    """Intentos calificados de la evaluación final (E9, E9c)."""
    return _history(await service.history(user, enrollment_id, None))


def _goals(goals: StudyGoals) -> StudyGoalsResponse:
    return StudyGoalsResponse(
        daily_minutes_goal=goals.daily_minutes_goal,
        daily_minutes_done=goals.daily_minutes_done,
        monthly_topics_goal=goals.monthly_topics_goal,
        monthly_topics_done=goals.monthly_topics_done,
        streak_days=goals.streak_days,
    )


@router.get("/study-goals", response_model=StudyGoalsResponse)
async def get_study_goals(user: LearnerUser, service: StudyGoalServiceDep) -> StudyGoalsResponse:
    """Metas personales y avance de hoy y del mes (E11, P2). `404` si aún no hay metas."""
    return _goals(await service.get(user))


@router.put("/study-goals", response_model=StudyGoalsResponse)
async def put_study_goals(
    payload: StudyGoalsBody, user: LearnerUser, service: StudyGoalServiceDep
) -> StudyGoalsResponse:
    """Define o cambia las metas (minutos al día y temas al mes)."""
    return _goals(await service.save(user, payload.daily_minutes_goal, payload.monthly_topics_goal))


routers: list[APIRouter] = [router]
