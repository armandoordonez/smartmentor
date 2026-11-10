"""Errores del dominio de rutas (códigos de docs/contracts/error-codes.md)."""

from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


def enrollment_not_found(enrollment_id: int) -> NotFoundError:
    return NotFoundError("Enrollment", enrollment_id, code="ENROLLMENT_NOT_FOUND")


def step_not_found(step_id: int) -> NotFoundError:
    return NotFoundError("Path step", step_id, code="STEP_NOT_FOUND")


def path_not_found(path_id: int) -> NotFoundError:
    return NotFoundError("Learning path", path_id)


def enrollment_closed() -> ConflictError:
    return ConflictError(
        "The enrollment is completed, abandoned or withdrawn.", code="ENROLLMENT_CLOSED"
    )


def consent_required() -> ForbiddenError:
    return ForbiddenError(
        "The data processing consent is required before enrolling.", code="CONSENT_REQUIRED"
    )


def path_not_published() -> BusinessRuleError:
    return BusinessRuleError(
        "The learning path is not published.", code="LEARNING_PATH_NOT_PUBLISHED"
    )


def step_not_available(status: str) -> ConflictError:
    return ConflictError(f"The step is {status}.", code="STEP_NOT_AVAILABLE")


def max_attempts_exceeded(used: int, maximum: int) -> BusinessRuleError:
    return BusinessRuleError(
        "There are no attempts left.",
        code="MAX_ATTEMPTS_EXCEEDED",
        extra={"attempts_used": used, "max_attempts": maximum},
    )
