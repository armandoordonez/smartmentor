"""Textos y colores de cada estado, tal como los usa el diseño de Figma.

El color es el nombre de la paleta de Streamlit; sus valores exactos (los hex de Figma) están en
`.streamlit/config.toml`. Un estado nuevo se agrega aquí, nunca con un color suelto en una página.
"""

from typing import Literal

from clients.models import (
    BloomLevel,
    CourseStatus,
    EmbeddingStatus,
    EnrollmentStatus,
    QuestionKind,
    ReviewStatus,
    Role,
    StepStatus,
    TopicLevelStatus,
)

BadgeColor = Literal["green", "blue", "orange", "gray", "violet", "red"]
BadgeStyle = tuple[str, BadgeColor]

ROLE_BADGE: dict[Role, BadgeStyle] = {
    "student": ("Estudiante", "blue"),
    "teacher": ("Docente", "green"),
    "admin": ("Admin", "violet"),
}

STEP_BADGE: dict[StepStatus, BadgeStyle] = {
    "skipped": ("Dominado", "green"),
    "approved": ("Aprobado", "green"),
    "in_progress": ("En curso", "blue"),
    "pending": ("Pendiente", "gray"),
}

FINAL_LOCKED_BADGE: BadgeStyle = ("Bloqueada", "gray")
FINAL_AVAILABLE_BADGE: BadgeStyle = ("Disponible", "blue")
FINAL_PASSED_BADGE: BadgeStyle = ("Aprobada", "green")

LEVEL_BADGE: dict[TopicLevelStatus, BadgeStyle] = {
    "mastered": ("Dominado", "green"),
    "reinforce": ("Por reforzar", "orange"),
    "learn": ("Por aprender", "gray"),
}

ENROLLMENT_BADGE: dict[EnrollmentStatus, BadgeStyle] = {
    "onboarding": ("Diagnóstico", "gray"),
    "in_progress": ("En curso", "blue"),
    "completed": ("Completada", "green"),
    "abandoned": ("Abandonada", "gray"),
}

COURSE_BADGE: dict[CourseStatus, BadgeStyle] = {
    "draft": ("Borrador", "gray"),
    "in_review": ("En revisión", "blue"),
    "published": ("Publicado", "green"),
}

REVIEW_BADGE: dict[ReviewStatus, BadgeStyle] = {
    "approved": ("Aprobado", "green"),
    "pending": ("Pendiente", "orange"),
    "retired": ("Retirado", "gray"),
}

EMBEDDING_BADGE: dict[EmbeddingStatus, BadgeStyle] = {
    "indexed": ("Indexado", "green"),
    "pending": ("Pendiente", "orange"),
}

USER_STATUS_BADGE: dict[bool, BadgeStyle] = {True: ("Activo", "green"), False: ("Inactivo", "gray")}
ANSWER_BADGE: dict[bool, BadgeStyle] = {
    True: ("Correcta", "green"),
    False: ("Incorrecta", "orange"),
}
ATTEMPT_BADGE: dict[bool, BadgeStyle] = {
    True: ("Aprobado", "green"),
    False: ("No aprobado", "orange"),
}
TARGET_BADGE: dict[bool, BadgeColor] = {True: "green", False: "orange"}

BLOOM_LABEL: dict[BloomLevel, str] = {
    "remember": "Recordar",
    "understand": "Comprender",
    "apply": "Aplicar",
    "analyze": "Analizar",
    "evaluate": "Evaluar",
    "create": "Crear",
}

QUESTION_KIND_LABEL: dict[QuestionKind, str] = {
    "multiple_choice": "Opción múltiple",
    "short_answer": "Respuesta corta",
}
