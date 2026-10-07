"""Casos de uso de recursos (video y texto de cada tema)."""

from app.common.service import CrudService
from app.domains.content.entities import Resource


class ResourceService(CrudService[Resource]):
    resource_name = "Resource"
