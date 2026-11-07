"""CU-14 ampliado: el administrador asigna o quita roles y nunca deja la plataforma sin admin."""

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.domains.identity.entities import Role, User, UserRole
from app.domains.identity.service import (
    UserRolesAdminService,
    UserRoleService,
    UserService,
)
from tests.unit.fakes import FakeUnitOfWork, InMemoryRoles, InMemoryUserRoles, InMemoryUsers


class RecordingSync:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self._fail = fail

    async def sync_roles(self, identity_subject: str, roles: list[str]) -> None:
        if self._fail:
            raise RuntimeError("Keycloak no responde")
        self.calls.append((identity_subject, roles))


def build(
    sync: RecordingSync | None = None,
) -> tuple[UserRolesAdminService, UserRoleService, UserService, InMemoryUsers, InMemoryUserRoles]:
    roles = InMemoryRoles(
        [
            Role(id=1, code="admin", name="Administrador"),
            Role(id=2, code="instructor", name="Instructor"),
            Role(id=3, code="learner", name="Aprendiz"),
        ]
    )
    user_roles = InMemoryUserRoles(
        [
            UserRole(user_id=1, role_id=1),  # único administrador
            UserRole(user_id=2, role_id=3),
            UserRole(user_id=3, role_id=1),
            UserRole(user_id=3, role_id=3),
        ]
    )
    users = InMemoryUsers(
        [
            User(
                id=1,
                full_name="Admin",
                email="a@example.org",
                identity_provider="keycloak",
                identity_subject="s1",
            ),
            User(
                id=2,
                full_name="Learner",
                email="l@example.org",
                identity_provider="keycloak",
                identity_subject="s2",
            ),
            User(id=3, full_name="Segundo", email="s@example.org"),
        ],
        user_roles,
        roles,
    )
    uow = FakeUnitOfWork()
    return (
        UserRolesAdminService(users, roles, user_roles, uow, sync),
        UserRoleService(user_roles, users, roles, uow),
        UserService(users, uow),
        users,
        user_roles,
    )


async def test_roles_can_be_replaced_and_a_user_may_have_several() -> None:
    admin_service, _, _, users, _ = build()
    result = await admin_service.set_roles(2, ["instructor", "learner"])
    assert result == ["instructor", "learner"]
    assert await users.get_role_codes(2) == frozenset({"instructor", "learner"})


async def test_removed_roles_are_deactivated_not_deleted() -> None:
    admin_service, _, _, users, user_roles = build()
    await admin_service.set_roles(2, ["instructor"])
    assert await users.get_role_codes(2) == frozenset({"instructor"})
    learner_row = next(
        ur for ur in user_roles.items.values() if ur.user_id == 2 and ur.role_id == 3
    )
    assert learner_row.active is False  # el cambio queda en la auditoría de la fila


async def test_a_deactivated_role_can_be_assigned_again() -> None:
    admin_service, _, _, users, _ = build()
    await admin_service.set_roles(2, ["instructor"])
    await admin_service.set_roles(2, ["learner"])
    assert await users.get_role_codes(2) == frozenset({"learner"})


async def test_unknown_role_is_404_and_changes_nothing() -> None:
    admin_service, _, _, users, _ = build()
    with pytest.raises(NotFoundError) as error:
        await admin_service.set_roles(2, ["learner", "evaluator"])
    assert error.value.code == "ROLE_NOT_FOUND"
    assert await users.get_role_codes(2) == frozenset({"learner"})


async def test_unknown_user_is_404() -> None:
    admin_service, _, _, _, _ = build()
    with pytest.raises(NotFoundError) as error:
        await admin_service.set_roles(99, ["learner"])
    assert error.value.code == "USER_NOT_FOUND"


async def test_the_last_administrator_cannot_lose_the_role() -> None:
    admin_service, _, _, users, _ = build()
    # El usuario 3 también es admin: se puede quitar a uno...
    await admin_service.set_roles(3, ["learner"])
    # ...pero no al último.
    with pytest.raises(ConflictError) as error:
        await admin_service.set_roles(1, ["instructor"])
    assert error.value.code == "LAST_ADMIN"
    assert "admin" in await users.get_role_codes(1)


async def test_the_admin_check_takes_the_membership_lock() -> None:
    admin_service, _, _, users, _ = build()
    await admin_service.set_roles(3, ["learner"])
    assert users.locks == 1


async def test_the_last_administrator_cannot_be_deactivated() -> None:
    _, _, user_service, _, _ = build()
    await user_service.deactivate(3)  # hay otro administrador
    with pytest.raises(ConflictError) as error:
        await user_service.deactivate(1)
    assert error.value.code == "LAST_ADMIN"


async def test_deactivating_the_admin_assignment_of_the_last_admin_is_blocked() -> None:
    _, user_role_service, _, _, user_roles = build()
    admin_row = next(ur for ur in user_roles.items.values() if ur.user_id == 1 and ur.role_id == 1)
    other_row = next(ur for ur in user_roles.items.values() if ur.user_id == 3 and ur.role_id == 1)
    await user_role_service.deactivate(other_row.id or 0)
    with pytest.raises(ConflictError) as error:
        await user_role_service.deactivate(admin_row.id or 0)
    assert error.value.code == "LAST_ADMIN"


async def test_assigning_a_role_twice_is_a_conflict() -> None:
    _, user_role_service, _, _, _ = build()
    with pytest.raises(ConflictError) as error:
        await user_role_service.create(UserRole(user_id=2, role_id=3))
    assert error.value.code == "ROLE_ALREADY_ASSIGNED"


async def test_creating_the_assignment_of_an_inactive_one_reactivates_it() -> None:
    admin_service, user_role_service, _, users, _ = build()
    await admin_service.set_roles(2, ["instructor"])
    await user_role_service.create(UserRole(user_id=2, role_id=3))
    assert await users.get_role_codes(2) == frozenset({"instructor", "learner"})


async def test_the_roles_are_mirrored_in_the_identity_provider() -> None:
    sync = RecordingSync()
    admin_service, _, _, _, _ = build(sync)
    await admin_service.set_roles(2, ["instructor", "learner"])
    assert sync.calls == [("s2", ["instructor", "learner"])]


async def test_a_failing_identity_provider_does_not_undo_the_change() -> None:
    admin_service, _, _, users, _ = build(RecordingSync(fail=True))
    await admin_service.set_roles(2, ["instructor"])
    assert await users.get_role_codes(2) == frozenset({"instructor"})
