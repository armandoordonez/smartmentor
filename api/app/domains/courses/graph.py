"""Grafo de prerrequisitos de un curso: detección de ciclos (`PREREQUISITE_CYCLE`).

Un grafo es `tema -> temas que son prerrequisito suyo`. Python puro, sin base de datos.
"""

from collections.abc import Iterable, Mapping

Graph = Mapping[int, Iterable[int]]


def find_cycle(graph: Graph, *, starts: Iterable[int] | None = None) -> list[int] | None:
    """Devuelve un ciclo como camino cerrado (`[12, 11, 12]`) o `None` si el grafo es acíclico.

    El camino sigue la relación «requiere»: 12 requiere 11 y 11 requiere 12. Con `starts` solo se
    busca desde esos temas (por ejemplo, el tema que se acaba de editar).
    """
    nodes = list(starts) if starts is not None else list(graph)
    done: set[int] = set()
    for start in nodes:
        if start in done:
            continue
        cycle = _dfs(graph, start, done)
        if cycle is not None:
            return cycle
    return None


def _dfs(graph: Graph, start: int, done: set[int]) -> list[int] | None:
    # Recorrido iterativo (los cursos tienen decenas de temas, pero sin límite de recursión).
    path: list[int] = []
    on_path: set[int] = set()
    stack: list[tuple[int, list[int]]] = [(start, list(graph.get(start, ())))]
    path.append(start)
    on_path.add(start)
    while stack:
        node, pending = stack[-1]
        if not pending:
            stack.pop()
            on_path.discard(node)
            path.pop()
            done.add(node)
            continue
        nxt = pending.pop(0)
        if nxt in on_path:
            return [*path[path.index(nxt) :], nxt]
        if nxt in done:
            continue
        path.append(nxt)
        on_path.add(nxt)
        stack.append((nxt, list(graph.get(nxt, ()))))
    return None


def build_graph(edges: Iterable[tuple[int, int]]) -> dict[int, list[int]]:
    """Arma `tema -> prerrequisitos` desde pares `(tema, prerrequisito)`."""
    graph: dict[int, list[int]] = {}
    for topic_id, prerequisite_id in edges:
        graph.setdefault(topic_id, []).append(prerequisite_id)
        graph.setdefault(prerequisite_id, [])
    return graph
