"""Vistas de la ruta del aprendiz (E5, E5b): textos armados con lo que dice la API.

Solo presenta datos: el estado de cada paso, su motivo de inclusión y los puntajes los calcula la
API. Aquí se redactan las líneas que muestra la pantalla.
"""

from clients.models import AssessmentItem, BloomLevel, Enrollment, PathDetail, PathStep
from components.formatting import approx_duration, duration, percent_points
from components.path_rows import PathRow

# Pasos que no se abren: la API no entrega su contenido (`409 STEP_NOT_AVAILABLE`). Un tema
# aprobado u omitido no se repasa desde la ruta (decisión del 11-nov-2026: seguir a la API).
CLOSED_STEPS = frozenset({"blocked", "on_hold", "passed", "skipped"})


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
            return None  # el motivo ya dice «Omitido por tu diagnóstico»
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
        )
        for step in path.steps
    ]


def progress_line(enrollment: Enrollment, path: PathDetail) -> str:
    progress = enrollment.progress
    line = f"Progreso: {progress.steps_done} de {progress.steps_total} temas"
    skipped = path.savings.skipped_topics
    if skipped:
        word = "omitido" if skipped == 1 else "omitidos"
        line += (
            f" · {skipped} {word} por tu diagnóstico "
            f"(ahorro {duration(path.savings.skipped_minutes)})"
        )
    return line


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
