"""Contratos HTTP de contenido."""

from typing import Any, Self

from pydantic import Field, model_validator

from app.common.constants import ResourceType
from app.common.schemas import RequestSchema, ResponseSchema


class ResourceCreate(RequestSchema):
    topic_id: int = Field(gt=0)
    resource_type: ResourceType
    url: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    sources: list[Any] | None = None
    prompt_version: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def needs_url_or_content(self) -> Self:
        if self.url is None and self.content is None:
            raise ValueError("a resource needs a url or a content")
        return self


class ResourceUpdate(RequestSchema):
    url: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    sources: list[Any] | None = None
    prompt_version: str | None = Field(default=None, max_length=50)


class ResourceResponse(ResponseSchema):
    topic_id: int
    resource_type: str
    url: str | None
    content: str | None
    sources: list[Any] | None
    prompt_version: str | None
