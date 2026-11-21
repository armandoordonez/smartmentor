"""Modelos de los resultados que la API ingiere (espejo de `prompts/schemas/*.json`).

La imagen de la API no incluye la carpeta `prompts/`, así que la validación en tiempo de ejecución
usa estos modelos. La prueba de contrato compara cada salida de `FakeAiService` contra el JSON
Schema real y contra estos modelos, de modo que si el contrato cambia, la prueba falla.
Cada dominio que ingiere un contrato nuevo agrega aquí su modelo.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SNAKE_KEY = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
BLOOM = r"^(remember|understand|apply|analyze|evaluate|create)$"

SnakeKey = Annotated[str, StringConstraints(pattern=SNAKE_KEY)]
BloomName = Annotated[str, StringConstraints(pattern=BLOOM)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResultMeta(_Strict):
    prompt_id: str
    prompt_version: Annotated[str, StringConstraints(pattern=r"^v\d+$")]
    model: str
    generated_at: datetime
    input_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    from_cache: bool = False


class SyllabusLearningOutcome(_Strict):
    id: Annotated[str, StringConstraints(pattern=r"^lo_[a-z0-9_]+_\d+$")]
    statement: Annotated[str, StringConstraints(min_length=1)]
    bloom_level: BloomName


class SyllabusTopic(_Strict):
    id: SnakeKey
    name: Annotated[str, StringConstraints(min_length=1)]
    description: str
    subtopics: list[str]
    learning_outcomes: Annotated[list[SyllabusLearningOutcome], Field(min_length=1)]
    bloom_level: BloomName
    prerequisites: list[str]
    estimated_minutes: Annotated[int, Field(ge=1)] | None = None
    is_mandatory: bool = False


class SyllabusV1(_Strict):
    """`syllabus.v1`: resultado del trabajo `syllabus.structure`."""

    course_key: SnakeKey
    course_name: Annotated[str, StringConstraints(min_length=1)]
    default_objective: str
    topics: Annotated[list[SyllabusTopic], Field(min_length=1)]
    meta: ResultMeta


class GeneratedChildJob(BaseModel):
    job_id: str
    job_type: str
    topic_id: int | str | None = None


class CourseGenerateContentResult(BaseModel):
    """Resultado de `course.generate_content`: los trabajos hijos que orquestó."""

    jobs: list[GeneratedChildJob]
