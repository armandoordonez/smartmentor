"""Errors that end a job (``error.code`` of a ``failed`` job, ``docs/contracts/error-codes.md``).

They are not HTTP responses: the worker stores them in ``ai_jobs`` and the API translates them
to ``AI_TASK_FAILED`` or ``AI_BUDGET_EXCEEDED``. Synchronous tasks map a few of them to HTTP.
"""

from __future__ import annotations

from typing import Final

# Codes and whether the API may ask to retry them (error-codes.md, last table).
RETRYABLE: Final[dict[str, bool]] = {
    "INVALID_OUTPUT": True,
    "LLM_PROVIDER_ERROR": True,
    "LLM_PROVIDER_TIMEOUT": True,
    "LLM_QUOTA_EXHAUSTED": True,
    "LLM_CONTENT_BLOCKED": False,
    "BUDGET_EXCEEDED": False,
    "PRICE_NOT_CONFIGURED": False,
    "NO_SOURCE_FRAGMENTS": False,
    "SYLLABUS_NO_TOPICS": False,
    "VIDEO_SEARCH_UNAVAILABLE": True,
    "INPUT_REFERENCE_NOT_FOUND": False,
    "INTERNAL_ERROR": True,
}

# Transient codes the worker re-queues by itself (up to AI_JOB_MAX_ATTEMPTS). INVALID_OUTPUT is
# retryable only on request (/retry): it already used its 2 retries with the model.
AUTO_RETRY: Final[frozenset[str]] = frozenset(
    {"LLM_PROVIDER_ERROR", "LLM_PROVIDER_TIMEOUT", "VIDEO_SEARCH_UNAVAILABLE", "INTERNAL_ERROR"}
)


class TaskError(Exception):
    """A job failure with a catalogued code."""

    def __init__(self, code: str, message: str, *, retryable: bool | None = None) -> None:
        if code not in RETRYABLE:
            raise ValueError(f"unknown job error code {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = RETRYABLE[code] if retryable is None else retryable


class BudgetExceededError(TaskError):
    def __init__(self, message: str) -> None:
        super().__init__("BUDGET_EXCEEDED", message)


class InputReferenceNotFoundError(TaskError):
    def __init__(self, message: str) -> None:
        super().__init__("INPUT_REFERENCE_NOT_FOUND", message)
