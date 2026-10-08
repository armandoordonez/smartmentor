"""Contratos HTTP del estudiante. Las respuestas reutilizan los esquemas de cada dominio."""

from typing import Any

from pydantic import Field

from app.common.schemas import RequestSchema


class EnrollRequest(RequestSchema):
    """El usuario no se envía: es siempre el del token."""

    learning_path_id: int = Field(gt=0)
    profile_description: str | None = None
    personal_objective: str | None = None


class ProfileUpdate(RequestSchema):
    profile_description: str | None = None
    personal_objective: str | None = None


class SubmitAnswers(RequestSchema):
    answers: list[Any] | dict[str, Any]
