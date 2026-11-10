"""Mensajes de error de las operaciones del instructor y del administrador (`error-codes.md`)."""

import streamlit as st

from clients.base import ApiError
from core.errors import action_message, is_global

STAFF_MESSAGES: dict[str, str] = {
    "SYLLABUS_NO_TEXT": "El PDF no tiene texto seleccionable. Sube otro archivo o pega el texto.",
    "SYLLABUS_TOO_LARGE": "El archivo pesa más de 10 MB. Sube uno más liviano o pega el texto.",
    "SYLLABUS_UNSUPPORTED_TYPE": "Solo se aceptan archivos PDF o texto.",
    "EXTRACTION_IN_PROGRESS": "La extracción de temas ya está en curso.",
    "PREREQUISITE_CYCLE": "Los prerrequisitos forman un ciclo. Quita una de las flechas.",
    "PREREQUISITE_SELF": "Un tema no puede ser prerrequisito de sí mismo.",
    "COURSE_REVIEW_INCOMPLETE": "Termina de revisar los temas antes de publicar.",
    "INVALID_STATE_TRANSITION": "Esa acción no está disponible en el estado actual.",
    "COURSE_NOT_FOUND": "No encontramos ese curso.",
    "PILOT_RUNNING": "Hay un piloto en curso: confirma el cambio para continuar.",
    "PILOT_ALREADY_STARTED": "El piloto ya inició y no admite este cambio.",
    "PILOT_NOT_READY": "El piloto todavía no está listo para iniciar.",
    "PILOT_CONSENT_REQUIRED": "Se necesitan aprendices con consentimiento para sortear.",
    "LAST_ADMIN": "Debe quedar al menos un administrador.",
    "ROLE_ALREADY_ASSIGNED": "La persona ya tiene ese rol.",
    "EMAIL_ALREADY_REGISTERED": "Ese correo ya está registrado.",
    "OWNER_NOT_FOUND": "No encontramos a ese instructor.",
    "ANNOTATION_ALREADY_EXISTS": "Ya anotaste esta pregunta.",
    "EVALUATOR_SLOTS_FULL": "Esta pregunta ya tiene sus dos evaluadores.",
    "EVALUATOR_NOT_ASSIGNED": "No estás asignado como evaluador de este curso.",
    "HUMAN_GRADING_ALREADY_EXISTS": "Ya calificaste esta respuesta.",
    "CONSENT_REQUIRED": "El aprendiz no ha aceptado el tratamiento de datos.",
}


def staff_message(error: ApiError) -> str:
    return STAFF_MESSAGES.get(error.code) or action_message(error)


def show_staff_error(error: ApiError) -> None:
    """Muestra el error de una acción; los globales (401, 403 de rol) los atiende `main.py`."""
    if is_global(error):
        raise error
    st.error(staff_message(error))
