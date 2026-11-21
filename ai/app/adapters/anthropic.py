"""``AnthropicProvider``: interface of the alternative provider (ADR 0011).

Phase 4 delivers only the interface: Gemini is the default provider and the ``anthropic`` SDK
is not a dependency yet. When the owner enables it (``AI_LLM_PROVIDER=anthropic``), this adapter
will request structured output through a forced tool whose ``input_schema`` is the ``...LLM``
schema, and map usage (``input_tokens``, ``output_tokens``) and errors the same way as
``GeminiProvider``. Until then every call fails with ``LlmProviderError`` and ``/ready`` reports
the provider as not available.
"""

from __future__ import annotations

from app.ports.llm import LlmProviderError, LlmRequest, LlmResponse

NOT_AVAILABLE = "anthropic provider is not implemented yet (Phase 4 ships the interface only)"


class AnthropicProvider:
    available = False

    def __init__(self, api_key: str, *, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "anthropic"

    async def generate_structured(self, request: LlmRequest) -> LlmResponse:
        del request
        raise LlmProviderError(NOT_AVAILABLE)
