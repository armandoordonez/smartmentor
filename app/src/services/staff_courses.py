"""Cursos, temas y grafo del instructor (D1 a D2d): arma textos y vistas, sin reglas de negocio.

La detección de ciclos es solo una ayuda de presentación (avisa en el grafo antes de publicar): la
API valida de verdad al guardar y al publicar (`PREREQUISITE_CYCLE`).
"""

from collections.abc import Sequence

from clients.base import SmartMentorClient
from clients.models import Job
from clients.models_staff import Course, CourseTopic, ReviewCounts, TopicGraphDoc
from components.loading_steps import LoadingStep, StepState


def prereq_text(topic: CourseTopic, positions: dict[int, int]) -> str:
    """«Ninguno», «Tema 1» o «Temas 2, 3 y 4»."""
    numbers = sorted(positions[i] for i in topic.prerequisite_topic_ids if i in positions)
    if not numbers:
        return "Ninguno"
    if len(numbers) == 1:
        return f"Tema {numbers[0]}"
    return "Temas " + ", ".join(str(n) for n in numbers[:-1]) + f" y {numbers[-1]}"


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def review_summary(counts: ReviewCounts) -> str:
    """«1 corregido · 1 agregado por ti · 1 eliminado» (solo las partes con cambios)."""
    parts: list[str] = []
    if counts.corrected:
        parts.append(_plural(counts.corrected, "corregido", "corregidos"))
    if counts.added:
        parts.append(_plural(counts.added, "agregado por ti", "agregados por ti"))
    if counts.deleted:
        parts.append(_plural(counts.deleted, "eliminado", "eliminados"))
    return " · ".join(parts) if parts else "Sin cambios"


def reviewed_count(counts: ReviewCounts) -> int:
    return counts.unchanged + counts.corrected + counts.added


def find_cycle(edges: Sequence[tuple[int, int]]) -> list[int] | None:
    """Un ciclo del grafo dirigido (lista de ids con el primero repetido al final) o None."""
    graph: dict[int, list[int]] = {}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, [])
    state: dict[int, int] = {}
    stack: list[int] = []

    def visit(node: int) -> list[int] | None:
        state[node] = 1
        stack.append(node)
        for nxt in graph[node]:
            if state.get(nxt, 0) == 1:
                return [*stack[stack.index(nxt) :], nxt]
            if state.get(nxt, 0) == 0 and (found := visit(nxt)):
                return found
        stack.pop()
        state[node] = 2
        return None

    for start in graph:
        if state.get(start, 0) == 0 and (found := visit(start)):
            return found
    return None


def cycle_text(cycle: Sequence[int], names: dict[int, str]) -> str:
    return "«" + " → ".join(names.get(i, f"Tema {i}") for i in cycle) + " forma un ciclo»"


def graph_cycle(graph: TopicGraphDoc) -> list[int] | None:
    return find_cycle([(e.source, e.target) for e in graph.edges])


def extraction_steps(job: Job) -> list[LoadingStep]:
    """Los tres pasos de D1c según el estado del trabajo (`ai_jobs.status`)."""
    labels = (
        "Leer el documento",
        "Identificar temas, prerrequisitos y resultados de aprendizaje",
        "Validar que el grafo de temas no tenga ciclos",
    )
    states: list[StepState]
    match job.status:
        case "queued":
            states = ["running", "pending", "pending"]
        case "running":
            states = ["done", "running", "pending"]
        case "succeeded":
            states = ["done", "done", "done"]
        case _:
            states = ["done", "failed", "pending"]
    return [LoadingStep(label, state) for label, state in zip(labels, states, strict=True)]


def first_path_id(client: SmartMentorClient) -> int | None:
    """Ruta del primer curso publicado del instructor (entrada por el menú «Rutas y avance»)."""
    courses = client.list_courses(mine=True).items
    return next((c.learning_path.id for c in courses if c.learning_path), None)


def course_for(client: SmartMentorClient, course_id: int | None) -> Course | None:
    """El curso elegido o, si no hay, el primero de la lista."""
    if course_id is not None:
        return client.get_course(course_id)
    items = client.list_courses(mine=True).items
    return items[0] if items else None
