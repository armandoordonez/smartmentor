"""Interfaz (puerto) del repositorio de recursos."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.content.entities import Resource


class ResourceRepository(CrudRepository[Resource], Protocol): ...
