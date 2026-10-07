"""Interfaces (puertos) de los repositorios de rutas de aprendizaje."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.learning_paths.entities import Enrollment, LearningPath, PathStep


class LearningPathRepository(CrudRepository[LearningPath], Protocol): ...


class EnrollmentRepository(CrudRepository[Enrollment], Protocol): ...


class PathStepRepository(CrudRepository[PathStep], Protocol): ...
