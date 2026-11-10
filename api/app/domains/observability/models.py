"""Modelo de solo lectura de `llm_call_logs` (la escribe `ai/`; la API solo la consulta)."""

from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel


class LlmCallLogModel(TableModel):
    __tablename__ = "llm_call_logs"

    ai_job_id: Mapped[int | None] = mapped_column(BigInteger)
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str | None] = mapped_column(String(50))
    task: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_id: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    json_valid: Mapped[bool | None] = mapped_column(Boolean)
    call_attempt: Mapped[int] = mapped_column(SmallInteger)
    from_cache: Mapped[bool] = mapped_column(Boolean)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
