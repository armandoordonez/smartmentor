"""Traduce los errores de la API a mensajes en español para el usuario (sin detalles técnicos)."""

from dataclasses import dataclass
from typing import Literal

from clients.base import ApiError
from clients.models import Role

_ROLE_NAME: dict[Role, str] = {"student": "Estudiante", "teacher": "Docente", "admin": "Admin"}

_MESSAGES = {
    "ALREADY_ENROLLED": "Ya estás inscrito en esta ruta.",
    "ALREADY_SUBMITTED": "Ya entregaste esta prueba.",
    "NO_ATTEMPTS_LEFT": "Ya usaste todos los intentos de este tema. Habla con tu docente.",
    "FINAL_LOCKED": "La evaluación final se habilita al completar todos los temas.",
    "QUIZ_NOT_READY": "Este tema todavía no tiene quiz.",
    "DIAGNOSTIC_REQUIRED": "Primero completa el diagnóstico.",
    "SYLLABUS_REQUIRED": "Solo se puede publicar un curso con el syllabus en revisión.",
    "EMAIL_TAKEN": "Ya existe un usuario con ese correo.",
    "SELF_EDIT_FORBIDDEN": "Solo otro admin puede editar tu cuenta.",
}


@dataclass(frozen=True)
class ErrorView:
    kind: Literal["session_expired", "forbidden", "not_found", "conflict", "unavailable"]
    title: str
    message: str


def describe_error(error: ApiError, role: Role | None, page_title: str) -> ErrorView:
    if error.status == 401:
        return ErrorView(
            "session_expired",
            "Tu sesión expiró",
            "Por seguridad cerramos tu sesión. Tu avance está guardado.",
        )
    if error.status == 403 and error.code == "INSUFFICIENT_ROLE":
        role_name = _ROLE_NAME[role] if role else "actual"
        return ErrorView(
            "forbidden",
            "No tienes permiso para ver esta página",
            f"Tu rol ({role_name}) no puede acceder a «{page_title}». "
            "Si crees que es un error, contacta al administrador.",
        )
    if error.status == 404:
        return ErrorView("not_found", "No encontramos lo que buscas", action_message(error))
    if error.status < 500:
        return ErrorView("conflict", "No se pudo completar la acción", action_message(error))
    return ErrorView(
        "unavailable",
        "El servicio no está disponible",
        "Intenta de nuevo en unos minutos.",
    )


def action_message(error: ApiError) -> str:
    """Mensaje corto para un error al ejecutar una acción dentro de una pantalla."""
    if error.code in _MESSAGES:
        return _MESSAGES[error.code]
    if error.status == 403:
        return "No tienes permiso para esta acción."
    if error.status == 404:
        return "No encontramos lo que buscas."
    if error.status == 422:
        return error.detail or "Revisa los datos del formulario."
    if error.status >= 500:
        return "El servicio no está disponible. Intenta de nuevo en unos minutos."
    return error.detail or "No se pudo completar la acción."
