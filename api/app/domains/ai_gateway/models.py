"""Modelo de `ai_jobs`: la cola que escribe `ai/`. La API solo la LEE (ADR 0009 y 0019).

`smartmentor_api` tiene permiso de lectura sobre esta tabla y ninguno de escritura. El `public_id`
es el `job_id` UUID del contrato de `ai/`; el `id` interno lo usan las claves foráneas
(`syllabus_extractions.ai_job_id`).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import PublicTableModel


class AiJobModel(PublicTableModel):
    __tablename__ = "ai_jobs"

    job_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer)
    requested_by: Mapped[str | None] = mapped_column(String(20))
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_id: Mapped[int | None] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
