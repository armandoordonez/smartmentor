"""Casos de uso de cursos: cursos, syllabus, temas, revisión y publicación (CU-24, CU-25, D1, D2).

Reglas de propiedad (sección 18.2 del plan): el instructor solo ve y modifica sus cursos y el
administrador todos. Un curso ajeno responde 404, nunca 403.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.common.constants import (
    CourseStatus,
    JobType,
    LearningPathStatus,
    RoleCode,
    TopicOrigin,
    TopicReviewStatus,
)
from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.domains.ai_gateway.entities import JobRef, JobRefs
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.courses import graph
from app.domains.courses.entities import (
    Course,
    LearningOutcome,
    SyllabusDocument,
    SyllabusExtraction,
    Topic,
    TopicPrerequisite,
)
from app.domains.courses.repository import (
    CourseRepository,
    LearningPathRepository,
    OutcomeRepository,
    PrerequisiteRepository,
    SyllabusRepository,
    TopicRepository,
)
from app.domains.courses.syllabus_text import ExtractedSyllabus
from app.domains.identity.authentication import CurrentUser
from app.domains.identity.repository import UserRepository
from app.domains.learning_paths.entities import LearningPath

EDITABLE_STATUSES = frozenset(
    {CourseStatus.DRAFT, CourseStatus.IN_REVIEW, CourseStatus.EXTRACTION_FAILED}
)
QUIZ_ITEMS_PER_TOPIC = 23
FINAL_VERSIONS = 2


async def load_course(courses: CourseRepository, user: CurrentUser, course_id: int) -> Course:
    """Curso al que el usuario tiene acceso; si no, `404 COURSE_NOT_FOUND`."""
    course = await courses.get(course_id)
    if course is None or not course.active:
        raise NotFoundError("Course", course_id, code="COURSE_NOT_FOUND")
    is_admin = user.has_any_role(RoleCode.ADMIN)
    owns = user.has_any_role(RoleCode.INSTRUCTOR) and course.owner_user_id == user.id
    if not (is_admin or owns):
        raise NotFoundError("Course", course_id, code="COURSE_NOT_FOUND")
    return course


def _require_editable(course: Course) -> None:
    if course.status == CourseStatus.EXTRACTING:
        raise ConflictError(
            "The syllabus is being processed; wait for the extraction to finish.",
            code="EXTRACTION_IN_PROGRESS",
        )
    if course.status not in EDITABLE_STATUSES:
        raise InvalidStateTransitionError(
            f"The course cannot be edited while it is {course.status}."
        )


# --- Cursos -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseView:
    course: Course
    learning_path: LearningPath | None
    extraction_job_id: str | None = None


class CourseService:
    def __init__(
        self,
        courses: CourseRepository,
        paths: LearningPathRepository,
        syllabus: SyllabusRepository,
        users: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._paths = paths
        self._syllabus = syllabus
        self._users = users
        self._uow = uow

    async def create(
        self,
        user: CurrentUser,
        *,
        name: str,
        description: str | None,
        path_name: str | None,
        group_label: str | None,
    ) -> CourseView:
        # Un instructor queda como dueño; si crea un administrador sin ser instructor, el curso
        # queda «Sin asignar» hasta que lo asigne (AD5).
        owner_id = user.id if user.has_any_role(RoleCode.INSTRUCTOR) else None
        course = await self._courses.add(
            Course(owner_user_id=owner_id, name=name, description=description)
        )
        path = await self._paths.add(
            LearningPath(
                course_id=require_id(course),
                name=path_name or name,
                group_label=group_label,
                status=LearningPathStatus.DRAFT,
            )
        )
        await self._uow.commit()
        return CourseView(course, path)

    async def get(self, user: CurrentUser, course_id: int) -> CourseView:
        course = await load_course(self._courses, user, course_id)
        path = await self._paths.get_by_course(course_id)
        current = await self._syllabus.current_extraction(course_id)
        return CourseView(course, path, current.ai_job_id if current else None)

    async def list_courses(
        self,
        user: CurrentUser,
        *,
        mine: bool,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[CourseView], int]:
        filters: dict[str, Any] = {}
        # Un instructor que no es administrador solo ve los suyos, aunque no pida `mine=true`.
        if mine or not user.has_any_role(RoleCode.ADMIN):
            filters["owner_user_id"] = user.id
        if status is not None:
            filters["status"] = status
        courses, total = await self._courses.search(
            filters=filters, active=True, limit=limit, offset=offset
        )
        paths = await self._paths.by_course_ids([require_id(c) for c in courses])
        return [CourseView(c, paths.get(require_id(c))) for c in courses], total

    async def update(
        self, user: CurrentUser, course_id: int, changes: dict[str, Any]
    ) -> CourseView:
        await load_course(self._courses, user, course_id)
        if changes:
            await self._courses.update(course_id, changes)
            await self._uow.commit()
        return await self.get(user, course_id)

    async def assign_owner(
        self, user: CurrentUser, course_id: int, owner_user_id: int | None
    ) -> CourseView:
        await load_course(self._courses, user, course_id)
        if owner_user_id is not None:
            owner = await self._users.get(owner_user_id)
            roles = await self._users.get_role_codes(owner_user_id) if owner else frozenset()
            if owner is None or not owner.active or RoleCode.INSTRUCTOR not in roles:
                raise BusinessRuleError(
                    "The owner must be an active user with the instructor role.",
                    code="OWNER_NOT_FOUND",
                )
        await self._courses.update(course_id, {"owner_user_id": owner_user_id})
        await self._uow.commit()
        return await self.get(user, course_id)


# --- Syllabus y extracción --------------------------------------------------------------------


class SyllabusService:
    def __init__(
        self,
        courses: CourseRepository,
        syllabus: SyllabusRepository,
        topics: TopicRepository,
        prerequisites: PrerequisiteRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._syllabus = syllabus
        self._topics = topics
        self._prerequisites = prerequisites
        self._ai = ai
        self._uow = uow

    async def submit(
        self, user: CurrentUser, course_id: int, extracted: ExtractedSyllabus
    ) -> JobRef:
        """Guarda el syllabus ya extraído y encola `syllabus.structure` (D1b, D1c)."""
        course = await load_course(self._courses, user, course_id)
        _require_editable(course)
        document = await self._syllabus.add_document(
            SyllabusDocument(
                course_id=course_id,
                source_type=extracted.source_type,
                file_name=extracted.file_name,
                file_sha256=extracted.sha256,
                byte_size=extracted.byte_size,
                page_count=extracted.page_count,
                extracted_char_count=extracted.char_count,
                extracted_text=extracted.text,
            )
        )
        return await self._start_extraction(course, require_id(document), version=1)

    async def re_extract(
        self, user: CurrentUser, course_id: int, *, confirm_discard_review: bool
    ) -> JobRef:
        """Vuelve a extraer los temas del último syllabus; la revisión se reemplaza (D2c)."""
        course = await load_course(self._courses, user, course_id)
        _require_editable(course)
        document = await self._syllabus.latest_document(course_id)
        if document is None:
            raise InvalidStateTransitionError("The course has no syllabus to extract again.")
        reviewed = [
            t
            for t in await self._topics.list_for_course(course_id)
            if t.origin == TopicOrigin.INSTRUCTOR or t.review_status != TopicReviewStatus.UNCHANGED
        ]
        if reviewed and not confirm_discard_review:
            raise BusinessRuleError(
                "The review would be discarded; send confirm_discard_review=true to continue.",
                code="BUSINESS_RULE_VIOLATION",
            )
        previous = await self._syllabus.count_extractions(require_id(document))
        return await self._start_extraction(course, require_id(document), version=previous + 1)

    async def _start_extraction(self, course: Course, document_id: int, *, version: int) -> JobRef:
        course_id = require_id(course)
        job = await self._ai.submit_job(
            JobType.SYLLABUS_STRUCTURE,
            {"syllabus_document_id": document_id},
            f"{JobType.SYLLABUS_STRUCTURE}:syllabus_document:{document_id}:v{version}",
            JobRefs(course_id=course_id),
        )
        await self._syllabus.add_extraction(
            SyllabusExtraction(
                course_id=course_id, syllabus_document_id=document_id, ai_job_id=job.job_id
            )
        )
        await self._courses.update(
            course_id, {"status": CourseStatus.EXTRACTING, "extraction_error_code": None}
        )
        await self._uow.commit()
        return job

    async def metrics(self, user: CurrentUser, course_id: int) -> "ExtractionMetrics":
        """Insumos del F1 (D2, AD3): lo que dio el LLM frente a lo que dejó el instructor."""
        await load_course(self._courses, user, course_id)
        extraction = await self._syllabus.current_extraction(course_id)
        if extraction is None or extraction.raw_output is None:
            return ExtractionMetrics(topics=None, prerequisites=None, corrections=0)
        topics = await self._topics.list_for_course(course_id, include_inactive=True)
        edges = await self._prerequisites.list_for_course(course_id)
        return compute_extraction_metrics(extraction.raw_output, topics, edges)


@dataclass(frozen=True)
class Score:
    precision: float | None
    recall: float | None
    f1: float | None


@dataclass(frozen=True)
class ExtractionMetrics:
    topics: Score | None
    prerequisites: Score | None
    corrections: int


def _score(llm: set[Any], final: set[Any]) -> Score:
    hits = len(llm & final)
    precision = hits / len(llm) if llm else None
    recall = hits / len(final) if final else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else (0.0 if precision is not None and recall is not None else None)
    )
    return Score(precision, recall, f1)


def compute_extraction_metrics(
    raw_output: dict[str, Any], topics: Sequence[Topic], edges: Sequence[TopicPrerequisite]
) -> ExtractionMetrics:
    """Precisión, exhaustividad y F1 de temas y prerrequisitos frente a la salida original."""
    llm_topics = {t["id"] for t in raw_output.get("topics", [])}
    llm_edges = {
        (t["id"], prerequisite)
        for t in raw_output.get("topics", [])
        for prerequisite in t.get("prerequisites", [])
    }
    active = [t for t in topics if t.active]
    key_of = {require_id(t): t.extraction_key or f"topic:{t.id}" for t in active}
    final_topics = set(key_of.values())
    final_edges = {
        (key_of[e.topic_id], key_of[e.prerequisite_topic_id])
        for e in edges
        if e.topic_id in key_of and e.prerequisite_topic_id in key_of
    }
    corrections = sum(
        1
        for t in topics
        if t.review_status
        in (TopicReviewStatus.CORRECTED, TopicReviewStatus.ADDED, TopicReviewStatus.DELETED)
        and (t.active or t.review_status == TopicReviewStatus.DELETED)
    )
    return ExtractionMetrics(
        topics=_score(llm_topics, final_topics),
        prerequisites=_score(llm_edges, final_edges),
        corrections=corrections,
    )


# --- Temas ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeDraft:
    statement: str
    bloom_level: str
    id: int | None = None


@dataclass(frozen=True)
class TopicDraft:
    name: str
    description: str | None = None
    subtopics: list[str] = field(default_factory=list)
    position: int | None = None
    estimated_minutes: int | None = None
    is_mandatory: bool = False
    bloom_level: str | None = None
    learning_outcomes: list[OutcomeDraft] = field(default_factory=list)
    prerequisite_topic_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class TopicView:
    topic: Topic
    learning_outcomes: list[LearningOutcome]
    prerequisite_topic_ids: list[int]


@dataclass(frozen=True)
class TopicList:
    topics: list[TopicView]
    review_counts: dict[str, int]


@dataclass(frozen=True)
class TopicGraph:
    nodes: list[Topic]
    edges: list[TopicPrerequisite]


class TopicService:
    def __init__(
        self,
        courses: CourseRepository,
        topics: TopicRepository,
        outcomes: OutcomeRepository,
        prerequisites: PrerequisiteRepository,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._topics = topics
        self._outcomes = outcomes
        self._prerequisites = prerequisites
        self._uow = uow

    # --- lectura ---
    async def list_topics(self, user: CurrentUser, course_id: int) -> TopicList:
        await load_course(self._courses, user, course_id)
        everything = await self._topics.list_for_course(course_id, include_inactive=True)
        active = [t for t in everything if t.active]
        views = await self._views(course_id, active)
        counts = {s.value: 0 for s in TopicReviewStatus}
        for topic in active:
            if topic.review_status != TopicReviewStatus.DELETED:
                counts[topic.review_status] += 1
        counts[TopicReviewStatus.DELETED] = sum(
            1 for t in everything if t.review_status == TopicReviewStatus.DELETED
        )
        return TopicList(views, counts)

    async def graph(self, user: CurrentUser, course_id: int) -> TopicGraph:
        await load_course(self._courses, user, course_id)
        nodes = await self._topics.list_for_course(course_id)
        return TopicGraph(nodes, await self._prerequisites.list_for_course(course_id))

    async def _views(self, course_id: int, topics: list[Topic]) -> list[TopicView]:
        outcomes = await self._outcomes.list_for_topics([require_id(t) for t in topics])
        edges = await self._prerequisites.list_for_course(course_id)
        by_topic: dict[int, list[int]] = {}
        for edge in edges:
            by_topic.setdefault(edge.topic_id, []).append(edge.prerequisite_topic_id)
        return [
            TopicView(t, outcomes.get(require_id(t), []), by_topic.get(require_id(t), []))
            for t in topics
        ]

    async def _view(self, topic: Topic) -> TopicView:
        views = await self._views(topic.course_id, [topic])
        return views[0]

    # --- escritura ---
    async def create(self, user: CurrentUser, course_id: int, draft: TopicDraft) -> TopicView:
        course = await load_course(self._courses, user, course_id)
        _require_editable(course)
        siblings = await self._topics.list_for_course(course_id)
        await self._validate_prerequisites(course_id, None, draft.prerequisite_topic_ids, siblings)
        position = draft.position or (max((t.position for t in siblings), default=0) + 1)
        topic = await self._topics.add(
            Topic(
                course_id=course_id,
                name=draft.name,
                description=draft.description,
                subtopics=list(draft.subtopics),
                position=position,
                estimated_minutes=draft.estimated_minutes,
                is_mandatory=draft.is_mandatory,
                bloom_level=draft.bloom_level,
                origin=TopicOrigin.INSTRUCTOR,
                review_status=TopicReviewStatus.ADDED,
            )
        )
        topic_id = require_id(topic)
        for number, outcome in enumerate(draft.learning_outcomes, start=1):
            await self._outcomes.add(
                LearningOutcome(
                    topic_id=topic_id,
                    code=f"lo_t{topic_id}_{number}",
                    statement=outcome.statement,
                    bloom_level=outcome.bloom_level,
                )
            )
        for prerequisite_id in dict.fromkeys(draft.prerequisite_topic_ids):
            await self._prerequisites.upsert(topic_id, prerequisite_id, TopicOrigin.INSTRUCTOR)
        await self._uow.commit()
        return await self._view(topic)

    async def update(self, user: CurrentUser, topic_id: int, draft: TopicDraft) -> TopicView:
        topic = await self._load_topic(user, topic_id)
        course = await load_course(self._courses, user, topic.course_id)
        _require_editable(course)
        siblings = await self._topics.list_for_course(topic.course_id)
        await self._validate_prerequisites(
            topic.course_id, topic_id, draft.prerequisite_topic_ids, siblings
        )

        before = await self._view(topic)
        outcomes_changed = await self._sync_outcomes(topic_id, before.learning_outcomes, draft)
        prerequisites_changed = await self._sync_prerequisites(
            topic_id, set(before.prerequisite_topic_ids), draft.prerequisite_topic_ids
        )
        changes: dict[str, Any] = {
            "name": draft.name,
            "description": draft.description,
            "subtopics": list(draft.subtopics),
            "estimated_minutes": draft.estimated_minutes,
            "is_mandatory": draft.is_mandatory,
            "bloom_level": draft.bloom_level,
        }
        if draft.position is not None:
            changes["position"] = draft.position
        fields_changed = any(getattr(topic, key) != value for key, value in changes.items())
        if (
            (fields_changed or outcomes_changed or prerequisites_changed)
            and topic.origin == TopicOrigin.LLM
            and topic.review_status == TopicReviewStatus.UNCHANGED
        ):
            changes["review_status"] = TopicReviewStatus.CORRECTED
        updated = await self._topics.update(topic_id, changes)
        await self._uow.commit()
        return await self._view(updated or topic)

    async def deactivate(self, user: CurrentUser, topic_id: int) -> TopicView:
        topic = await self._load_topic(user, topic_id)
        course = await load_course(self._courses, user, topic.course_id)
        _require_editable(course)
        updated = await self._topics.update(
            topic_id, {"active": False, "review_status": TopicReviewStatus.DELETED}
        )
        await self._prerequisites.deactivate_touching(topic_id)
        await self._uow.commit()
        return TopicView(updated or topic, [], [])

    async def _load_topic(self, user: CurrentUser, topic_id: int) -> Topic:
        topic = await self._topics.get(topic_id)
        if topic is None or not topic.active:
            raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND")
        # Si el curso no es del usuario, el tema tampoco: mismo 404.
        try:
            await load_course(self._courses, user, topic.course_id)
        except NotFoundError as exc:
            raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND") from exc
        return topic

    async def _validate_prerequisites(
        self, course_id: int, topic_id: int | None, wanted: list[int], siblings: list[Topic]
    ) -> None:
        valid = {require_id(t) for t in siblings}
        for prerequisite_id in wanted:
            if topic_id is not None and prerequisite_id == topic_id:
                raise BusinessRuleError(
                    "A topic cannot be its own prerequisite.", code="PREREQUISITE_SELF"
                )
            if prerequisite_id not in valid:
                raise BusinessRuleError(
                    f"The prerequisite topic {prerequisite_id} does not exist in this course.",
                    code="PREREQUISITE_TOPIC_NOT_FOUND",
                )
        if topic_id is None:
            return  # un tema nuevo no tiene quién dependa de él: no puede cerrar un ciclo
        current = await self._prerequisites.list_for_course(course_id)
        edges = [
            (e.topic_id, e.prerequisite_topic_id) for e in current if e.topic_id != topic_id
        ] + [(topic_id, p) for p in wanted]
        cycle = graph.find_cycle(graph.build_graph(edges), starts=[topic_id])
        if cycle is not None:
            raise BusinessRuleError(
                "The prerequisites form a cycle.",
                code="PREREQUISITE_CYCLE",
                extra={"cycle": cycle},
            )

    async def _sync_outcomes(
        self, topic_id: int, current: list[LearningOutcome], draft: TopicDraft
    ) -> bool:
        by_id = {require_id(o): o for o in current}
        changed = False
        kept: set[int] = set()
        added: list[LearningOutcome] = []
        for outcome in draft.learning_outcomes:
            if outcome.id is None:
                created = await self._outcomes.add(
                    LearningOutcome(
                        topic_id=topic_id,
                        code=_next_outcome_code(topic_id, [*by_id.values(), *added]),
                        statement=outcome.statement,
                        bloom_level=outcome.bloom_level,
                    )
                )
                added.append(created)
                kept.add(require_id(created))
                changed = True
                continue
            existing = by_id.get(outcome.id)
            if existing is None:
                raise BusinessRuleError(
                    f"The learning outcome {outcome.id} does not belong to this topic.",
                    code="REFERENCE_NOT_FOUND",
                )
            kept.add(outcome.id)
            if (existing.statement, existing.bloom_level) != (
                outcome.statement,
                outcome.bloom_level,
            ):
                await self._outcomes.update(
                    outcome.id, {"statement": outcome.statement, "bloom_level": outcome.bloom_level}
                )
                changed = True
        for outcome_id in by_id.keys() - kept:
            await self._outcomes.set_active(outcome_id, False)
            changed = True
        return changed

    async def _sync_prerequisites(
        self, topic_id: int, current: set[int], wanted_list: list[int]
    ) -> bool:
        wanted = set(wanted_list)
        for prerequisite_id in wanted - current:
            await self._prerequisites.upsert(topic_id, prerequisite_id, TopicOrigin.INSTRUCTOR)
        if current - wanted:
            edges = await self._prerequisites.list_for_course(
                (await self._topics.get(topic_id) or _missing(topic_id)).course_id
            )
            for edge in edges:
                if edge.topic_id == topic_id and edge.prerequisite_topic_id in current - wanted:
                    await self._prerequisites.set_active(require_id(edge), False)
        return wanted != current


def _next_outcome_code(topic_id: int, existing: Sequence[LearningOutcome]) -> str:
    """`lo_t<tema>_<n>` con `n` mayor que cualquiera ya usado (cumple `^lo_[a-z0-9_]+_\\d+$`)."""
    used = [int(o.code.rsplit("_", 1)[1]) for o in existing if o.code.rsplit("_", 1)[-1].isdigit()]
    return f"lo_t{topic_id}_{max(used, default=0) + 1}"


def _missing(topic_id: int) -> Topic:
    raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND")


# --- Publicación ------------------------------------------------------------------------------


class PublicationService:
    def __init__(
        self,
        courses: CourseRepository,
        paths: LearningPathRepository,
        topics: TopicRepository,
        outcomes: OutcomeRepository,
        prerequisites: PrerequisiteRepository,
        ai: AiServicePort,
        uow: UnitOfWork,
    ) -> None:
        self._courses = courses
        self._paths = paths
        self._topics = topics
        self._outcomes = outcomes
        self._prerequisites = prerequisites
        self._ai = ai
        self._uow = uow

    async def publish(self, user: CurrentUser, course_id: int) -> JobRef:
        """Valida el DAG y la revisión y dispara la generación del contenido (D2)."""
        course = await load_course(self._courses, user, course_id)
        if course.status == CourseStatus.EXTRACTING:
            raise ConflictError("The extraction is still running.", code="EXTRACTION_IN_PROGRESS")
        if course.status != CourseStatus.IN_REVIEW:
            raise InvalidStateTransitionError(
                f"Only a course in review can be published (it is {course.status})."
            )
        topics = await self._topics.list_for_course(course_id)
        edges = await self._prerequisites.list_for_course(course_id)
        cycle = graph.find_cycle(
            graph.build_graph((e.topic_id, e.prerequisite_topic_id) for e in edges)
        )
        if cycle is not None:
            raise BusinessRuleError(
                "The prerequisites form a cycle.",
                code="PREREQUISITE_CYCLE",
                extra={"cycle": cycle},
            )
        outcomes = await self._outcomes.list_for_topics([require_id(t) for t in topics])
        without_outcomes = [require_id(t) for t in topics if not outcomes.get(require_id(t))]
        if not topics or without_outcomes:
            raise BusinessRuleError(
                "Every topic needs at least one learning outcome before publishing.",
                code="COURSE_REVIEW_INCOMPLETE",
                extra={"missing": without_outcomes},
            )
        path = await self._paths.get_by_course(course_id)
        if path is None:
            raise InvalidStateTransitionError("The course has no learning path.")
        digest = _content_digest(topics, outcomes, edges)
        job = await self._ai.submit_job(
            JobType.COURSE_GENERATE_CONTENT,
            {
                "course_id": course_id,
                "learning_path_id": require_id(path),
                "quiz_items_per_topic": QUIZ_ITEMS_PER_TOPIC,
                "final_versions": FINAL_VERSIONS,
            },
            f"{JobType.COURSE_GENERATE_CONTENT}:course:{course_id}:{digest}",
            JobRefs(course_id=course_id),
        )
        await self._courses.update(
            course_id,
            {"status": CourseStatus.GENERATING_CONTENT, "extraction_error_code": None},
        )
        await self._uow.commit()
        return job


def _content_digest(
    topics: Sequence[Topic],
    outcomes: dict[int, list[LearningOutcome]],
    edges: Sequence[TopicPrerequisite],
) -> str:
    """Versión del contenido del curso: cambia si cambia algo que alimenta la generación."""
    payload = {
        "topics": [
            [
                t.id,
                t.name,
                t.description,
                t.subtopics,
                t.position,
                t.estimated_minutes,
                t.is_mandatory,
                [[o.id, o.statement, o.bloom_level] for o in outcomes.get(require_id(t), [])],
            ]
            for t in topics
        ],
        "edges": sorted([e.topic_id, e.prerequisite_topic_id] for e in edges),
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:12]
