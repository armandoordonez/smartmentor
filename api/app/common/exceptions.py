"""Errores de negocio (sin dependencias de FastAPI). La capa API los traduce a HTTP."""


class DomainError(Exception):
    """Error de negocio con código estable para los consumidores de la API."""

    code = "DOMAIN_ERROR"
    title = "Domain error"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    title = "Resource not found"

    def __init__(self, resource: str, resource_id: int | str) -> None:
        super().__init__(f"{resource} with id {resource_id} was not found.")


class ConflictError(DomainError):
    """Unicidad o estado en conflicto (HTTP 409)."""

    code = "CONFLICT"
    title = "Conflict"


class BusinessRuleError(DomainError):
    """Violación de una regla de negocio (HTTP 422)."""

    code = "BUSINESS_RULE_VIOLATION"
    title = "Business rule violation"


class UnauthorizedError(DomainError):
    """Falta el token o no es válido (HTTP 401)."""

    code = "UNAUTHORIZED"
    title = "Authentication required"


class ForbiddenError(DomainError):
    """El usuario está autenticado pero no puede hacer esto (HTTP 403)."""

    code = "FORBIDDEN"
    title = "Forbidden"


class ServiceUnavailableError(DomainError):
    """Un servicio del que depende la API no responde (HTTP 503)."""

    code = "SERVICE_UNAVAILABLE"
    title = "Service unavailable"


class ReferenceNotFoundError(BusinessRuleError):
    """Una llave foránea apunta a un registro que no existe."""

    code = "REFERENCE_NOT_FOUND"
    title = "Referenced resource not found"
