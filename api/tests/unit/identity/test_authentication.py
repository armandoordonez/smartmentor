"""Primer ingreso (CU-34, G-04): creación del usuario y del rol `learner`, enlace por correo."""

import asyncio

import pytest

from app.common.exceptions import ConflictError, ForbiddenError
from app.domains.identity.authentication import AuthenticationService, ExternalIdentity
from app.domains.identity.entities import Role, User, UserRole
from tests.unit.fakes import FakeUnitOfWork, InMemoryRoles, InMemoryUserRoles, InMemoryUsers


def make_service(
    users: list[User], user_roles: list[UserRole] | None = None
) -> tuple[AuthenticationService, InMemoryUsers, InMemoryUserRoles, FakeUnitOfWork]:
    roles = InMemoryRoles(
        [
            Role(id=1, code="admin", name="A"),
            Role(id=2, code="instructor", name="I"),
            Role(id=3, code="learner", name="L"),
        ]
    )
    assignments = InMemoryUserRoles(
        user_roles if user_roles is not None else [UserRole(user_id=10, role_id=2)]
    )
    repo = InMemoryUsers(users, assignments, roles)
    uow = FakeUnitOfWork()
    return (
        AuthenticationService(repo, roles, assignments, uow, provider="keycloak"),
        repo,
        assignments,
        uow,
    )


def identity(
    sub: str = "sub-1", email: str | None = "ana@example.com", verified: bool = True
) -> ExternalIdentity:
    return ExternalIdentity(
        subject=sub, email=email, email_verified=verified, full_name="Ana Pérez"
    )


async def test_unknown_verified_user_is_created_with_the_learner_role() -> None:
    service, repo, _, uow = make_service([])
    current = await service.resolve(identity())
    assert current.roles == frozenset({"learner"})
    assert current.is_new_user is True
    assert current.default_role == "learner"
    created = await repo.get_by_identity("keycloak", "sub-1")
    assert created is not None
    assert created.full_name == "Ana Pérez"
    assert uow.commits == 1


async def test_the_second_call_returns_the_same_user_and_is_not_new() -> None:
    service, repo, _, _ = make_service([])
    first = await service.resolve(identity())
    second = await service.resolve(identity())
    assert second.id == first.id
    assert second.is_new_user is False
    assert len(repo.items) == 1


async def test_two_simultaneous_first_calls_create_one_user() -> None:
    service, repo, assignments, _ = make_service([])
    results = await asyncio.gather(service.resolve(identity()), service.resolve(identity()))
    assert results[0].id == results[1].id
    assert len(repo.items) == 1
    learner_assignments = [ur for ur in assignments.items.values() if ur.role_id == 3]
    assert len(learner_assignments) == 1


async def test_full_name_falls_back_to_the_email_local_part() -> None:
    service, repo, _, _ = make_service([])
    await service.resolve(ExternalIdentity("sub-1", "ana.perez@example.com", True, None))
    created = await repo.get_by_identity("keycloak", "sub-1")
    assert created is not None
    assert created.full_name == "ana.perez"


async def test_returning_user_is_found_by_subject_without_writes() -> None:
    linked = User(
        id=10,
        full_name="Doc",
        email="doc@example.com",
        identity_provider="keycloak",
        identity_subject="sub-9",
    )
    service, _, _, uow = make_service([linked])
    current = await service.resolve(identity(sub="sub-9", email="otro-correo@example.com"))
    assert current.id == 10
    assert current.roles == frozenset({"instructor"})
    assert uow.commits == 0


async def test_existing_user_is_linked_by_verified_email_and_keeps_its_roles() -> None:
    precreated = User(id=10, full_name="Doc", email="Doc@Example.com")
    service, repo, _, uow = make_service([precreated])
    current = await service.resolve(identity(sub="sub-7", email="doc@example.com"))
    assert current.id == 10
    assert current.roles == frozenset({"instructor"})  # no se agrega learner
    assert current.is_new_user is False
    linked = await repo.get(10)
    assert linked is not None
    assert linked.identity_subject == "sub-7"
    assert uow.commits == 1


async def test_unverified_email_never_creates_or_links() -> None:
    service, repo, _, uow = make_service([User(id=10, full_name="Doc", email="ana@example.com")])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(verified=False))
    assert error.value.code == "EMAIL_NOT_VERIFIED"
    existing = await repo.get(10)
    assert existing is not None
    assert existing.identity_subject is None
    assert uow.commits == 0


async def test_token_without_email_is_rejected() -> None:
    service, _, _, _ = make_service([])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(email=None))
    assert error.value.code == "EMAIL_NOT_VERIFIED"


async def test_email_of_a_user_linked_to_another_identity_is_a_conflict() -> None:
    owner = User(
        id=10,
        full_name="Doc",
        email="ana@example.com",
        identity_provider="keycloak",
        identity_subject="otro",
    )
    service, _, _, _ = make_service([owner])
    with pytest.raises(ConflictError) as error:
        await service.resolve(identity(sub="intruso"))
    assert error.value.code == "IDENTITY_ALREADY_LINKED"


async def test_deactivated_user_cannot_log_in() -> None:
    off = User(
        id=10,
        full_name="Doc",
        email="doc@example.com",
        identity_provider="keycloak",
        identity_subject="sub-9",
        active=False,
    )
    service, _, _, _ = make_service([off])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(sub="sub-9"))
    assert error.value.code == "ACCOUNT_DEACTIVATED"


async def test_default_role_is_the_highest_privilege_and_roles_are_ordered() -> None:
    user = User(
        id=10,
        full_name="Doc",
        email="d@example.com",
        identity_provider="keycloak",
        identity_subject="s",
    )
    service, _, _, _ = make_service(
        [user],
        [
            UserRole(user_id=10, role_id=3),
            UserRole(user_id=10, role_id=2),
            UserRole(user_id=10, role_id=1),
        ],
    )
    current = await service.resolve(identity(sub="s"))
    assert current.ordered_roles == ["admin", "instructor", "learner"]
    assert current.default_role == "admin"
