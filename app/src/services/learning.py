"""Vistas de la ruta del aprendiz (E5, E5b): textos armados con lo que dice la API.

Solo presenta datos: el estado de cada paso, su motivo de inclusión y los puntajes los calcula la
API. Aquí se redactan las líneas que muestra la pantalla.
"""

from typing import Literal

from clients.models import (
    AssessmentItem,
    BloomLevel,
    Enrollment,
    NextAction,
    NextActionType,
    PathDetail,
    PathStep,
)
from components.formatting import approx_duration, duration, percent_points
from components.path_rows import PathRow

# Pasos que no se abren: la API no entrega su contenido (`409 STEP_NOT_AVAILABLE`). Un tema
# aprobado u omitido sí se abre: la API lo entrega en modo repaso (B-025, 2026-11-15).
CLOSED_STEPS = frozenset({"blocked", "on_hold"})
SKIPPED_DETAIL = "Puedes repasarlo cuando quieras"


def reason_line(step: PathStep) -> str:
    level = percent_points(step.diagnostic_level) if step.diagnostic_level is not None else None
    suffix = f" ({level} en el diagnóstico)" if level else ""
    match step.inclusion_reason:
        case "skipped_mastered":
            return (
                f"Omitido por tu diagnóstico: ya lo dominas ({level})"
                if level
                else ("Omitido por tu diagnóstico: ya lo dominas")
            )
        case "weak_prerequisite":
            return f"Incluido como prerrequisito débil{suffix}"
        case "objective_focus":
            return f"Parte de tu objetivo{suffix}"
        case "required_by_path":
            return f"Requerido por la ruta del curso{suffix}"
        case "mandatory":
            return f"Obligatorio{suffix}"
        case "fixed_path":
            return "Incluido · ruta fija"
        case None:
            return ""


def detail_line(step: PathStep) -> str | None:
    best = percent_points(step.best_score) if step.best_score is not None else None
    match step.status:
        case "skipped":
            return SKIPPED_DETAIL  # el motivo ya dice «Omitido por tu diagnóstico»
        case "passed":
            if best is None:
                return "Aprobado"
            when = (
                "al primer intento"
                if step.attempts_used <= 1
                else (f"en el intento {step.attempts_used}")
            )
            return f"Aprobado {when} · {best}"
        case "in_progress" | "attempts_exhausted":
            total = step.max_attempts + step.extra_attempts_granted
            line = (
                f"Usaste los {total} intentos"
                if step.status == "attempts_exhausted"
                else f"Intento {min(step.attempts_used + 1, total)} de {total}"
            )
            return f"{line} · mejor puntaje {best}" if best else line
        case "pending":
            if step.estimated_minutes is None:
                return None
            return f"Video + lectura + quiz · {approx_duration(step.estimated_minutes)}"
        case _:
            return None


def _reason_tone(step: PathStep) -> Literal["green", "blue"] | None:
    match step.inclusion_reason:
        case "skipped_mastered":
            return "green"
        case "weak_prerequisite" | "objective_focus":
            return "blue"
        case _:
            return None


def path_rows(path: PathDetail, *, fixed: bool) -> list[PathRow]:
    """Una fila por paso; en la ruta fija solo el motivo «Incluido · ruta fija»."""
    return [
        PathRow(
            step_id=step.step_id,
            order=step.step_order,
            name=step.name,
            status=step.status,
            reason=reason_line(step),
            detail=None if fixed else detail_line(step),
            openable=step.status not in CLOSED_STEPS,
            tone=_reason_tone(step),
        )
        for step in path.steps
    ]


def savings_label(path: PathDetail) -> str:
    """Tiempo ahorrado por los temas omitidos, o «—» si no hay minutos que mostrar.

    La API suma `estimated_minutes` de los temas omitidos; el syllabus extraído con IA suele dejar
    ese dato en `null`, y entonces la suma da 0 aunque haya temas omitidos (B-039). Con una
    inscripción nueva (nada omitido) también llega 0. En ambos casos no hay dato de minutos:
    «0 min» parecería un dato real, así que se muestra «—» (B-052).
    """
    minutes = path.savings.skipped_minutes
    return duration(minutes) if minutes > 0 else "—"


def progress_line(enrollment: Enrollment, path: PathDetail) -> str:
    progress = enrollment.progress
    line = f"Progreso: {progress.steps_done} de {progress.steps_total} temas"
    skipped = path.savings.skipped_topics
    if skipped:
        word = "omitido" if skipped == 1 else "omitidos"
        line += f" · {skipped} {word} por tu diagnóstico"
        if path.savings.skipped_minutes:
            line += f" (ahorro {duration(path.savings.skipped_minutes)})"
    return line


CONTINUE_TOPIC = "Continuar tema"
# Texto del botón principal de E5 según el `next_action` (B-039). Lo que no está aquí sigue un
# tema y dice «Continuar tema». Se reusan los textos de E9 y E10. Con la encuesta pendiente el
# botón lleva al badge (E10), que la ofrece como tarjeta opcional (B-045).
CONTINUE_LABELS: dict[NextActionType, str] = {
    "take_final": "Presentar evaluación final",
    "review_final": "Ver resultado de la evaluación final",
    "answer_survey": "Ver badge",
    "view_badge": "Ver badge",
}


def continue_label(action: NextAction, path: PathDetail, *, fixed: bool) -> str:
    """Texto de «Continuar» de E5 y E5b: dice a dónde lleva el `next_action`."""
    if action.type == "take_final" and path.final.attempts_used > 0:
        return "Reintentar evaluación final"
    if action.type == "continue_attempt" and action.step_id is None:
        return "Continuar evaluación final"  # intento abierto de la final
    label = CONTINUE_LABELS.get(action.type)
    if label is not None:
        return label
    next_step = step_name(path, action.step_id)
    return f"Continuar con {next_step}" if fixed and next_step else CONTINUE_TOPIC


NEXT_TOPIC = "Siguiente tema"
# Acciones que sí llevan a otro tema; para el resto el botón dice a dónde va (B-046).
_TOPIC_ACTIONS: frozenset[NextActionType] = frozenset({"study_topic", "continue_attempt"})


def passed_next_label(action: NextAction) -> str:
    """Texto del botón de E7 tras aprobar: «Siguiente tema» solo si hay otro tema que estudiar."""
    if action.type in _TOPIC_ACTIONS:
        return NEXT_TOPIC
    return CONTINUE_LABELS.get(action.type, "Continuar")


def step_name(path: PathDetail, step_id: int | None) -> str | None:
    for step in path.steps:
        if step.step_id == step_id:
            return step.name
    return None


BLOOM_LABEL: dict[BloomLevel, str] = {
    "remember": "Recordar",
    "understand": "Comprender",
    "apply": "Aplicar",
    "analyze": "Analizar",
    "evaluate": "Evaluar",
    "create": "Crear",
}


def bloom_label(item: AssessmentItem) -> str | None:
    return BLOOM_LABEL[item.bloom_level] if item.bloom_level else None


def item_context(item: AssessmentItem) -> str | None:
    """«Tema · Regresión lineal · Bloom · Aplicar» (E3, E14)."""
    parts = []
    if item.topic_name:
        parts.append(f"Tema · {item.topic_name}")
    bloom = bloom_label(item)
    if bloom:
        parts.append(f"Bloom · {bloom}")
    return " · ".join(parts) or None
