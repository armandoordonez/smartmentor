"""Composition root: builds adapters and services from the settings.

The HTTP app and the worker share it. Tests build a ``Container`` with in-memory adapters and
the fake providers through ``build_container(..., overrides)``.

Phase 5 job types (content, items, grading, video, badge) register their handlers in
``build_handlers``; nothing else needs to change.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.anthropic import AnthropicProvider
from app.adapters.budget import BudgetLimits, CallLogBudgetGuard
from app.adapters.fake_embedding import FakeEmbeddingProvider
from app.adapters.fake_llm import FakeLlmProvider
from app.adapters.gemini import GeminiEmbeddingProvider, GeminiProvider
from app.adapters.memory import (
    InMemoryCallLogRepository,
    InMemoryCatalogReader,
    InMemoryGenerationCache,
    InMemoryJobRepository,
)
from app.adapters.prompt_files import FilePromptStore
from app.application.content.registry import ContentServices, build_job_handlers
from app.application.content.wiring import build_content_for_container
from app.application.diagnostic import (
    DiagnosticFinalizeHandler,
    DiagnosticGenerateHandler,
    LevelEstimator,
)
from app.application.items import ItemsReviewHandler
from app.application.jobs import JobHandler, JobService
from app.application.llm_runner import EmbeddingRunner, LlmRunner, ModelConfig
from app.application.pricing import PriceTable
from app.application.syllabus import SyllabusStructureHandler
from app.core.config import Settings
from app.core.security import ServiceTokenValidator
from app.ports.budget import BudgetGuard
from app.ports.cache import GenerationCache
from app.ports.call_logs import LlmCallLogRepository
from app.ports.catalog import CatalogReader
from app.ports.embedding import EmbeddingProvider, EmbeddingPurpose, EmbeddingResult
from app.ports.jobs import JobRepository
from app.ports.llm import LlmProvider, LlmProviderError, LlmRequest, LlmResponse
from app.ports.prompts import PromptStore
from app.worker.loop import WorkerConfig

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class UnconfiguredLlmProvider:
    """Stands in while ``AI_LLM_PROVIDER`` is missing: every call fails (``/ready`` says why)."""

    @property
    def name(self) -> str:
        return "unconfigured"

    async def generate_structured(self, request: LlmRequest) -> LlmResponse:
        del request
        raise LlmProviderError("AI_LLM_PROVIDER is not configured")


class UnconfiguredEmbeddingProvider:
    @property
    def name(self) -> str:
        return "unconfigured"

    @property
    def model(self) -> str:
        return ""

    @property
    def dimension(self) -> int:
        return 0

    async def embed(self, texts: Sequence[str], purpose: EmbeddingPurpose) -> EmbeddingResult:
        del texts, purpose
        raise LlmProviderError("AI_EMBEDDING_PROVIDER is not configured")


@dataclass
class Container:
    settings: Settings
    clock: Clock
    prompts: PromptStore
    prices: PriceTable
    llm: LlmProvider
    embeddings: EmbeddingProvider
    jobs: JobRepository
    call_logs: LlmCallLogRepository
    cache: GenerationCache
    catalog: CatalogReader
    budget: BudgetGuard
    runner: LlmRunner
    embedding_runner: EmbeddingRunner
    level_estimator: LevelEstimator
    job_service: JobService
    content: ContentServices
    worker_config: WorkerConfig
    token_validator: ServiceTokenValidator | None
    database_ping: Callable[[], Awaitable[None]] | None = None
    engine: AsyncEngine | None = None
    notes: list[str] = field(default_factory=list)

    async def readiness(self) -> list[str]:
        """What is missing for ``/ready`` (empty = ready)."""
        missing = [f"env:{name}" for name in self.settings.missing_configuration()]
        if self.database_ping is None:
            missing.append("database:not configured (AI_DATABASE_USER, AI_DATABASE_PASSWORD)")
        else:
            try:
                await self.database_ping()
            except Exception as exc:  # any driver error means "not ready"
                missing.append(f"database:{exc.__class__.__name__}")
        missing += [f"prompts:{issue}" for issue in self.prompts.verify()]
        missing += [f"prices:{issue}" for issue in self.prices.issues]
        if self.settings.uses_real_llm:
            missing += [
                f"prices:model {model} has no price in config/prices.yaml"
                for model in self.prices.missing(self.settings.configured_models())
            ]
        missing += self.notes
        return missing

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()


def build_llm(settings: Settings, examples_dir: Any) -> tuple[LlmProvider, list[str]]:
    provider = settings.ai_llm_provider
    if provider == "fake":
        return FakeLlmProvider(examples_dir), []
    if provider == "gemini" and settings.gemini_api_key is not None:
        key = settings.gemini_api_key.get_secret_value()
        return GeminiProvider.from_api_key(key, timeout_seconds=settings.ai_llm_timeout_seconds), []
    if provider == "anthropic" and settings.anthropic_api_key is not None:
        anthropic = AnthropicProvider(
            settings.anthropic_api_key.get_secret_value(),
            timeout_seconds=settings.ai_llm_timeout_seconds,
        )
        return anthropic, ["provider:anthropic adapter is not implemented yet (interface only)"]
    return UnconfiguredLlmProvider(), []


def build_embeddings(settings: Settings) -> EmbeddingProvider:
    model, dimension = settings.ai_embedding_model, settings.embedding_dimension
    if model is None or dimension is None:
        return UnconfiguredEmbeddingProvider()
    if settings.ai_embedding_provider == "fake":
        return FakeEmbeddingProvider(model, dimension)
    if settings.ai_embedding_provider == "gemini" and settings.gemini_api_key is not None:
        return GeminiEmbeddingProvider.from_api_key(
            settings.gemini_api_key.get_secret_value(),
            model=model,
            dimension=dimension,
            timeout_seconds=settings.ai_llm_timeout_seconds,
        )
    return UnconfiguredEmbeddingProvider()


def build_handlers(
    runner: LlmRunner,
    catalog: CatalogReader,
    estimator: LevelEstimator,
    content: ContentServices | None = None,
) -> dict[str, JobHandler[Any]]:
    handlers: list[JobHandler[Any]] = [
        SyllabusStructureHandler(runner, catalog),
        DiagnosticGenerateHandler(runner, catalog),
        ItemsReviewHandler(runner),
        DiagnosticFinalizeHandler(runner, estimator),
        *(build_job_handlers(content) if content is not None else []),
    ]
    return {h.job_type: h for h in handlers}


@dataclass
class Overrides:
    """Replace adapters (tests). ``None`` keeps what the settings would build."""

    clock: Clock | None = None
    llm: LlmProvider | None = None
    embeddings: EmbeddingProvider | None = None
    jobs: JobRepository | None = None
    call_logs: LlmCallLogRepository | None = None
    cache: GenerationCache | None = None
    catalog: CatalogReader | None = None
    prices: PriceTable | None = None
    token_validator: ServiceTokenValidator | None = None
    database_ping: Callable[[], Awaitable[None]] | None = None
    provider_backoff_seconds: float | None = None


def build_container(settings: Settings, overrides: Overrides | None = None) -> Container:
    o = overrides or Overrides()
    clock = o.clock or utc_now
    prompts = FilePromptStore(settings.ai_prompts_dir)
    prices = o.prices or PriceTable.load(settings.ai_prices_file)
    notes: list[str] = []
    if o.llm is not None:
        llm: LlmProvider = o.llm
    else:
        llm, notes = build_llm(settings, settings.ai_prompts_dir / "examples" / "llm")
    embeddings = o.embeddings or build_embeddings(settings)

    engine: AsyncEngine | None = None
    database_ping = o.database_ping
    persistence_overridden = o.jobs is not None and o.call_logs is not None
    if settings.database_configured and not persistence_overridden:
        from app.adapters.postgres.cache import PostgresGenerationCache
        from app.adapters.postgres.call_logs import PostgresCallLogRepository
        from app.adapters.postgres.catalog import PostgresCatalogReader, ping
        from app.adapters.postgres.jobs import PostgresJobRepository
        from app.core.database import create_engine

        engine = create_engine(settings)
        db_engine = engine
        jobs: JobRepository = PostgresJobRepository(engine)
        call_logs: LlmCallLogRepository = PostgresCallLogRepository(engine)
        cache: GenerationCache = o.cache or PostgresGenerationCache(engine)
        catalog: CatalogReader = o.catalog or PostgresCatalogReader(engine)

        async def _ping() -> None:
            await ping(db_engine)

        database_ping = database_ping or _ping
    else:
        jobs = o.jobs or InMemoryJobRepository()
        call_logs = o.call_logs or InMemoryCallLogRepository()
        cache = o.cache or InMemoryGenerationCache()
        catalog = o.catalog or InMemoryCatalogReader()

    budget = CallLogBudgetGuard(
        BudgetLimits(
            daily_usd=settings.ai_daily_budget_usd,
            monthly_usd=settings.ai_monthly_budget_usd,
            course_usd=settings.ai_course_budget_usd,
            enrollment_usd=settings.ai_enrollment_budget_usd,
        ),
        call_logs,
        settings.app_timezone,
    )
    models = ModelConfig(
        provider_is_real=settings.uses_real_llm,
        default_model=settings.ai_llm_model_default or "",
        small_model=settings.ai_llm_model_small or "",
    )
    backoff = 2.0 if o.provider_backoff_seconds is None else o.provider_backoff_seconds
    runner = LlmRunner(
        provider=llm,
        prompts=prompts,
        models=models,
        prices=prices,
        cache=cache,
        call_logs=call_logs,
        budget=budget,
        clock=clock,
        provider_backoff_seconds=backoff,
    )
    embedding_runner = EmbeddingRunner(
        provider=embeddings,
        prices=prices,
        provider_is_real=settings.ai_embedding_provider == "gemini",
        call_logs=call_logs,
        budget=budget,
        clock=clock,
    )
    estimator = LevelEstimator(embedding_runner, catalog)
    content = build_content_for_container(
        runner=runner,
        embedding_runner=embedding_runner,
        catalog=catalog,
        jobs=jobs,
        clock=clock,
        engine=engine,
    )
    job_service = JobService(
        jobs=jobs,
        call_logs=call_logs,
        handlers=build_handlers(runner, catalog, estimator, content),
        clock=clock,
    )
    token_validator = o.token_validator
    if token_validator is None and settings.oidc_issuer_url and settings.oidc_jwks_url:
        token_validator = ServiceTokenValidator.from_urls(
            issuer=settings.oidc_issuer_url,
            jwks_url=settings.oidc_jwks_url,
            audience=settings.ai_service_audience,
        )
    return Container(
        settings=settings,
        clock=clock,
        prompts=prompts,
        prices=prices,
        llm=llm,
        embeddings=embeddings,
        jobs=jobs,
        call_logs=call_logs,
        cache=cache,
        catalog=catalog,
        budget=budget,
        runner=runner,
        embedding_runner=embedding_runner,
        level_estimator=estimator,
        job_service=job_service,
        content=content,
        worker_config=WorkerConfig(
            lease_seconds=settings.ai_job_lock_seconds,
            max_attempts=settings.ai_job_max_attempts,
            backoff_seconds=settings.ai_job_retry_backoff_seconds,
            poll_seconds=settings.ai_worker_poll_seconds,
        ),
        token_validator=token_validator,
        database_ping=database_ping,
        engine=engine,
        notes=notes,
    )
