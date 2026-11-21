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
    description: str = ""
    """Qué hace el prompt, según `prompts/<id>/v<n>.md` (columna «Qué hace» de C4, V-087)."""


PROMPTS: tuple[PromptEntry, ...] = (
    PromptEntry(
        "syllabus_structuring",
        1,
        "Estructuración del syllabus",
        "D1c, D2",
        "Estructura el syllabus en temas, prerrequisitos y resultados de aprendizaje medibles",
    ),
    PromptEntry(
        "diagnostic_generation",
        2,
        "Generación del diagnóstico",
        "E3",
        "Genera 3 preguntas por tema (recordar, aplicar y analizar) para estimar el nivel previo, "
        "con distractores plausibles",
    ),
    PromptEntry(
        "item_review",
        1,
        "Revisión automática de ítems",
        "D5",
        "Revisa cada ítem: una sola respuesta correcta, enunciado claro y nivel de Bloom coherente",
    ),
    PromptEntry(
        "simulated_learner",
        1,
        "Aprendiz simulado (solo evaluación)",
        "",
        "Responde como un aprendiz simulado, con errores realistas, para probar la plataforma",
    ),
    PromptEntry(
        "learning_objective",
        1,
        "Objetivo de aprendizaje",
        "E4, E4b",
        "Propone el objetivo personal (Bloom + contenido + criterio) según su brecha",
    ),
    PromptEntry(
        "topic_explanation",
        1,
        "Explicación del tema",
        "E6, D5, D5d",
        "Explica el tema solo con los fragmentos del material, citando cada afirmación con [n]",
    ),
    PromptEntry(
        "remedial_explanation",
        1,
        "Explicación alterna",
        "E7b",
        "Explicación alterna con analogías, centrada en los errores del quiz no aprobado",
    ),
    PromptEntry(
        "personalized_example",
        1,
        "Ejemplo personalizado",
        "E6",
        "Ejemplo breve que aplica el tema a la experiencia del aprendiz",
    ),
    PromptEntry(
        "rag_faithfulness",
        1,
        "Verificación de fidelidad",
        "D5, D5d",
        "Verifica que cada afirmación de la explicación esté respaldada por los fragmentos citados",
    ),
    PromptEntry(
        "topic_quiz",
        3,
        "Banco del quiz del tema",
        "E6b, E6c, U1b, D5",
        "Genera ítems nuevos de opción múltiple y respuesta corta para el banco del quiz, con "
        "distractores plausibles y el nivel de Bloom que el ítem exige",
    ),
    PromptEntry(
        "short_answer_grading",
        2,
        "Calificación de respuesta corta",
        "E7, U1c, U1d, D5c",
        "Califica la respuesta corta con la rúbrica, explica cada criterio y da retroalimentación "
        "breve",
    ),
    PromptEntry(
        "final_assessment",
        2,
        "Banco de la evaluación final",
        "E8, E14",
        "Banco de la evaluación final y de retención, con versiones equivalentes de cada ítem y "
        "distractores plausibles",
    ),
    PromptEntry(
        "badge_text",
        1,
        "Texto del badge",
        "E10",
        "Redacta el nombre, la descripción, los criterios y las competencias del badge",
    ),
)
