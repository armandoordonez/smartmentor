"""Ingestores de los trabajos de cursos: `syllabus.structure` y `course.generate_content`.

Cada ingestor es idempotente: mira el estado de su propia entidad (con bloqueo de fila) para saber
si ya ingirió el trabajo, de modo que dos consultas simultáneas o el barrido no duplican nada.
"""

from pydantic import BaseModel

from app.common.constants import (
    CourseStatus,
    JobType,
    LearningPathStatus,
    RoleCode,
    TopicOrigin,
    TopicReviewStatus,
)
from app.common.entities import require_id
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.contracts import CourseGenerateContentResult, SyllabusV1
from app.domains.ai_gateway.entities import JobRefs, JobStatus, PendingJob
from app.domains.ai_gateway.exceptions import AiResultInvalidError
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.courses import graph
from app.domains.courses.entities import LearningOutcome, Topic
from app.domains.courses.repository import (
    CourseRepository,
    LearningPathRepository,
    OutcomeRepository,
    PrerequisiteRepository,
    SyllabusRepository,
    TopicRepository,
)
from app.domains.identity.authentication import CurrentUser


async def _owns_course(courses: CourseRepository, refs: JobRefs, user: CurrentUser) -> bool:
    if refs.course_id is None or not user.has_any_role(RoleCode.INSTRUCTOR):
        return False
    course = await courses.get(refs.course_id)
    return course is not None and course.owner_user_id == user.id


class SyllabusIngestor:
    """`syllabus.structure` → temas, resultados de aprendizaje y prerrequisitos (D1c, D2)."""

    job_type = JobType.SYLLABUS_STRUCTURE.value
    result_model: type[BaseModel] = SyllabusV1
    progress_label = "Estructurando el contenido del curso"

    def __init__(
        self,
        courses: CourseRepository,
        syllabus: SyllabusRepository,
        topics: TopicRepository,
        outcomes: OutcomeRepository,
        prerequisites: PrerequisiteRepository,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._syllabus = syllabus
        self._topics = topics
        self._outcomes = outcomes
        self._prerequisites = prerequisites
        self._uow = uow

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        return await _owns_course(self._courses, refs, user)

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:
        if not isinstance(result, SyllabusV1):
            raise TypeError("SyllabusIngestor expects a SyllabusV1 result.")
        syllabus = result
        extraction = await self._syllabus.get_extraction_by_job(job.job_id, for_update=True)
        if extraction is None or extraction.is_ingested or not extraction.is_current:
            await self._uow.commit()  # libera el bloqueo de fila
            return False
        _check_syllabus_graph(job.job_id, syllabus)
        course_id = extraction.course_id

        # El resultado nuevo reemplaza a los temas anteriores del curso (re-extracción, D2c).
        for old in await self._topics.list_for_course(course_id):
            await self._topics.set_active(require_id(old), False)
            await self._prerequisites.deactivate_touching(require_id(old))

        created: dict[str, Topic] = {}
        for position, item in enumerate(syllabus.topics, start=1):
            topic = await self._topics.add(
                Topic(
                    course_id=course_id,
                    name=item.name,
                    description=item.description,
                    subtopics=list(item.subtopics),
                    position=position,
                    estimated_minutes=item.estimated_minutes,
                    is_mandatory=item.is_mandatory,
                    bloom_level=item.bloom_level,
                    origin=TopicOrigin.LLM,
                    review_status=TopicReviewStatus.UNCHANGED,
                    extraction_key=item.id,
                )
            )
            created[item.id] = topic
            for outcome in item.learning_outcomes:
                await self._outcomes.add(
                    LearningOutcome(
                        topic_id=require_id(topic),
                        code=outcome.id,
                        statement=outcome.statement,
                        bloom_level=outcome.bloom_level,
                    )
                )
        for item in syllabus.topics:
            for prerequisite_key in item.prerequisites:
                await self._prerequisites.upsert(
                    require_id(created[item.id]),
                    require_id(created[prerequisite_key]),
                    TopicOrigin.LLM,
                )

        await self._syllabus.save_result(
            require_id(extraction),
            syllabus.model_dump(mode="json"),
            f"{syllabus.meta.prompt_id} {syllabus.meta.prompt_version}",
        )
        course = await self._courses.get(course_id)
        if course is not None and course.status == CourseStatus.EXTRACTING:
            await self._courses.update(
                course_id,
                {"status": CourseStatus.IN_REVIEW, "extraction_error_code": None},
            )
        await self._uow.commit()
        return True

    async def on_failed(self, job: JobStatus, error_code: str) -> None:
        extraction = await self._syllabus.get_extraction_by_job(job.job_id, for_update=True)
        if extraction is not None and extraction.is_current and not extraction.is_ingested:
            course = await self._courses.get(extraction.course_id)
            if course is not None and course.status == CourseStatus.EXTRACTING:
                await self._courses.update(
                    extraction.course_id,
                    {
                        "status": CourseStatus.EXTRACTION_FAILED,
                        "extraction_error_code": error_code,
                    },
                )
        await self._uow.commit()

    async def pending_jobs(self) -> list[PendingJob]:
        return [
            PendingJob(job_id=e.ai_job_id, job_type=self.job_type)
            for e in await self._syllabus.pending_extractions()
            if e.ai_job_id is not None
        ]


def _check_syllabus_graph(job_id: str, syllabus: SyllabusV1) -> None:
    """La salida debe tener claves únicas, prerrequisitos conocidos y ningún ciclo."""
    keys = [t.id for t in syllabus.topics]
    if len(set(keys)) != len(keys):
        raise AiResultInvalidError(job_id)
    edges: list[tuple[int, int]] = []
    index = {key: n for n, key in enumerate(keys)}
    for topic in syllabus.topics:
        for prerequisite in topic.prerequisites:
            if prerequisite not in index or prerequisite == topic.id:
                raise AiResultInvalidError(job_id)
            edges.append((index[topic.id], index[prerequisite]))
    if graph.find_cycle(graph.build_graph(edges)) is not None:
        raise AiResultInvalidError(job_id)


class PublicationIngestor:
    """`course.generate_content` → el curso queda `published` (D2 «Aprobar y publicar»).

    Los trabajos hijos (explicaciones, banco de ítems, videos) los ingieren los dominios de
    contenido y evaluación (agentes posteriores); aquí solo se cierra la publicación del curso.
    """

    job_type = JobType.COURSE_GENERATE_CONTENT.value
    result_model: type[BaseModel] = CourseGenerateContentResult
    progress_label = "Generando el contenido del curso"

    def __init__(
        self,
        courses: CourseRepository,
        paths: LearningPathRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._paths = paths
        self._ai = ai
        self._uow = uow

    async def is_owner(self, refs: JobRefs, user: CurrentUser) -> bool:
        return await _owns_course(self._courses, refs, user)

    async def ingest(self, job: JobStatus, result: BaseModel) -> bool:  # noqa: ARG002
        if job.refs.course_id is None:
            return False
        course = await self._courses.get_for_update(job.refs.course_id)
        if course is None or course.status != CourseStatus.GENERATING_CONTENT:
            await self._uow.commit()
            return False
        await self._courses.update(
            require_id(course), {"status": CourseStatus.PUBLISHED, "extraction_error_code": None}
        )
        path = await self._paths.get_by_course(require_id(course))
        if path is not None:
            await self._paths.update(require_id(path), {"status": LearningPathStatus.PUBLISHED})
        await self._uow.commit()
        return True

    async def on_failed(self, job: JobStatus, error_code: str) -> None:
        if job.refs.course_id is not None:
            course = await self._courses.get_for_update(job.refs.course_id)
            if course is not None and course.status == CourseStatus.GENERATING_CONTENT:
                await self._courses.update(
                    require_id(course),
                    {"status": CourseStatus.IN_REVIEW, "extraction_error_code": error_code},
                )
        await self._uow.commit()

    async def pending_jobs(self) -> list[PendingJob]:
        pending: list[PendingJob] = []
        for course in await self._courses.list_by_status(CourseStatus.GENERATING_CONTENT):
            jobs = await self._ai.list_jobs(
                job_type=self.job_type, course_id=require_id(course), limit=20
            )
            pending.extend(PendingJob(job_id=j.job_id, job_type=self.job_type) for j in jobs)
        return pending
