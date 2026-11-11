"""Structured LLM calls with validation, retries, cache, budget and logging (plan 5.4.4, 5.4.11).

Pipeline of ``LlmRunner.run``::

    prompt (PromptStore) -> cache lookup (SHA-256) -> price check -> [budget check ->
    provider (transient errors retried) -> model_validate_json -> code checks] x (1 + 2 retries
    with the issues fed back) -> cache store

Every provider attempt, cache hit and budget refusal leaves one ``llm_call_logs`` row. Failures
end the job with a catalogued ``TaskError`` code.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.application.pricing import PriceTable
from app.domain.contracts.common import Meta
from app.domain.errors import BudgetExceededError, TaskError
from app.ports.budget import BudgetGuard, BudgetScope
from app.ports.cache import CachedGeneration, GenerationCache, cache_key
from app.ports.call_logs import CallStatus, LlmCallLog, LlmCallLogRepository
from app.ports.embedding import EmbeddingProvider, EmbeddingPurpose
from app.ports.llm import (
    LlmContentBlockedError,
    LlmProvider,
    LlmProviderError,
    LlmQuotaError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
)
from app.ports.prompts import ModelTier, PromptStore, PromptTemplate

logger = logging.getLogger("app.llm")

MAX_VALIDATION_RETRIES = 2
MAX_ISSUES_FED_BACK = 12
MAX_ERROR_MESSAGE = 500


@dataclass(frozen=True)
class CallContext:
    """Who pays and where the call is logged: the job (if any) and its budget scope."""

    task: str
    job_id: UUID | None = None
    scope: BudgetScope = field(default_factory=BudgetScope)


@dataclass(frozen=True)
class ModelConfig:
    provider_is_real: bool
    default_model: str
    small_model: str

    def model_for(self, tier: ModelTier) -> str:
        return self.small_model if tier == "small" else self.default_model


def schema_issues(error: ValidationError) -> list[str]:
    """Short, value-free description of schema errors (fed back to the model)."""
    return [
        f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
        for e in error.errors(include_url=False, include_input=False)
    ]


def retry_feedback(issues: Sequence[str]) -> str:
    listed = "\n".join(f"- {i}" for i in issues[:MAX_ISSUES_FED_BACK])
    return (
        "\n\nTu respuesta anterior no cumplió el esquema o las reglas. Problemas encontrados:\n"
        f"{listed}\nDevuelve solo JSON válido que cumpla el esquema y todas las reglas."
    )


class LlmRunner:
    def __init__(
        self,
        *,
        provider: LlmProvider,
        prompts: PromptStore,
        models: ModelConfig,
        prices: PriceTable,
        cache: GenerationCache,
        call_logs: LlmCallLogRepository,
        budget: BudgetGuard,
        clock: Callable[[], datetime],
        provider_retries: int = 2,
        provider_backoff_seconds: float = 2.0,
    ) -> None:
        self._provider = provider
        self._prompts = prompts
        self._models = models
        self._prices = prices
        self._cache = cache
        self._logs = call_logs
        self._budget = budget
        self._clock = clock
        self._provider_retries = provider_retries
        self._backoff = provider_backoff_seconds

    @property
    def prompts(self) -> PromptStore:
        return self._prompts

    def model_for(self, template: PromptTemplate) -> str:
        return self._models.model_for(template.model_tier)

    # ---------- helpers ----------

    def _cost(self, model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
        cost = self._prices.cost(model, input_tokens, output_tokens)
        if cost is None and not self._models.provider_is_real:
            return Decimal(0)  # the fake provider is free even without a price
        return cost

    async def _log(
        self,
        ctx: CallContext,
        *,
        provider: str,
        model: str,
        template: PromptTemplate | None,
        key: str | None,
        attempt: int,
        status: CallStatus,
        json_valid: bool | None,
        started: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        from_cache: bool = False,
        error: str | None = None,
    ) -> None:
        cost = Decimal(0) if from_cache or status == "budget_exceeded" else None
        if cost is None:
            cost = self._cost(model, input_tokens, output_tokens)
        latency = int((time.perf_counter() - started) * 1000)
        await self._logs.add(
            LlmCallLog(
                provider=provider,
                model=model,
                task=ctx.task,
                prompt_id=template.id if template else None,
                prompt_version=template.version_label if template else None,
                input_sha256=key,
                call_attempt=attempt,
                from_cache=from_cache,
                status=status,
                json_valid=json_valid,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency,
                created_at=self._clock(),
                ai_job_id=ctx.job_id,
                course_id=ctx.scope.course_id,
                enrollment_id=ctx.scope.enrollment_id,
                error_message=error[:MAX_ERROR_MESSAGE] if error else None,
            )
        )
        logger.info(
            "llm call %s",
            status,
            extra={
                "task": ctx.task,
                "prompt_id": template.id if template else None,
                "model": model,
                "call_attempt": attempt,
                "latency_ms": latency,
            },
        )

    def _ensure_price(self, model: str) -> None:
        if self._models.provider_is_real and self._prices.get(model) is None:
            raise TaskError(
                "PRICE_NOT_CONFIGURED", f"model {model} has no price in config/prices.yaml"
            )

    async def _ensure_budget(
        self,
        ctx: CallContext,
        *,
        provider: str,
        model: str,
        template: PromptTemplate | None,
        key: str | None,
        attempt: int,
    ) -> None:
        breach = await self._budget.check(ctx.scope, self._clock())
        if breach is None:
            return
        await self._log(
            ctx,
            provider=provider,
            model=model,
            template=template,
            key=key,
            attempt=attempt,
            status="budget_exceeded",
            json_valid=None,
            started=time.perf_counter(),
            error=breach.describe(),
        )
        logger.warning("budget exceeded: %s", breach.scope, extra={"code": "BUDGET_EXCEEDED"})
        raise BudgetExceededError(breach.describe())

    async def _call_provider(
        self,
        ctx: CallContext,
        request: LlmRequest,
        template: PromptTemplate,
        key: str,
        first_attempt: int,
    ) -> tuple[LlmResponse, int, float]:
        """Call with transient retries. Returns (response, attempt number, start time)."""
        attempt = first_attempt
        for provider_try in range(self._provider_retries + 1):
            await self._ensure_budget(
                ctx,
                provider=self._provider.name,
                model=request.model,
                template=template,
                key=key,
                attempt=attempt,
            )
            started = time.perf_counter()
            try:
                return await self._provider.generate_structured(request), attempt, started
            except LlmContentBlockedError as exc:
                await self._log_failure(ctx, request, template, key, attempt, started, exc)
                raise TaskError("LLM_CONTENT_BLOCKED", "the provider blocked the answer") from exc
            except LlmQuotaError as exc:
                await self._log_failure(ctx, request, template, key, attempt, started, exc)
                raise TaskError("LLM_QUOTA_EXHAUSTED", f"provider quota exhausted: {exc}") from exc
            except LlmProviderError as exc:
                await self._log_failure(ctx, request, template, key, attempt, started, exc)
                if provider_try == self._provider_retries:
                    code = (
                        "LLM_PROVIDER_TIMEOUT"
                        if isinstance(exc, LlmTimeoutError)
                        else "LLM_PROVIDER_ERROR"
                    )
                    raise TaskError(code, f"provider failed: {exc.__class__.__name__}") from exc
                attempt += 1
                await asyncio.sleep(self._backoff * (provider_try + 1))
        raise AssertionError("unreachable")  # pragma: no cover

    async def _log_failure(
        self,
        ctx: CallContext,
        request: LlmRequest,
        template: PromptTemplate,
        key: str,
        attempt: int,
        started: float,
        exc: Exception,
    ) -> None:
        await self._log(
            ctx,
            provider=self._provider.name,
            model=request.model,
            template=template,
            key=key,
            attempt=attempt,
            status="error",
            json_valid=None,
            started=started,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    # ---------- public API ----------

    async def run[M: BaseModel](
        self,
        prompt_id: str,
        variables: Mapping[str, Any],
        output_model: type[M],
        ctx: CallContext,
        *,
        check: Callable[[M], list[str]] | None = None,
        use_cache: bool = True,
    ) -> tuple[M, Meta]:
        """Return the validated ``...LLM`` output and its ``Meta``.

        Raises ``TaskError`` (``INVALID_OUTPUT``, ``BUDGET_EXCEEDED``, ``LLM_PROVIDER_*``,
        ``PRICE_NOT_CONFIGURED``).
        """
        template = self._prompts.get(prompt_id)
        model = self.model_for(template)
        if not model:
            # No default model in code (ADR 0011): /ready already reports it.
            raise TaskError("INTERNAL_ERROR", "AI_LLM_MODEL_DEFAULT or AI_LLM_MODEL_SMALL missing")
        prompt = template.render(variables)
        key = cache_key(
            model=model,
            task=template.id,
            prompt_version=template.version_label,
            system=template.system,
            prompt=prompt,
            schema_name=template.output_schema_name,
        )
        checker = check or (lambda _obj: [])

        if use_cache:
            hit = await self._from_cache(ctx, template, model, key, output_model, checker)
            if hit is not None:
                return hit

        self._ensure_price(model)
        contents = prompt
        attempt = 1
        issues: list[str] = []
        for _ in range(MAX_VALIDATION_RETRIES + 1):
            request = LlmRequest(
                prompt_id=template.id,
                prompt_version=template.version,
                system=template.system,
                user=contents,
                schema_name=template.output_schema_name,
                schema=template.output_schema,
                model=model,
                temperature=template.temperature,
            )
            response, attempt, started = await self._call_provider(
                ctx, request, template, key, attempt
            )
            json_valid = False
            parsed: M | None = None
            try:
                parsed = output_model.model_validate_json(response.text)
                json_valid = True
                issues = checker(parsed)
            except ValidationError as exc:
                issues = schema_issues(exc)
            await self._log(
                ctx,
                provider=self._provider.name,
                model=response.model,
                template=template,
                key=key,
                attempt=attempt,
                status="success" if not issues else "invalid_output",
                json_valid=json_valid,
                started=started,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                error="; ".join(issues) if issues else None,
            )
            if parsed is not None and not issues:
                now = self._clock()
                if use_cache:
                    await self._cache.put(
                        CachedGeneration(
                            cache_key=key,
                            task=template.id,
                            prompt_version=template.version_label,
                            model=model,
                            output=parsed.model_dump(mode="json"),
                            created_at=now,
                        )
                    )
                return parsed, self._meta(template, model, key, now, from_cache=False)
            contents = prompt + retry_feedback(issues)
            attempt += 1
        raise TaskError(
            "INVALID_OUTPUT",
            f"{template.id}: no valid output after {MAX_VALIDATION_RETRIES} retries: "
            + "; ".join(issues[:MAX_ISSUES_FED_BACK]),
        )

    async def _from_cache[M: BaseModel](
        self,
        ctx: CallContext,
        template: PromptTemplate,
        model: str,
        key: str,
        output_model: type[M],
        checker: Callable[[M], list[str]],
    ) -> tuple[M, Meta] | None:
        hit = await self._cache.get(key)
        if hit is None:
            return None
        try:
            parsed = output_model.model_validate(hit.output)
        except ValidationError:
            return None
        if checker(parsed):
            return None
        await self._log(
            ctx,
            provider=self._provider.name,
            model=model,
            template=template,
            key=key,
            attempt=1,
            status="success",
            json_valid=True,
            started=time.perf_counter(),
            from_cache=True,
        )
        return parsed, self._meta(template, model, key, hit.created_at, from_cache=True)

    @staticmethod
    def _meta(
        template: PromptTemplate, model: str, key: str, generated_at: datetime, *, from_cache: bool
    ) -> Meta:
        return Meta(
            prompt_id=template.id,
            prompt_version=template.version_label,
            model=model,
            generated_at=generated_at,
            input_sha256=key,
            from_cache=from_cache,
        )


class EmbeddingRunner:
    """Embeddings with budget check and one ``llm_call_logs`` row per call."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        prices: PriceTable,
        provider_is_real: bool,
        call_logs: LlmCallLogRepository,
        budget: BudgetGuard,
        clock: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._prices = prices
        self._real = provider_is_real
        self._logs = call_logs
        self._budget = budget
        self._clock = clock

    @property
    def model(self) -> str:
        return self._provider.model

    async def embed(
        self, texts: Sequence[str], purpose: EmbeddingPurpose, ctx: CallContext
    ) -> list[list[float]]:
        model = self._provider.model
        price = self._prices.get(model)
        if self._real and price is None:
            raise TaskError(
                "PRICE_NOT_CONFIGURED", f"model {model} has no price in config/prices.yaml"
            )
        breach = await self._budget.check(ctx.scope, self._clock())
        if breach is not None:
            await self._add(ctx, model, "budget_exceeded", 0, 0, Decimal(0), breach.describe())
            raise BudgetExceededError(breach.describe())
        started = time.perf_counter()
        try:
            result = await self._provider.embed(texts, purpose)
        except LlmProviderError as exc:
            latency = int((time.perf_counter() - started) * 1000)
            error = f"{exc.__class__.__name__}: {exc}"
            await self._add(ctx, model, "error", latency, 0, None, error)
            if isinstance(exc, LlmQuotaError):
                code = "LLM_QUOTA_EXHAUSTED"
            elif isinstance(exc, LlmTimeoutError):
                code = "LLM_PROVIDER_TIMEOUT"
            else:
                code = "LLM_PROVIDER_ERROR"
            raise TaskError(code, f"embedding provider failed: {exc.__class__.__name__}") from exc
        latency = int((time.perf_counter() - started) * 1000)
        cost = price.cost(result.input_tokens, 0) if price else Decimal(0)
        await self._add(ctx, model, "success", latency, result.input_tokens, cost, None)
        return result.vectors

    async def _add(
        self,
        ctx: CallContext,
        model: str,
        status: CallStatus,
        latency: int,
        tokens: int,
        cost: Decimal | None,
        error: str | None,
    ) -> None:
        await self._logs.add(
            LlmCallLog(
                provider=self._provider.name,
                model=model,
                task=ctx.task,
                prompt_id=None,
                prompt_version=None,
                input_sha256=None,
                call_attempt=1,
                from_cache=False,
                status=status,
                json_valid=None,
                input_tokens=tokens,
                output_tokens=0,
                cost_usd=cost,
                latency_ms=latency,
                created_at=self._clock(),
                ai_job_id=ctx.job_id,
                course_id=ctx.scope.course_id,
                enrollment_id=ctx.scope.enrollment_id,
                error_message=error,
            )
        )
