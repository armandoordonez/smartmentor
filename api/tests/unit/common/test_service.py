import pytest

from app.common.exceptions import NotFoundError
from app.common.service import CrudService
from app.domains.identity.entities import Role
from tests.unit.fakes import FakeUnitOfWork, InMemoryRepository


def make_service() -> tuple[CrudService[Role], FakeUnitOfWork, InMemoryRepository[Role]]:
    repository = InMemoryRepository[Role]()
    uow = FakeUnitOfWork()
    return CrudService(repository, uow), uow, repository


async def test_create_commits_once() -> None:
    service, uow, _ = make_service()
    created = await service.create(Role(code="admin", name="Admin"))
    assert created.id == 1
    assert uow.commits == 1


async def test_get_missing_raises_not_found() -> None:
    service, _, _ = make_service()
    with pytest.raises(NotFoundError):
        await service.get(99)


async def test_update_without_changes_does_not_commit() -> None:
    service, uow, _ = make_service()
    created = await service.create(Role(code="admin", name="Admin"))
    await service.update(created.id or 0, {})
    assert uow.commits == 1


async def test_deactivate_is_logical_and_reversible() -> None:
    service, _, repository = make_service()
    created = await service.create(Role(code="admin", name="Admin"))
    off = await service.deactivate(created.id or 0)
    assert off.active is False
    assert created.id in repository.items  # el registro no se borra
    on = await service.activate(created.id or 0)
    assert on.active is True


async def test_search_ignores_empty_filters() -> None:
    service, _, _ = make_service()
    await service.create(Role(code="admin", name="Admin"))
    await service.create(Role(code="teacher", name="Teacher"))
    items, total = await service.search(filters={"code": None}, active=True, limit=10, offset=0)
    assert total == 2
    assert len(items) == 2
    only_teacher, total = await service.search(
        filters={"code": "teacher"}, active=True, limit=10, offset=0
    )
    assert total == 1
    assert only_teacher[0].code == "teacher"
