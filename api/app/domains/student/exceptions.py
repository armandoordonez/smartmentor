"""Errores de negocio del estudiante sobre sus propios datos."""

from app.common.exceptions import BusinessRuleError, ConflictError


class EnrollmentClosedError(BusinessRuleError):
    code = "ENROLLMENT_CLOSED"
    title = "Enrollment closed"

    def __init__(self) -> None:
        super().__init__("The enrollment is completed or abandoned and cannot be changed.")


class AlreadySubmittedError(ConflictError):
    code = "ALREADY_SUBMITTED"
    title = "Already submitted"

    def __init__(self, what: str) -> None:
        super().__init__(f"The {what} was already submitted.")
