"""Errores de negocio del dominio de rutas de aprendizaje."""

from app.common.exceptions import BusinessRuleError


class TopicNotInPathCourseError(BusinessRuleError):
    code = "TOPIC_NOT_IN_PATH_COURSE"
    title = "Topic not in the path course"

    def __init__(self) -> None:
        super().__init__("The topic does not belong to the course of the learning path.")
