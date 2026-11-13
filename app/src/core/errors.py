"""Traduce los errores de la API (`ApiError`) a mensajes en español, sin detalles técnicos.

El catálogo de códigos es `docs/contracts/error-codes.md`. El `title` y el `detail` de la API van en
inglés y son para quien depura: la interfaz muestra el texto de `MESSAGES` según el `code` y, si no
lo conoce, uno genérico por estado HTTP. El `request_id` va al registro, no a la pantalla.
"""

from dataclasses import dataclass
from typing import Literal

import streamlit as st

from clients.base import ApiError

# Los textos del contrato: código de error -> mensaje para la persona.
MESSAGES: dict[str, str] = {
    "CONSENT_REQUIRED": "Para continuar necesitas aceptar el tratamiento de tus datos.",
    "CONSENT_ALREADY_REVOKED": "Esta autorización ya estaba revocada.",
    "ENROLLMENT_ALREADY_EXISTS": "Ya estás inscrito en esta ruta.",
    "ENROLLMENT_NOT_FOUND": "No encontramos esa inscripción.",
    "ENROLLMENT_CLOSED": "Esta inscripción ya está cerrada.",
    "LEARNING_PATH_NOT_PUBLISHED": "Esta ruta todavía no está publicada.",
    "PROFILE_INCOMPLETE": "Completa la descripción de tu perfil para continuar.",
    "DIAGNOSTIC_ALREADY_SUBMITTED": "Ya entregaste el diagnóstico.",
    "DIAGNOSTIC_NOT_READY": "Todavía estamos calculando tu nivel.",
    "OBJECTIVE_NOT_MEASURABLE": "Agrega cómo sabrás que lo lograste.",
    "STEP_NOT_AVAILABLE": "Este tema todavía no está disponible.",
    "MAX_ATTEMPTS_EXCEEDED": "Ya usaste todos los intentos de este tema.",
    "ATTEMPT_ALREADY_SUBMITTED": "Ya entregaste esta prueba.",
    "ATTEMPT_NOT_GRADED": "Todavía estamos calificando tu prueba.",
    "FINAL_ASSESSMENT_LOCKED": "La evaluación final se habilita al aprobar todos los temas.",
    "REVIEW_ALREADY_REQUESTED": "Ya pediste la revisión de esta respuesta.",
    "SURVEY_ALREADY_SUBMITTED": "Ya respondiste la encuesta.",
    "EMAIL_NOT_VERIFIED": "Verifica tu correo para entrar a SmartMentor.",
    "ACCOUNT_DEACTIVATED": "Tu cuenta está desactivada. Contacta al administrador.",
    "SECOND_FACTOR_REQUIRED": "Esta página exige verificación en dos pasos.",
    "AI_TASK_FAILED": "No pudimos completar la tarea. Tu avance está guardado.",
    "AI_BUDGET_EXCEEDED": "La IA no está disponible por ahora. Tu avance está guardado.",
    "AI_SERVICE_UNAVAILABLE": "El servicio de IA no está disponible. Tu avance está guardado.",
    "JOB_TIMEOUT": "Está tardando más de lo normal. Tu avance está guardado.",
    "RATE_LIMITED": "Hiciste muchas peticiones seguidas. Espera un momento.",
}

ErrorKind = Literal[
    "session_expired", "forbidden", "blocked", "not_found", "conflict", "unavailable"
]

_BLOCKED_CODES = frozenset({"EMAIL_NOT_VERIFIED", "ACCOUNT_DEACTIVATED"})
# Errores que no se resuelven dentro de una pantalla: los atiende main.py (A6, A7, bloqueo).
_GLOBAL_CODES = _BLOCKED_CODES | {"INSUFFICIENT_ROLE", "SECOND_FACTOR_REQUIRED", "FORBIDDEN"}


@dataclass(frozen=True)
class ErrorView:
    kind: ErrorKind
    title: str
    message: str


def action_message(error: ApiError) -> str:
    """Mensaje corto para un error al ejecutar una acción dentro de una pantalla."""
    if error.code in MESSAGES:
        return MESSAGES[error.code]
    if error.status == 403:
        return "No tienes permiso para esta acción."
    if error.status == 404:
        return "No encontramos lo que buscas."
    if error.status == 422:
        return "Revisa los datos del formulario."
    if error.status >= 500:
        return "El servicio no está disponible. Intenta de nuevo en unos minutos."
    return "No se pudo completar la acción."


def describe_error(error: ApiError, role_label: str | None, page_title: str) -> ErrorView:
    """Pantalla de error de una página: A7 (401), A6 (403), cuenta bloqueada, 404, 409/422, 5xx."""
    if error.status == 401:
        return ErrorView(
            "session_expired",
            "Tu sesión expiró",
            "Por seguridad cerramos tu sesión tras 3 horas sin actividad. Tu avance está guardado.",
        )
    if error.status == 403 and error.code in _BLOCKED_CODES:
        return ErrorView("blocked", "No pudimos darte acceso", MESSAGES[error.code])
    if error.status == 403:
        return ErrorView(
            "forbidden",
            "No tienes permiso para ver esta página",
            f"Tu rol ({role_label or 'actual'}) no puede acceder a «{page_title}». "
            "Si crees que es un error, contacta al administrador.",
        )
    if error.status == 404:
        return ErrorView("not_found", "No encontramos lo que buscas", action_message(error))
    if error.status < 500:
        return ErrorView("conflict", "No se pudo completar la acción", action_message(error))
    return ErrorView(
        "unavailable", "El servicio no está disponible", "Intenta de nuevo en unos minutos."
    )


def is_global(error: ApiError) -> bool:
    """True si el error lo atiende `main.py` con una pantalla de estado (401 y 403 de rol)."""
    return error.status == 401 or error.code in _GLOBAL_CODES


def show_action_error(error: ApiError) -> None:
    """Muestra el error de una acción dentro de la pantalla; los globales (A6, A7) se relanzan.

    Se llama dentro de un `except ApiError`.
    """
    if is_global(error):
        raise error
    st.error(action_message(error))
