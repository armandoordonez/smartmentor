"""Fixtures de las pruebas unitarias: servicios sobre repositorios en memoria y `FakeAiService`."""

from dataclasses import dataclass

import pytest

from app.domains.ai_gateway.fake import FakeAiService
from app.domains.ai_gateway.service import IngestorRegistry, JobService
from app.domains.courses.ingestion import PublicationIngestor, SyllabusIngestor
from app.domains.courses.service import (
    CourseService,
    PublicationService,
    SyllabusService,
    TopicService,
)
from app.domains.identity.authentication import CurrentUser
from app.domains.identity.entities import Role, User, UserRole
from tests.unit.fakes import (
    FakeUnitOfWork,
    InMemoryCourses,
    InMemoryOutcomes,
    InMemoryPaths,
    InMemoryPrerequisites,
    InMemoryRoles,
    InMemorySyllabus,
    InMemoryTopics,
    InMemoryUserRoles,
    InMemoryUsers,
)

ADMIN_ID, INSTRUCTOR_ID, OTHER_INSTRUCTOR_ID, LEARNER_ID = 1, 2, 3, 4


def current(user_id: int, *roles: str, name: str = "Usuario") -> CurrentUser:
    return CurrentUser(
        id=user_id,
        full_name=name,
        email=f"u{user_id}@example.org",
        roles=frozenset(roles),
        identity_provider="keycloak",
        identity_subject=f"sub-{user_id}",
    )


@dataclass
class World:
    """Todo el dominio de cursos sobre memoria, con `FakeAiService` y los ingestores."""

    ai: FakeAiService
    uow: FakeUnitOfWork
    courses: InMemoryCourses
    paths: InMemoryPaths
    syllabus: InMemorySyllabus
    topics: InMemoryTopics
    outcomes: InMemoryOutcomes
    prerequisites: InMemoryPrerequisites
    users: InMemoryUsers
    course_service: CourseService
    syllabus_service: SyllabusService
    topic_service: TopicService
    publication_service: PublicationService
    job_service: JobService

    admin: CurrentUser
    instructor: CurrentUser
    other_instructor: CurrentUser
    learner: CurrentUser


@pytest.fixture
def world() -> World:
    ai = FakeAiService()
    uow = FakeUnitOfWork()
    roles = InMemoryRoles(
        [
            Role(id=1, code="admin", name="Administrador"),
            Role(id=2, code="instructor", name="Instructor"),
            Role(id=3, code="learner", name="Aprendiz"),
        ]
    )
    user_roles = InMemoryUserRoles(
        [
            UserRole(user_id=ADMIN_ID, role_id=1),
            UserRole(user_id=INSTRUCTOR_ID, role_id=2),
            UserRole(user_id=OTHER_INSTRUCTOR_ID, role_id=2),
            UserRole(user_id=LEARNER_ID, role_id=3),
        ]
    )
    users = InMemoryUsers(
        [
            User(id=ADMIN_ID, full_name="Admin", email="admin@example.org"),
            User(id=INSTRUCTOR_ID, full_name="Instructor", email="instructor@example.org"),
            User(id=OTHER_INSTRUCTOR_ID, full_name="Otro", email="otro@example.org"),
            User(id=LEARNER_ID, full_name="Aprendiz", email="learner@example.org"),
        ],
        user_roles,
        roles,
    )
    courses = InMemoryCourses()
    paths = InMemoryPaths()
    syllabus = InMemorySyllabus()
    topics = InMemoryTopics()
    outcomes = InMemoryOutcomes()
    prerequisites = InMemoryPrerequisites(topics)
    registry = IngestorRegistry(
        [
            SyllabusIngestor(courses, syllabus, topics, outcomes, prerequisites, ai, uow),
            PublicationIngestor(courses, paths, ai, uow),
        ]
    )
    return World(
        ai=ai,
        uow=uow,
        courses=courses,
        paths=paths,
        syllabus=syllabus,
        topics=topics,
        outcomes=outcomes,
        prerequisites=prerequisites,
        users=users,
        course_service=CourseService(courses, paths, users, ai, uow),
        syllabus_service=SyllabusService(courses, syllabus, topics, prerequisites, ai, uow),
        topic_service=TopicService(courses, topics, outcomes, prerequisites, uow),
        publication_service=PublicationService(
            courses, paths, topics, outcomes, prerequisites, ai, uow
        ),
        job_service=JobService(ai, registry),
        admin=current(ADMIN_ID, "admin"),
        instructor=current(INSTRUCTOR_ID, "instructor"),
        other_instructor=current(OTHER_INSTRUCTOR_ID, "instructor"),
        learner=current(LEARNER_ID, "learner"),
    )
