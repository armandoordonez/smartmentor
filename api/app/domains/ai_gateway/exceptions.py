"""Errores del servicio de IA vistos desde la API (docs/contracts/error-codes.md)."""

from app.common.exceptions import (
    BadGatewayError,
    NotFoundError,
    ServiceUnavailableError,
)


class AiJobNotFoundError(NotFoundError):
    code = "JOB_NOT_FOUND"

    def __init__(self, job_id: str) -> None:
        super().__init__("Job", job_id, code="JOB_NOT_FOUND")


class AiServiceUnavailableError(ServiceUnavailableError):
    """`ai/` no responde o devolvió 5xx."""

    code = "AI_SERVICE_UNAVAILABLE"
    title = "AI service unavailable"

    def __init__(self, detail: str = "The AI service is not reachable.") -> None:
        super().__init__(detail, extra={"retryable": True})


class AiTaskFailedError(BadGatewayError):
    """El trabajo terminó en `failed`."""

    code = "AI_TASK_FAILED"
    title = "AI task failed"

    def __init__(self, job_id: str, *, retryable: bool, error_code: str) -> None:
        super().__init__(
            f"The AI task failed ({error_code}).",
            extra={"job_id": job_id, "retryable": retryable},
        )


class AiBudgetExceededError(ServiceUnavailableError):
    """`ai/` rechazó el trabajo por presupuesto."""

    code = "AI_BUDGET_EXCEEDED"
    title = "AI budget exceeded"

    def __init__(self, job_id: str | None = None) -> None:
        super().__init__(
            "The AI budget was exceeded.", extra={"job_id": job_id} if job_id else None
        )


class AiResultInvalidError(BadGatewayError):
    """El resultado no cumple el contrato al ingerirlo."""

    code = "AI_RESULT_INVALID"
    title = "AI result invalid"

    def __init__(self, job_id: str) -> None:
        super().__init__(
            "The AI result does not comply with its contract.", extra={"job_id": job_id}
        )
