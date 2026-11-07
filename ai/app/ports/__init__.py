"""Ports (interfaces) of the AI service (plan 5.4.1, ADR 0008).

Application code depends on these protocols only; adapters (``app/adapters``) implement them.
"""

from app.ports.budget import BudgetBreach, BudgetGuard, BudgetScope
from app.ports.cache import CachedGeneration, GenerationCache, cache_key
from app.ports.call_logs import LlmCallLog, LlmCallLogRepository
from app.ports.catalog import CatalogReader, OutcomeRecord, SyllabusDocumentRecord, TopicRecord
from app.ports.embedding import EmbeddingProvider, EmbeddingPurpose, EmbeddingResult
from app.ports.jobs import Job, JobError, JobRefs, JobRepository, NewJob
from app.ports.llm import (
    LlmContentBlockedError,
    LlmProvider,
    LlmProviderError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
    LlmUsage,
)
from app.ports.prompts import PromptCatalogEntry, PromptStore, PromptTemplate
from app.ports.video import TranscriptProvider, VideoSearchProvider

__all__ = [
    "BudgetBreach",
    "BudgetGuard",
    "BudgetScope",
    "CachedGeneration",
    "CatalogReader",
    "EmbeddingProvider",
    "EmbeddingPurpose",
    "EmbeddingResult",
    "GenerationCache",
    "Job",
    "JobError",
    "JobRefs",
    "JobRepository",
    "LlmCallLog",
    "LlmCallLogRepository",
    "LlmContentBlockedError",
    "LlmProvider",
    "LlmProviderError",
    "LlmRequest",
    "LlmResponse",
    "LlmTimeoutError",
    "LlmUsage",
    "NewJob",
    "OutcomeRecord",
    "PromptCatalogEntry",
    "PromptStore",
    "PromptTemplate",
    "SyllabusDocumentRecord",
    "TopicRecord",
    "TranscriptProvider",
    "VideoSearchProvider",
    "cache_key",
]
