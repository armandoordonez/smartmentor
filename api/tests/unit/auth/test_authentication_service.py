import pytest

from app.common.exceptions import ForbiddenError
from app.domains.identity.authentication import AuthenticationService, ExternalIdentity
from app.domains.identity.entities import Role, User, UserRole
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository


class InMemoryUsers(InMemoryRepository[User]):
    def __init__(
        self,
        items: list[User],
        user_roles: InMemoryRepository[UserRole],
        roles: InMemoryRepository[Role],
    ):
        super().__init__(items)
        self._user_roles = user_roles
        self._roles = roles

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
        return frozenset(r.code for r in self._roles.items.values() if r.id in role_ids)


class InMemoryRoles(InMemoryRepository[Role]):
    async def get_by_code(self, code: str) -> Role | None:
        return next((r for r in self.items.values() if r.code == code), None)


def make_service(users: list[User]) -> tuple[AuthenticationService, InMemoryUsers, FakeUnitOfWork]:
    roles = InMemoryRoles(
        [
            Role(id=1, code="admin", name="A"),
            Role(id=2, code="teacher", name="T"),
            Role(id=3, code="student", name="S"),
        ]
    )
    user_roles = InMemoryRepository[UserRole](
        [UserRole(user_id=10, role_id=2)]
    )  # el usuario 10 es docente
    repo = InMemoryUsers(users, user_roles, roles)
    uow = FakeUnitOfWork()
    service = AuthenticationService(repo, roles, user_roles, uow, provider="keycloak")
    return service, repo, uow


def identity(
    sub: str = "sub-1", email: str | None = "ana@example.com", verified: bool = True
) -> ExternalIdentity:
    return ExternalIdentity(
        subject=sub, email=email, email_verified=verified, full_name="Ana Pérez"
    )


async def test_unknown_verified_user_is_created_as_student() -> None:
    service, repo, uow = make_service([])
    current = await service.resolve(identity())
    assert current.roles == frozenset({"student"})
    assert current.email == "ana@example.com"
    created = await repo.get_by_identity("keycloak", "sub-1")
    assert created is not None
    assert created.full_name == "Ana Pérez"
    assert uow.commits == 1


async def test_full_name_falls_back_to_the_email_local_part() -> None:
    service, repo, _ = make_service([])
    await service.resolve(ExternalIdentity("sub-1", "ana.perez@example.com", True, None))
    assert (await repo.get_by_identity("keycloak", "sub-1")).full_name == "ana.perez"  # type: ignore[union-attr]


async def test_returning_user_is_found_by_subject_without_writes() -> None:
    linked = User(
        id=10,
        full_name="Doc",
        email="doc@example.com",
        identity_provider="keycloak",
        identity_subject="sub-9",
    )
    service, _, uow = make_service([linked])
    current = await service.resolve(identity(sub="sub-9", email="otro-correo@example.com"))
    assert current.id == 10
    assert current.roles == frozenset({"teacher"})
    assert uow.commits == 0


async def test_existing_user_is_linked_by_verified_email_and_keeps_its_roles() -> None:
    precreated = User(id=10, full_name="Doc", email="Doc@Example.com")
    service, repo, uow = make_service([precreated])
    current = await service.resolve(identity(sub="sub-7", email="doc@example.com"))
    assert current.id == 10
    assert current.roles == frozenset({"teacher"})  # no se agrega student
    assert (await repo.get(10)).identity_subject == "sub-7"  # type: ignore[union-attr]
    assert uow.commits == 1


async def test_unverified_email_never_creates_or_links() -> None:
    service, repo, uow = make_service([User(id=10, full_name="Doc", email="ana@example.com")])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(verified=False))
    assert error.value.code == "EMAIL_NOT_VERIFIED"
    assert (await repo.get(10)).identity_subject is None  # type: ignore[union-attr]
    assert uow.commits == 0


async def test_token_without_email_is_rejected() -> None:
    service, _, _ = make_service([])
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
    service, _, _ = make_service([owner])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(sub="intruso"))
    assert error.value.code == "IDENTITY_CONFLICT"


async def test_deactivated_user_cannot_log_in() -> None:
    off = User(
        id=10,
        full_name="Doc",
        email="doc@example.com",
        identity_provider="keycloak",
        identity_subject="sub-9",
        active=False,
    )
    service, _, _ = make_service([off])
    with pytest.raises(ForbiddenError) as error:
        await service.resolve(identity(sub="sub-9"))
    assert error.value.code == "ACCOUNT_DEACTIVATED"
