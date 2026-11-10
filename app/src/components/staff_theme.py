"""Textos y colores de los estados del instructor y del administrador (D1 a D5f, AD1 a AD5).

Igual que `theme.py`: el estado siempre lleva texto además del color y un estado nuevo se agrega
aquí, nunca con un color suelto en una página.
"""

from clients.models import BloomLevel, EnrollmentStatus, ItemType, PilotArm, Role
from clients.models_staff import (
    CourseStatus,
    ItemReviewStatus,
    MasteryStatus,
    MetricStatus,
    PilotStatus,
    QualityStatus,
    ResourceKind,
    ResourceReviewStatus,
    TopicReviewStatus,
    VideoStatus,
)
from components.theme import BadgeStyle

COURSE_BADGE: dict[CourseStatus, BadgeStyle] = {
    "draft": ("Borrador", "gray"),
    "extracting": ("Extrayendo", "blue"),
    "extraction_failed": ("Extracción fallida", "orange"),
    "in_review": ("En revisión", "orange"),
    "generating_content": ("Generando contenido", "blue"),
    "published": ("Publicado", "green"),
    "archived": ("Archivado", "gray"),
}

TOPIC_REVIEW_BADGE: dict[TopicReviewStatus, BadgeStyle] = {
    "unchanged": ("Sin cambios", "gray"),
    "corrected": ("Corregido", "blue"),
    "added": ("Agregado por ti", "green"),
    "deleted": ("Eliminado", "orange"),
}

BLOOM_LABEL: dict[BloomLevel, str] = {
    "remember": "Recordar",
    "understand": "Comprender",
    "apply": "Aplicar",
    "analyze": "Analizar",
    "evaluate": "Evaluar",
    "create": "Crear",
}

MASTERY_BADGE: dict[MasteryStatus, BadgeStyle] = {
    "skipped": ("Omitido", "gray"),
    "passed": ("Aprobado", "green"),
    "in_progress": ("En curso", "blue"),
    "reinforce": ("Refuerzo", "orange"),
    "attempts_exhausted": ("Intentos agotados", "red"),
    "pending": ("Pendiente", "gray"),
    "blocked": ("Bloqueado", "gray"),
    "on_hold": ("En espera", "orange"),
}

RESOURCE_BADGE: dict[ResourceReviewStatus, BadgeStyle] = {
    "approved": ("Aprobado", "green"),
    "pending_review": ("Por revisar", "orange"),
    "retired": ("Retirado", "gray"),
}
ITEM_BADGE: dict[ItemReviewStatus, BadgeStyle] = {
    "approved": ("Aprobado", "green"),
    "pending_review": ("Por revisar", "orange"),
    "auto_rejected": ("Rechazado por la IA", "red"),
    "retired": ("Retirado", "gray"),
}
ITEM_TYPE_LABEL: dict[ItemType, str] = {
    "multiple_choice": "Opción múltiple",
    "short_answer": "Respuesta corta",
}
RESOURCE_KIND_LABEL: dict[ResourceKind, str] = {
    "explanation": "Texto",
    "alternate_explanation": "Texto",
    "video": "Video",
}

VIDEO_STATUS_BADGE: dict[VideoStatus, BadgeStyle] = {
    "in_use": ("En uso", "green"),
    "backup": ("Respaldo", "blue"),
    "candidate": ("Candidato", "gray"),
    "rejected": ("Descartado", "gray"),
}
QUALITY_BADGE: dict[QualityStatus, BadgeStyle] = {
    "recommended": ("Recomendado", "green"),
    "observation": ("En observación", "orange"),
    "under_review": ("En revisión", "red"),
    "measuring": ("Midiendo", "gray"),
}

METRIC_BADGE: dict[MetricStatus, BadgeStyle] = {
    "meets": ("Cumple", "green"),
    "not_met": ("No cumple", "orange"),
    "report": ("Reportar", "blue"),
    "no_data": ("Sin datos", "gray"),
}

ADMIN_ENROLLMENT_BADGE: dict[EnrollmentStatus, BadgeStyle] = {
    "enrolled": ("Inscrito", "gray"),
    "profiling": ("Perfil", "gray"),
    "diagnosing": ("Diagnóstico", "gray"),
    "objective_pending": ("Objetivo", "gray"),
    "in_path": ("En curso", "blue"),
    "final_ready": ("Evaluación final", "blue"),
    "completed": ("Completada", "green"),
    "abandoned": ("Abandonada", "gray"),
    "withdrawn": ("Retirada", "gray"),
}
PILOT_ARM_TEXT: dict[PilotArm, str] = {"personalized": "Personalizada", "fixed": "Ruta fija"}
PILOT_STATUS_BADGE: dict[PilotStatus, BadgeStyle] = {
    "draft": ("Borrador", "gray"),
    "randomized": ("Sorteado", "blue"),
    "running": ("En curso", "green"),
    "closed": ("Cerrado", "gray"),
}
READINESS_TEXT: dict[str, str] = {
    "min_consents": "Faltan aprendices con consentimiento informado",
    "item_bank": "El banco de ítems equivalentes está incompleto",
    "dates": "Faltan las fechas del piloto",
    "fixed_group": "Falta el grupo de ruta fija",
}

ROLE_TEXT: dict[Role, str] = {"learner": "Aprendiz", "instructor": "Instructor", "admin": "Admin"}
