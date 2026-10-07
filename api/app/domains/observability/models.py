"""Modelo SQLAlchemy de la tabla llm_call_logs de Liquibase."""

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel


class LlmCallLogModel(TableModel):
    __tablename__ = "llm_call_logs"

    enrollment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    task: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), server_default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
