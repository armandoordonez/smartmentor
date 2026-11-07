"""``LlmProvider`` port (plan 5.4.6, ADR 0011).

``generate_structured(request) -> LlmResponse``: the request carries the rendered prompt, the
``...LLM`` JSON Schema (structured output), the model and the temperature; the response is the
raw JSON text plus token usage. The provider SDK lives only inside its adapter. Validation,
retries, cache, budget and logging belong to ``application/llm_runner.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class LlmRequest:
    prompt_id: str
    prompt_version: int
    system: str
    user: str
    schema_name: str
    schema: dict[str, Any] = field(repr=False)
    model: str
    temperature: float


@dataclass(frozen=True)
class LlmResponse:
    text: str
    usage: LlmUsage
    model: str


class LlmProviderError(Exception):
    """Provider failure (5xx, network, quota): retried, then ``LLM_PROVIDER_ERROR``."""


class LlmTimeoutError(LlmProviderError):
    """No answer in time: ``LLM_PROVIDER_TIMEOUT``."""


class LlmContentBlockedError(LlmProviderError):
    """The provider's filters blocked the answer: ``LLM_CONTENT_BLOCKED`` (not retried)."""


class LlmProvider(Protocol):
    @property
    def name(self) -> str:
        """Provider id stored in ``llm_call_logs.provider`` (gemini, anthropic, fake)."""
        ...

    async def generate_structured(self, request: LlmRequest) -> LlmResponse: ...
