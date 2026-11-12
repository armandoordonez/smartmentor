"""Textos y colores de cada estado, tal como los usa el diseño de Figma.

El color es el nombre de la paleta de Streamlit; sus valores exactos salen de `tokens.css` por
`.streamlit/config.toml`. Un estado nuevo se agrega aquí, nunca con un color suelto en una página.
El estado siempre lleva texto además del color (accesibilidad).
"""

from typing import Literal

from clients.models import (
    EducationLevel,
    EnrollmentStatus,
    ExperienceBand,
    InclusionReason,
    PathLevel,
    PathTag,
    Role,
    StepStatus,
    TopicClassification,
    VideoRating,
)

BadgeColor = Literal["green", "blue", "orange", "gray", "violet", "red"]
BadgeStyle = tuple[str, BadgeColor]

ROLE_COLOR: dict[Role, BadgeColor] = {"learner": "blue", "instructor": "green", "admin": "violet"}

STEP_BADGE: dict[StepStatus, BadgeStyle] = {
    "skipped": ("Dominado", "green"),
    "passed": ("Aprobado", "green"),
    "in_progress": ("En curso", "blue"),
    "pending": ("Pendiente", "gray"),
    "blocked": ("Bloqueado", "gray"),
    "on_hold": ("En espera", "orange"),
    "attempts_exhausted": ("Intentos agotados", "orange"),
}

LEVEL_BADGE: dict[TopicClassification, BadgeStyle] = {
    "mastered": ("Dominado", "green"),
    "to_reinforce": ("Por reforzar", "orange"),
    "to_learn": ("Por aprender", "gray"),
}

ENROLLMENT_BADGE: dict[EnrollmentStatus, BadgeStyle] = {
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

ATTEMPT_BADGE: dict[bool, BadgeStyle] = {
    True: ("Aprobado", "green"),
    False: ("No aprobado", "orange"),
}
ANSWER_BADGE: dict[bool, BadgeStyle] = {
    True: ("Correcta", "green"),
    False: ("Incorrecta", "orange"),
}

# Antetítulos de las tarjetas del catálogo (E1).
PATH_TAG_TEXT: dict[PathTag, str] = {
    "recommended": "RECOMENDADA PARA TI",
    "new": "NUEVA",
    "popular": "POPULAR",
    "new_anthropic": "NUEVO · ANTHROPIC",
    "new_google": "NUEVO · GOOGLE",
}

PATH_LEVEL_LABEL: dict[PathLevel, str] = {
    "basic": "Básico",
    "intermediate": "Intermedio",
    "advanced": "Avanzado",
}

INCLUSION_REASON_TEXT: dict[InclusionReason, str] = {
    "skipped_mastered": "Omitido: ya lo dominas",
    "weak_prerequisite": "Incluido: prerrequisito débil",
    "objective_focus": "Incluido: parte de tu objetivo",
    "required_by_path": "Incluido: requerido por la ruta",
    "mandatory": "Incluido: obligatorio",
    "fixed_path": "Incluido: ruta fija",
}

# Campos de la hoja de vida (E2b, E15).
EDUCATION_LEVEL_LABEL: dict[EducationLevel, str] = {
    "none": "Sin estudios formales",
    "secondary": "Bachiller",
    "technical": "Técnico o tecnólogo",
    "undergraduate": "Profesional",
    "postgraduate": "Posgrado",
    "other": "Otro",
}
EXPERIENCE_BAND_LABEL: dict[ExperienceBand, str] = {
    "none": "Sin experiencia",
    "less_than_1_year": "Menos de 1 año",
    "1_3_years": "1 a 3 años",
    "3_5_years": "3 a 5 años",
    "more_than_5_years": "Más de 5 años",
}
LANGUAGE_LABEL: dict[str, str] = {
    "es": "Español",
    "en": "Inglés",
    "pt": "Portugués",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
}
COMMON_TOOLS: tuple[str, ...] = ("Excel", "SQL", "Python", "R", "Power BI", "Tableau")

# Tareas de `ai/` tal como las registra el log del LLM (`prompts/catalog.yaml`, AD2). Una tarea
# nueva que no esté aquí se muestra con su código.
AI_TASK_LABEL: dict[str, str] = {
    "syllabus.structure": "Estructurar el syllabus",
    "diagnostic.generate_items": "Preguntas del diagnóstico",
    "diagnostic.finalize": "Cerrar el diagnóstico",
    "levels.estimate": "Estimar niveles",
    "path.sequence": "Ordenar la ruta",
    "items.review": "Revisar preguntas",
    "items.generate_quiz_bank": "Quiz del tema",
    "items.generate_final_bank": "Evaluación final",
    "content.explain_topic": "Explicación (RAG)",
    "content.remedial": "Explicación alterna",
    "content.personal_example": "Ejemplo personalizado",
    "content.check_faithfulness": "Fidelidad de la explicación",
    "grading.short_answer": "Califica respuesta corta",
    "badge.compose_text": "Texto del badge",
    "video.rank": "Ordenar videos",
    "eval.simulate_learner": "Aprendiz simulado",
}

VIDEO_RATING_LABEL: dict[VideoRating, str] = {
    "useful": "Claro y útil",
    "audio_issue": "Audio con problemas",
    "outdated": "Desactualizado",
    "too_long": "Muy largo",
}

BLOOM_VERBS: tuple[str, ...] = ("Recordar", "Comprender", "Aplicar", "Analizar", "Evaluar", "Crear")
