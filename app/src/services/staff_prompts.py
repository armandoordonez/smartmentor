"""Catálogo de prompts (C4): copia de lectura de `prompts/catalog.yaml`.

Es documentación del equipo, sin ruta en la API. Si cambia `prompts/catalog.yaml`, se actualiza esta
lista (una prueba de la interfaz solo vigila que los ids no se repitan).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptEntry:
    prompt_id: str
    version: int
    name: str
    screens: str


PROMPTS: tuple[PromptEntry, ...] = (
    PromptEntry("syllabus_structuring", 1, "Estructuración del syllabus", "D1c, D2"),
    PromptEntry("diagnostic_generation", 1, "Generación del diagnóstico", "E3"),
    PromptEntry("item_review", 1, "Revisión automática de ítems", "D5"),
    PromptEntry("simulated_learner", 1, "Aprendiz simulado (solo evaluación)", ""),
    PromptEntry("learning_objective", 1, "Objetivo de aprendizaje", "E4, E4b"),
    PromptEntry("topic_explanation", 1, "Explicación del tema", "E6, D5, D5d"),
    PromptEntry("remedial_explanation", 1, "Explicación alterna", "E7b"),
    PromptEntry("personalized_example", 1, "Ejemplo personalizado", "E6"),
    PromptEntry("rag_faithfulness", 1, "Verificación de fidelidad", "D5, D5d"),
    PromptEntry("topic_quiz", 1, "Banco del quiz del tema", "E6b, E6c, U1b, D5"),
    PromptEntry("short_answer_grading", 1, "Calificación de respuesta corta", "E7, U1c, U1d, D5c"),
    PromptEntry("final_assessment", 1, "Banco de la evaluación final", "E8, E14"),
    PromptEntry("badge_text", 1, "Texto del badge", "E10"),
)
