"""Errores de negocio del dominio de cursos."""

from app.common.exceptions import BusinessRuleError


class PrerequisiteCycleError(BusinessRuleError):
    code = "PREREQUISITE_CYCLE"
    title = "Prerequisite cycle"

    def __init__(self) -> None:
        super().__init__("The prerequisite would create a cycle between topics.")


class PrerequisiteAcrossCoursesError(BusinessRuleError):
    code = "PREREQUISITE_ACROSS_COURSES"
    title = "Prerequisite across courses"

    def __init__(self) -> None:
        super().__init__("A topic and its prerequisite must belong to the same course.")
