"""Traduce los errores de la API (`ApiError`) a mensajes en español, sin detalles técnicos.

El catálogo de códigos es `docs/contracts/error-codes.md`. El `title` y el `detail` de la API van en
inglés y son para quien depura: la interfaz muestra el texto de `MESSAGES` según el `code` y, si no
lo conoce, uno genérico por estado HTTP. El `request_id` va al registro, no a la pantalla.
"""

from dataclasses import dataclass
from typing import Literal, NoReturn

import streamlit as st

from clients.base import ApiError
from core.auth import TOKEN_EXPIRED_CODE
from core.widget_state import PressedButton, current_interaction

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
    "INVALID_BLOOM_VERB": "Elige el verbo de la lista de verbos de Bloom (por ejemplo, Aplicar).",
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

# Error global que ocurrió dentro de un `st.fragment` y que `main.py` atiende en la siguiente
# ejecución completa (B-031).
_DEFERRED_KEY = "deferred_global_error"
# Clic del fragmento que encontró el token vencido antes de enviar su petición (B-040).
_DEFERRED_CLICK_KEY = "deferred_click"

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


def defer_to_main(error: ApiError) -> NoReturn:
    """Deja un error global para `main.py` y pide una ejecución completa de la aplicación.

    Para los `st.fragment`, que corren fuera del `try/except` de `main.py`: relanzar el error ahí
    mostraba el traceback de Streamlit y dejaba la hoja de preguntas sin responder (B-031). Lo que
    la persona respondió sigue en `st.session_state`; en la ejecución completa `main.py` revisa el
    token (renovación o A7) y, si el token sigue vigente, muestra este error con su pantalla.

    B-040: si el token venció antes de enviar la petición (`TOKEN_EXPIRED` lo lanza la app, no la
    API), se guarda también el botón pulsado, para que `main.py` lo repita después de renovar.
    """
    st.session_state[_DEFERRED_KEY] = error
    if error.code == TOKEN_EXPIRED_CODE:
        st.session_state[_DEFERRED_CLICK_KEY] = current_interaction().pressed
    st.rerun(scope="app")


def pop_deferred_error() -> ApiError | None:
    """El error global que dejó un fragmento, si lo hay; se borra al leerlo."""
    error = st.session_state.pop(_DEFERRED_KEY, None)
    return error if isinstance(error, ApiError) else None


def pop_deferred_click() -> PressedButton | None:
    """El clic que un fragmento no pudo atender por el token vencido (B-040); se borra al leerlo."""
    click = st.session_state.pop(_DEFERRED_CLICK_KEY, None)
    return click if isinstance(click, PressedButton) else None
