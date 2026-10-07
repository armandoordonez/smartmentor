"""Contratos HTTP de rutas de aprendizaje."""

from pydantic import Field, field_validator

from app.common.constants import EnrollmentStatus, StepStatus
from app.common.schemas import RequestSchema, ResponseSchema
from app.domains.courses.schemas import validate_embedding


class LearningPathCreate(RequestSchema):
    course_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    default_objective: str | None = None
    topic_pass_threshold: float = Field(default=70, ge=0, le=100)
    final_pass_threshold: float = Field(default=80, ge=0, le=100)
    mastery_skip_threshold: float = Field(default=80, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=100)


class LearningPathUpdate(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    default_objective: str | None = None
    topic_pass_threshold: float | None = Field(default=None, ge=0, le=100)
    final_pass_threshold: float | None = Field(default=None, ge=0, le=100)
    mastery_skip_threshold: float | None = Field(default=None, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class LearningPathResponse(ResponseSchema):
    course_id: int
    name: str
    default_objective: str | None
    topic_pass_threshold: float
    final_pass_threshold: float
    mastery_skip_threshold: float
    max_attempts: int


class EnrollmentCreate(RequestSchema):
    user_id: int = Field(gt=0)
    learning_path_id: int = Field(gt=0)
    profile_description: str | None = None
    profile_embedding: list[float] | None = None
    personal_objective: str | None = None
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED

    _check_embedding = field_validator("profile_embedding")(validate_embedding)


class EnrollmentUpdate(RequestSchema):
    profile_description: str | None = None
    profile_embedding: list[float] | None = None
    personal_objective: str | None = None
    status: EnrollmentStatus | None = None

    _check_embedding = field_validator("profile_embedding")(validate_embedding)


class EnrollmentResponse(ResponseSchema):
    """El embedding del perfil no se devuelve: es grande y solo lo usa la capa de IA."""

    user_id: int
    learning_path_id: int
    profile_description: str | None
    personal_objective: str | None
    status: str
    has_profile_embedding: bool


class PathStepCreate(RequestSchema):
    enrollment_id: int = Field(gt=0)
    topic_id: int = Field(gt=0)
    step_order: int = Field(ge=1, le=32767)
    status: StepStatus = StepStatus.PENDING
    score: float | None = Field(default=None, ge=0, le=100)


class PathStepUpdate(RequestSchema):
    step_order: int | None = Field(default=None, ge=1, le=32767)
    status: StepStatus | None = None
    score: float | None = Field(default=None, ge=0, le=100)


class PathStepResponse(ResponseSchema):
    enrollment_id: int
    topic_id: int
    step_order: int
    status: str
    score: float | None
