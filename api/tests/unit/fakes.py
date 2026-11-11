"""Repositorios en memoria para probar servicios sin base de datos."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.common.entities import BaseEntity, require_id
from app.domains.courses.entities import (
    Course,
    CourseCounts,
    LearningOutcome,
    SyllabusDocument,
    SyllabusExtraction,
    Topic,
    TopicPrerequisite,
)
from app.domains.identity.entities import (
    Consent,
    DataSubjectRequest,
    Role,
    User,
    UserProfile,
    UserRole,
)
from app.domains.learning_paths.entities import LearningPath


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class InMemoryRepository[E: BaseEntity]:
    def __init__(self, items: list[E] | None = None) -> None:
        self.items: dict[int, E] = {}
        self._next_id = 1
        for item in items or []:
            self._store(item)

    def _store(self, entity: E) -> E:
        stored = replace(entity, id=self._next_id) if entity.id is None else entity
        assert stored.id is not None
        self.items[stored.id] = stored
        self._next_id = max(self._next_id, stored.id) + 1
        return stored

    async def add(self, entity: E) -> E:
        return self._store(entity)

    async def get(self, entity_id: int) -> E | None:
        return self.items.get(entity_id)

    async def search(
        self, *, filters: Mapping[str, Any], active: bool | None, limit: int, offset: int
    ) -> tuple[list[E], int]:
        found = [
            e
            for e in self.items.values()
            if all(getattr(e, k) == v for k, v in filters.items())
            and (active is None or e.active == active)
        ]
        return found[offset : offset + limit], len(found)

    async def update(self, entity_id: int, changes: Mapping[str, Any]) -> E | None:
        current = self.items.get(entity_id)
        if current is None:
            return None
        self.items[entity_id] = replace(current, **changes)
        return self.items[entity_id]

    async def set_active(self, entity_id: int, active: bool) -> E | None:
        return await self.update(entity_id, {"active": active})


# --- identidad --------------------------------------------------------------------------------


class InMemoryRoles(InMemoryRepository[Role]):
    async def get_by_code(self, code: str) -> Role | None:
        return next((r for r in self.items.values() if r.code == code), None)

    async def list_by_codes(self, codes: list[str]) -> list[Role]:
        return [r for r in self.items.values() if r.code in codes and r.active]


class InMemoryUserRoles(InMemoryRepository[UserRole]):
    async def assign_if_absent(self, user_id: int, role_id: int) -> None:
        for existing in self.items.values():
            if existing.user_id == user_id and existing.role_id == role_id:
                self.items[require_id(existing)] = replace(existing, active=True)
                return
        self._store(UserRole(user_id=user_id, role_id=role_id))

    async def list_for_user(self, user_id: int) -> list[UserRole]:
        return [ur for ur in self.items.values() if ur.user_id == user_id]


class InMemoryUsers(InMemoryRepository[User]):
    def __init__(
        self,
        items: list[User],
        user_roles: InMemoryUserRoles,
        roles: InMemoryRoles,
    ) -> None:
        super().__init__(items)
        self._user_roles = user_roles
        self._roles = roles
        self.locks = 0

    async def get_by_identity(self, provider: str, subject: str) -> User | None:
        return next(
            (
                u
                for u in self.items.values()
                if u.identity_provider == provider and u.identity_subject == subject
            ),
            None,
        )

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.items.values() if u.email.lower() == email.lower()), None)

    async def get_role_codes(self, user_id: int) -> frozenset[str]:
        role_ids = {
            ur.role_id
            for ur in self._user_roles.items.values()
            if ur.user_id == user_id and ur.active
        }
        return frozenset(
            r.code for r in self._roles.items.values() if r.id in role_ids and r.active
        )

    async def link_identity_by_email(self, email: str, provider: str, subject: str) -> User | None:
        user = await self.get_by_email(email)
        if user is None or user.identity_subject is not None:
            return None
        return await self.update(
            require_id(user), {"identity_provider": provider, "identity_subject": subject}
        )

    async def create_if_absent(self, user: User) -> User | None:
        if await self.get_by_email(user.email) is not None:
            return None
        if (
            user.identity_provider
            and user.identity_subject
            and await self.get_by_identity(user.identity_provider, user.identity_subject)
        ):
            return None
        return self._store(user)

    async def count_active_admins(self, *, excluding_user_id: int | None = None) -> int:
        count = 0
        for user in self.items.values():
            if not user.active or user.id == excluding_user_id:
                continue
            if "admin" in await self.get_role_codes(require_id(user)):
                count += 1
        return count

    async def lock_admin_membership(self) -> None:
        self.locks += 1


class InMemoryProfiles:
    def __init__(self) -> None:
        self.items: dict[int, UserProfile] = {}

    async def get_by_user_id(self, user_id: int) -> UserProfile | None:
        return self.items.get(user_id)

    async def save(self, profile: UserProfile) -> UserProfile:
        stored = replace(profile, id=profile.id or len(self.items) + 1)
        self.items[profile.user_id] = stored
        return stored


class InMemoryConsents:
    def __init__(self) -> None:
        self.items: list[Consent] = []

    async def add(self, consent: Consent) -> Consent:
        stored = replace(consent, id=len(self.items) + 1, granted_at=datetime.now(UTC))
        self.items.append(stored)
        return stored

    async def list_for_user(self, user_id: int) -> list[Consent]:
        return [c for c in self.items if c.user_id == user_id]

    async def latest(self, user_id: int, consent_type: str) -> Consent | None:
        found = [c for c in self.items if c.user_id == user_id and c.consent_type == consent_type]
        return found[-1] if found else None

    async def revoke(self, consent_id: int) -> Consent | None:
        for index, consent in enumerate(self.items):
            if consent.id == consent_id:
                self.items[index] = replace(consent, revoked_at=datetime.now(UTC))
                return self.items[index]
        return None


class InMemoryDataSubjectRequests:
    def __init__(self) -> None:
        self.items: list[DataSubjectRequest] = []

    async def add(self, request: DataSubjectRequest) -> DataSubjectRequest:
        stored = replace(request, id=len(self.items) + 1)
        self.items.append(stored)
        return stored


# --- cursos -----------------------------------------------------------------------------------


class InMemoryCourses(InMemoryRepository[Course]):
    async def get_for_update(self, course_id: int) -> Course | None:
        return await self.get(course_id)

    async def list_by_status(self, status: str) -> list[Course]:
        return [c for c in self.items.values() if c.status == status and c.active]

    async def counts(self, course_ids: list[int]) -> dict[int, CourseCounts]:
        del course_ids  # la memoria no cruza temas ni inscripciones: todo cuenta 0
        return {}


class InMemoryPaths(InMemoryRepository[LearningPath]):
    async def get_by_course(self, course_id: int) -> LearningPath | None:
        return next((p for p in self.items.values() if p.course_id == course_id), None)

    async def by_course_ids(self, course_ids: list[int]) -> dict[int, LearningPath]:
        return {p.course_id: p for p in self.items.values() if p.course_id in course_ids}


class InMemorySyllabus:
    def __init__(self) -> None:
        self.documents: dict[int, SyllabusDocument] = {}
        self.extractions: dict[int, SyllabusExtraction] = {}

    async def add_document(self, document: SyllabusDocument) -> SyllabusDocument:
        stored = replace(document, id=len(self.documents) + 1)
        self.documents[require_id(stored)] = stored
        return stored

    async def latest_document(self, course_id: int) -> SyllabusDocument | None:
        found = [d for d in self.documents.values() if d.course_id == course_id]
        return found[-1] if found else None

    async def add_extraction(self, extraction: SyllabusExtraction) -> SyllabusExtraction:
        for key, existing in list(self.extractions.items()):
            if existing.course_id == extraction.course_id:
                self.extractions[key] = replace(existing, is_current=False)
        stored = replace(extraction, id=len(self.extractions) + 1)
        self.extractions[require_id(stored)] = stored
        return stored

    async def current_extraction(self, course_id: int) -> SyllabusExtraction | None:
        found = [e for e in self.extractions.values() if e.course_id == course_id and e.is_current]
        return found[-1] if found else None

    async def resolve_ai_job_id(self, public_id: str) -> int | None:
        return None


class InMemoryTopics(InMemoryRepository[Topic]):
    async def list_for_course(
        self, course_id: int, *, include_inactive: bool = False
    ) -> list[Topic]:
        found = [
            t
            for t in self.items.values()
            if t.course_id == course_id and (include_inactive or t.active)
        ]
        return sorted(found, key=lambda t: (t.position, require_id(t)))


class InMemoryOutcomes(InMemoryRepository[LearningOutcome]):
    async def next_code_number(self, topic_id: int) -> int:
        used = [
            int(o.code.rsplit("_", 1)[1])
            for o in self.items.values()
            if o.topic_id == topic_id and o.code.rsplit("_", 1)[-1].isdigit()
        ]
        return max(used, default=0) + 1

    async def list_for_topics(self, topic_ids: list[int]) -> dict[int, list[LearningOutcome]]:
        grouped: dict[int, list[LearningOutcome]] = {}
        for outcome in self.items.values():
            if outcome.topic_id in topic_ids and outcome.active:
                grouped.setdefault(outcome.topic_id, []).append(outcome)
        return grouped


class InMemoryPrerequisites(InMemoryRepository[TopicPrerequisite]):
    def __init__(self, topics: InMemoryTopics) -> None:
        super().__init__()
        self._topics = topics

    async def list_for_course(self, course_id: int) -> list[TopicPrerequisite]:
        active = {require_id(t) for t in await self._topics.list_for_course(course_id) if t.active}
        return [
            e
            for e in self.items.values()
            if e.active and e.topic_id in active and e.prerequisite_topic_id in active
        ]

    async def upsert(
        self, topic_id: int, prerequisite_topic_id: int, origin: str
    ) -> TopicPrerequisite:
        for edge in self.items.values():
            if edge.topic_id == topic_id and edge.prerequisite_topic_id == prerequisite_topic_id:
                self.items[require_id(edge)] = replace(edge, active=True, origin=origin)
                return self.items[require_id(edge)]
        return self._store(
            TopicPrerequisite(
                topic_id=topic_id, prerequisite_topic_id=prerequisite_topic_id, origin=origin
            )
        )

    async def deactivate_touching(self, topic_id: int) -> None:
        for key, edge in list(self.items.items()):
            if topic_id in (edge.topic_id, edge.prerequisite_topic_id):
                self.items[key] = replace(edge, active=False)
