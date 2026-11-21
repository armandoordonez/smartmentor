"""Errores de negocio (sin dependencias de FastAPI). La capa API los traduce a HTTP.

Cada clase fija su estado HTTP; el `code` estable sale del catálogo `docs/contracts/error-codes.md`
(una prueba verifica que todo código usado exista allí).
"""

from typing import Any


class DomainError(Exception):
    """Error de negocio con código estable para los consumidores de la API."""

    code = "DOMAIN_ERROR"
    title = "Domain error"
    status_code = 400

    def __init__(
        self, detail: str, *, code: str | None = None, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        # Extensiones permitidas por el catálogo: cycle, missing, retryable, job_id, ...
        self.extra: dict[str, Any] = extra or {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    title = "Resource not found"
    status_code = 404

    def __init__(self, resource: str, resource_id: int | str, *, code: str | None = None) -> None:
        super().__init__(f"{resource} with id {resource_id} was not found.", code=code)


class ConflictError(DomainError):
    """Unicidad o estado en conflicto (HTTP 409)."""

    code = "CONFLICT"
    title = "Conflict"
    status_code = 409


class InvalidStateTransitionError(ConflictError):
    code = "INVALID_STATE_TRANSITION"
    title = "Invalid state transition"


class BusinessRuleError(DomainError):
    """Violación de una regla de negocio (HTTP 422)."""

    code = "BUSINESS_RULE_VIOLATION"
    title = "Business rule violation"
    status_code = 422


class UnauthorizedError(DomainError):
    """Falta el token o no es válido (HTTP 401)."""

    code = "UNAUTHORIZED"
    title = "Authentication required"
    status_code = 401


class ForbiddenError(DomainError):
    """El usuario está autenticado pero no puede hacer esto (HTTP 403)."""

    code = "FORBIDDEN"
    title = "Forbidden"
    status_code = 403


class ServiceUnavailableError(DomainError):
    """Un servicio del que depende la API no responde (HTTP 503)."""

    code = "SERVICE_UNAVAILABLE"
    title = "Service unavailable"
    status_code = 503


class BadGatewayError(DomainError):
    """Un servicio del que depende la API respondió algo inválido o falló (HTTP 502)."""

    code = "AI_TASK_FAILED"
    title = "Upstream service error"
    status_code = 502


class PayloadTooLargeError(DomainError):
    code = "PAYLOAD_TOO_LARGE"
    title = "Payload too large"
    status_code = 413


class UnsupportedMediaTypeError(DomainError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    title = "Unsupported media type"
    status_code = 415


class PreconditionRequiredError(DomainError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    title = "Idempotency key required"
    status_code = 428


class ReferenceNotFoundError(BusinessRuleError):
    """Una llave foránea apunta a un registro que no existe."""

    code = "REFERENCE_NOT_FOUND"
    title = "Referenced resource not found"
