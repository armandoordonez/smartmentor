"""Contratos HTTP de rutas e inscripciones (docs/contracts/api-v2.md, secciones 3 a 6)."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.common.schemas import RequestSchema, UtcDatetime


class NextActionResponse(BaseModel):
    type: str
    step_id: int | None = None
    attempt_id: int | None = None
    job_id: str | None = None
    screen: str


class TopicSummary(BaseModel):
    id: int
    name: str
    estimated_minutes: int | None
    is_mandatory: bool


class CourseSummary(BaseModel):
    id: int
    name: str
    description: str | None


class LearningPathCard(BaseModel):
    """Tarjeta del catálogo (E1): solo rutas publicadas."""

    id: int
    name: str
    group_label: str | None
    course: CourseSummary
    topics: list[TopicSummary]
    topic_count: int
    estimated_minutes: int
    enrolled: bool


class PathRef(BaseModel):
    id: int
    name: str
    group_label: str | None


class ObjectiveResponse(BaseModel):
    statement: str
    bloom_verb: str
    content: str
    criterion: str
    origin: str | None


class ProgressResponse(BaseModel):
    steps_total: int
    steps_done: int
    percent: int


class EnrollmentResponse(BaseModel):
    id: int
    learning_path: PathRef
    status: str
    objective: ObjectiveResponse | None
    progress: ProgressResponse
    pilot_arm: str | None
    analysis_included: bool
    next_action: NextActionResponse
    created_at: UtcDatetime
    completed_at: UtcDatetime | None


class EnrollmentCreate(RequestSchema):
    learning_path_id: Annotated[int, Field(ge=1)]


class AdminEnrollmentCreate(RequestSchema):
    user_id: Annotated[int, Field(ge=1)]
    learning_path_id: Annotated[int, Field(ge=1)]


class AdminEnrollmentResponse(EnrollmentResponse):
    user_id: int
    # Lo que AD5 muestra sin otra llamada (aditivo, 2026-11-12): el nombre del aprendiz y si tiene
    # vigente la autorización `pilot_research`.
    full_name: str
    pilot_consent: bool


class WithdrawRequest(RequestSchema):
    note: Annotated[str, Field(max_length=1000)] | None = None


class MoveRequest(RequestSchema):
    learning_path_id: Annotated[int, Field(ge=1)]


class StepResponse(BaseModel):
    step_id: int
    step_order: int
    topic_id: int
    name: str
    status: str
    inclusion_reason: str | None
    diagnostic_level: float | None
    estimated_minutes: int | None
    attempts_used: int
    max_attempts: int
    extra_attempts_granted: int
    best_score: float | None
    last_score: float | None


class SavingsResponse(BaseModel):
    skipped_topics: int
    skipped_minutes: int


class FinalLockResponse(BaseModel):
    locked: bool
    attempts_used: int
    max_attempts: int
    pass_threshold: float


class PathResponse(BaseModel):
    enrollment_id: int
    steps: list[StepResponse]
    savings: SavingsResponse
    final: FinalLockResponse


class LevelWeightsBody(RequestSchema):
    test: Annotated[float, Field(ge=0, le=1)]
    profile: Annotated[float, Field(ge=0, le=1)]
    resume: Annotated[float, Field(ge=0, le=1)]


class DefaultObjectiveBody(RequestSchema):
    bloom_verb: Annotated[str, Field(max_length=60)] | None = None
    content: str | None = None
    criterion: str | None = None


class PathSettingsUpdate(RequestSchema):
    """`PathSettings` (D3b). Todos los campos son opcionales: se cambian los que llegan."""

    topic_pass_threshold: Annotated[float, Field(ge=0, le=100)] | None = None
    final_pass_threshold: Annotated[float, Field(ge=0, le=100)] | None = None
    mastery_skip_threshold: Annotated[float, Field(ge=0, le=100)] | None = None
    max_attempts: Annotated[int, Field(ge=1, le=10)] | None = None
    short_answer_min_ratio: Annotated[float, Field(gt=0, le=1)] | None = None
    level_weights: LevelWeightsBody | None = None
    default_objective: DefaultObjectiveBody | None = None
    confirm_pilot_change: bool = False


class PathSettingsResponse(BaseModel):
    learning_path_id: int
    topic_pass_threshold: float
    final_pass_threshold: float
    mastery_skip_threshold: float
    max_attempts: int
    short_answer_min_ratio: float
    level_weights: dict[str, float]
    default_objective: dict[str, str | None]


class DashboardKpi(BaseModel):
    learners: int
    active: int
    completed: int
    withdrawn: int
    completion_rate: float
    average_progress: float
    first_attempt_pass_rate: float | None
    exhausted_steps: int
    attempts_per_topic: float | None = Field(
        default=None, description="Intentos promedio por tema entre los temas ya intentados"
    )


class DashboardLearner(BaseModel):
    enrollment_id: int
    user_id: int
    full_name: str
    status: str
    progress_percent: int
    steps_done: int
    steps_total: int
    analysis_included: bool
    pilot_arm: str | None


class MasteryCell(BaseModel):
    topic_id: int
    status: str
    diagnostic_level: float | None
    best_score: float | None


class MasteryRow(BaseModel):
    enrollment_id: int
    cells: list[MasteryCell]


class CriticalTopic(BaseModel):
    topic_id: int
    name: str
    attempts_exhausted: int
    average_attempts: float | None
    first_attempt_pass_rate: float | None


class DashboardPath(BaseModel):
    id: int
    name: str
    group_label: str | None
    status: str


class DashboardResponse(BaseModel):
    learning_path_id: int
    course_id: int
    learning_path: DashboardPath
    settings: PathSettingsResponse
    pilot_running: bool
    kpi: DashboardKpi
    learners: list[DashboardLearner]
    topics: list[TopicSummary]
    mastery_matrix: list[MasteryRow]
    critical_topics: list[CriticalTopic]
    topic_stats: list[CriticalTopic] = Field(
        description="Indicadores de todos los temas, en el orden de `topics`"
    )


class AttemptSummaryResponse(BaseModel):
    id: int
    assessment_type: str
    step_id: int | None
    attempt_number: int
    status: str
    score: float | None
    passed: bool | None
    uses_extra_grant: bool
    submitted_at: UtcDatetime | None


class LearnerDetailResponse(BaseModel):
    """Detalle del aprendiz para el instructor (D4, D4b): perfil reducido según A3c."""

    enrollment_id: int
    # Ruta del aprendiz: el encabezado de D4 la muestra sin otra llamada (aditivo, 2026-11-12).
    learning_path: DashboardPath
    user_id: int
    full_name: str
    profile: dict[str, str | None]
    status: str
    objective: ObjectiveResponse | None
    level_by_topic: list[dict[str, Any]]
    steps: list[StepResponse]
    attempts: list[AttemptSummaryResponse]
    final_attempts_granted: int


class AttemptGrantCreate(RequestSchema):
    attempts: Annotated[int, Field(ge=1, le=10)] = 1
    note: Annotated[str, Field(max_length=1000)] | None = None


class AttemptGrantResponse(BaseModel):
    id: int
    path_step_id: int | None
    enrollment_id: int | None
    attempts: int
    note: str | None
    granted_by_user_id: int
    created_at: UtcDatetime


class AlertResponse(BaseModel):
    id: int
    alert_type: Literal["topic_attempts_exhausted", "final_attempts_exhausted", "review_requested"]
    enrollment_id: int | None
    path_step_id: int | None
    read_at: UtcDatetime | None
    created_at: UtcDatetime


class ObjectiveUpdate(RequestSchema):
    """Objetivo en tres partes (E4b). Si falta una: `422 OBJECTIVE_NOT_MEASURABLE`."""

    bloom_verb: Annotated[str, Field(max_length=60)] | None = None
    content: Annotated[str, Field(max_length=2000)] | None = None
    criterion: Annotated[str, Field(max_length=2000)] | None = None
    statement: Annotated[str, Field(max_length=4000)] | None = None
