"""Entidades del dominio de observabilidad (Python puro)."""

from dataclasses import dataclass

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class LlmCallLog(BaseEntity):
    task: str
    model: str
    enrollment_id: int | None = None
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    status: str = "success"
    error_message: str | None = None
