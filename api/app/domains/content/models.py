"""Modelo SQLAlchemy de la tabla resources de Liquibase."""

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel


class ResourceModel(TableModel):
    __tablename__ = "resources"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    resource_type: Mapped[str] = mapped_column(String(10))
    url: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[Any] | None] = mapped_column(JSONB)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
