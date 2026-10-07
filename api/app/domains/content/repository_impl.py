"""Repositorio SQLAlchemy de recursos."""

from typing import ClassVar

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.content.entities import Resource
from app.domains.content.models import ResourceModel


class SqlAlchemyResourceRepository(SqlAlchemyCrudRepository[ResourceModel, Resource]):
    model = ResourceModel
    entity = Resource
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "resources_topic_id_fk": ("TOPIC_NOT_FOUND", "The topic does not exist."),
        "resources_type_ck": ("INVALID_RESOURCE_TYPE", "resource_type must be video or text."),
        "resources_url_or_content_ck": (
            "RESOURCE_EMPTY",
            "A resource needs a url or a content.",
        ),
    }
