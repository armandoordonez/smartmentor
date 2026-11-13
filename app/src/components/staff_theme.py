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
from components.theme import BadgeColor, BadgeStyle

COURSE_BADGE: dict[CourseStatus, BadgeStyle] = {
    "draft": ("Borrador", "gray"),
    "extracting": ("Extrayendo", "blue"),
    "extraction_failed": ("Extracción fallida", "orange"),
    "in_review": ("En revisión", "blue"),  # azul como en Figma D1 (V-006)
    "generating_content": ("Generando contenido", "blue"),
    "published": ("Publicado", "green"),
    "archived": ("Archivado", "gray"),
}

# Como Figma D2 y D2d: corregido ámbar y agregado violeta (V-020).
TOPIC_REVIEW_BADGE: dict[TopicReviewStatus, BadgeStyle] = {
    "unchanged": ("Sin cambios", "gray"),
    "corrected": ("Corregido", "orange"),
    "added": ("Agregado por ti", "violet"),
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
# Color del nivel de Bloom en D2: Figma pinta Comprender gris, Aplicar azul y Analizar ámbar. Los
# demás niveles siguen esa escala: los dos más bajos en gris y los tres más altos en ámbar.
BLOOM_COLOR: dict[BloomLevel, BadgeColor] = {
    "remember": "gray",
    "understand": "gray",
    "apply": "blue",
    "analyze": "orange",
    "evaluate": "orange",
    "create": "orange",
}

MASTERY_BADGE: dict[MasteryStatus, BadgeStyle] = {
    "skipped": ("Omitido", "violet"),  # como Figma D3
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

# Prioridad de una métrica del brief (AD3): P1 azul, P2 ámbar y P3 verde, como en Figma.
PRIORITY_COLOR: dict[str, BadgeColor] = {"P1": "blue", "P2": "orange", "P3": "green"}

METRIC_BADGE: dict[MetricStatus, BadgeStyle] = {
    "meets": ("Cumple", "green"),
    "not_met": ("No cumple", "red"),  # rojo como en Figma AD3
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
    "abandoned": ("Abandonada", "orange"),  # ámbar como Figma D3
    "withdrawn": ("Retirada", "gray"),
}
PILOT_ARM_TEXT: dict[PilotArm, str] = {"personalized": "Personalizada", "fixed": "Ruta fija"}
# Grupo del piloto y consentimiento como insignias, igual que Figma AD5 (V-023).
PILOT_ARM_BADGE: dict[PilotArm, BadgeStyle] = {
    "personalized": (PILOT_ARM_TEXT["personalized"], "blue"),
    "fixed": (PILOT_ARM_TEXT["fixed"], "violet"),
}
CONSENT_BADGE: dict[bool, BadgeStyle] = {
    True: ("Aceptado", "green"),
    False: ("Pendiente", "orange"),
}
PILOT_STATUS_BADGE: dict[PilotStatus, BadgeStyle] = {
    "draft": ("Borrador", "gray"),
    "randomized": ("Sorteado", "blue"),
    "running": ("En curso", "green"),
    "closed": ("Cerrado", "gray"),
}
READINESS_TEXT: dict[str, str] = {
    "min_consents": "Faltan aprendices con consentimiento informado",
    "item_bank": "El banco de preguntas (quiz, diagnóstico o final) está incompleto",
    "dates": "Faltan las fechas del piloto",
    "fixed_group": "Falta el grupo de ruta fija",
}

ROLE_TEXT: dict[Role, str] = {"learner": "Aprendiz", "instructor": "Instructor", "admin": "Admin"}
