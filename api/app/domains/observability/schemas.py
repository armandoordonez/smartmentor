"""Contratos HTTP del log de llamadas al LLM."""

from pydantic import Field

from app.common.constants import LlmCallStatus
from app.common.schemas import RequestSchema, ResponseSchema


class LlmCallLogCreate(RequestSchema):
    task: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    enrollment_id: int | None = Field(default=None, gt=0)
    prompt_version: str | None = Field(default=None, max_length=50)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    status: LlmCallStatus = LlmCallStatus.SUCCESS
    error_message: str | None = None


class LlmCallLogUpdate(RequestSchema):
    """Solo se corrigen el resultado y el mensaje de error; el resto es un hecho registrado."""

    status: LlmCallStatus | None = None
    error_message: str | None = None


class LlmCallLogResponse(ResponseSchema):
    enrollment_id: int | None
    task: str
    model: str
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    status: str
    error_message: str | None
