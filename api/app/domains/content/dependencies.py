"""Composición: construye el servicio de recursos con su repositorio SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.content.repository_impl import SqlAlchemyResourceRepository
from app.domains.content.service import ResourceService


def get_resource_service(session: SessionDep) -> ResourceService:
    return ResourceService(SqlAlchemyResourceRepository(session), SqlAlchemyUnitOfWork(session))
