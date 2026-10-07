"""Errores de negocio del dominio de evaluaciones."""

from app.common.exceptions import BusinessRuleError


class MaxAttemptsExceededError(BusinessRuleError):
    code = "MAX_ATTEMPTS_EXCEEDED"
    title = "Maximum attempts exceeded"

    def __init__(self, max_attempts: int) -> None:
        super().__init__(f"The learning path allows at most {max_attempts} attempts.")


class StepEnrollmentMismatchError(BusinessRuleError):
    code = "STEP_ENROLLMENT_MISMATCH"
    title = "Step does not belong to the enrollment"

    def __init__(self) -> None:
        super().__init__("The path step does not belong to the enrollment.")


class FinalAssessmentNotPassedError(BusinessRuleError):
    code = "FINAL_ASSESSMENT_NOT_PASSED"
    title = "Final assessment not passed"

    def __init__(self) -> None:
        super().__init__("A badge requires a passed final assessment.")
