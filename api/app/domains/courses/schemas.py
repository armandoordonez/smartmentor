"""Contratos HTTP de cursos (docs/contracts/api-v2.md, sección 5)."""

from pydantic import BaseModel, ConfigDict, Field

from app.common.constants import BloomLevel, MaterialOrigin
from app.common.schemas import RequestSchema, UtcDatetime


class LearningPathInput(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    group_label: str | None = Field(default=None, max_length=100)


class CourseCreate(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    learning_path: LearningPathInput | None = None


class CourseUpdate(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class CourseOwnerUpdate(RequestSchema):
    owner_user_id: int | None = Field(default=None, gt=0)


class LearningPathSummary(BaseModel):
    id: int
    name: str
    group_label: str | None
    status: str


class SyllabusSummary(BaseModel):
    """Syllabus vigente (el más reciente) del curso; sin el texto extraído."""

    filename: str | None = Field(
        description="Nombre original del archivo, sin ruta; `null` si se pegó texto"
    )
    pages: int | None = Field(description="Páginas del PDF; `null` si no aplica")
    characters: int | None = Field(description="Caracteres de texto extraídos")


class CourseResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    owner_user_id: int | None
    extraction_error_code: str | None
    extraction_job_id: str | None
    learning_path: LearningPathSummary | None
    topics_count: int = Field(description="Temas activos del curso")
    enrolled_count: int = Field(description="Aprendices inscritos, sin los retirados")
    syllabus: SyllabusSummary | None = Field(
        default=None,
        description="Syllabus vigente. Solo en `GET /courses/{id}`; `null` en la lista "
        "y si el curso no tiene syllabus",
    )
    created_at: UtcDatetime | None
    updated_at: UtcDatetime | None


class SyllabusTextBody(RequestSchema):
    text: str = Field(min_length=1)


class MaterialResponse(BaseModel):
    """Apunte o lectura del curso (R-004). El texto extraído no viaja: solo su tamaño."""

    id: int
    course_id: int
    file_name: str | None
    source_type: str = Field(description="pdf o text (los TXT y MD son texto)")
    origin: MaterialOrigin
    byte_size: int | None
    page_count: int | None
    extracted_char_count: int | None = Field(description="Caracteres de texto extraídos")
    active: bool = Field(description="`false`: desactivado, ya no alimenta el RAG (R-010)")
    created_at: UtcDatetime | None


class ExtractionRequest(RequestSchema):
    confirm_discard_review: bool = False


class OutcomeWrite(RequestSchema):
    id: int | None = Field(default=None, gt=0)
    statement: str = Field(min_length=1, max_length=1000)
    bloom_level: BloomLevel


class TopicWrite(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    subtopics: list[str] = Field(default_factory=list, max_length=50)
    position: int | None = Field(default=None, ge=1)
    estimated_minutes: int | None = Field(default=None, ge=1, le=100_000)
    is_mandatory: bool = False
    bloom_level: BloomLevel | None = None
    learning_outcomes: list[OutcomeWrite] = Field(default_factory=list, max_length=30)
    prerequisite_topic_ids: list[int] = Field(default_factory=list, max_length=50)


class OutcomeResponse(BaseModel):
    id: int
    code: str
    statement: str
    bloom_level: str


class TopicResponse(BaseModel):
    id: int
    course_id: int
    name: str
    description: str | None
    subtopics: list[str]
    position: int
    estimated_minutes: int | None
    is_mandatory: bool
    bloom_level: str | None
    origin: str
    review_status: str
    extraction_key: str | None
    learning_outcomes: list[OutcomeResponse]
    prerequisite_topic_ids: list[int]


class ReviewCounts(BaseModel):
    unchanged: int
    corrected: int
    added: int
    deleted: int


class TopicListResponse(BaseModel):
    topics: list[TopicResponse]
    review_counts: ReviewCounts


class GraphNode(BaseModel):
    id: int
    name: str
    position: int


class GraphEdge(BaseModel):
    """`from` es el prerrequisito y `to` el tema que lo requiere."""

    model_config = ConfigDict(populate_by_name=True)

    from_: int = Field(alias="from")
    to: int
    origin: str


class TopicGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ScoreResponse(BaseModel):
    precision: float | None
    recall: float | None
    f1: float | None


class ExtractionMetricsResponse(BaseModel):
    topics: ScoreResponse | None
    prerequisites: ScoreResponse | None
    corrections: int
