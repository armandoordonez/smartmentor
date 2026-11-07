"""Prerequisite graph helpers shared by the syllabus checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def find_cycle(prerequisites: Mapping[str, Sequence[str]]) -> list[str] | None:
    """Return one prerequisite cycle as a closed path (``[a, b, a]``) or ``None``.

    ``prerequisites`` maps each topic id to the ids it requires. Unknown ids are ignored
    (they are reported by a separate check). Iterative DFS, deterministic in input order.
    """
    white, grey, black = 0, 1, 2
    color = dict.fromkeys(prerequisites, white)
    for root in prerequisites:
        if color[root] != white:
            continue
        stack: list[tuple[str, int]] = [(root, 0)]
        path: list[str] = [root]
        color[root] = grey
        while stack:
            node, index = stack[-1]
            deps = [d for d in prerequisites[node] if d in color]
            if index < len(deps):
                stack[-1] = (node, index + 1)
                nxt = deps[index]
                if color[nxt] == grey:
                    return [*path[path.index(nxt) :], nxt]
                if color[nxt] == white:
                    color[nxt] = grey
                    stack.append((nxt, 0))
                    path.append(nxt)
            else:
                color[node] = black
                stack.pop()
                path.pop()
    return None


def topological_order(
    order: Sequence[str], prerequisites: Mapping[str, Sequence[str]]
) -> list[str]:
    """Topological order that keeps the syllabus order whenever the DAG allows it.

    Same rule as ``topological_order`` in the notebook v2: at each step take the first topic,
    in syllabus order, whose prerequisites are already placed. Raises ``ValueError`` on a cycle.
    """
    pending = {t: {p for p in prerequisites.get(t, ()) if p != t and p in order} for t in order}
    result: list[str] = []
    while pending:
        ready = next((t for t in order if t in pending and not pending[t]), None)
        if ready is None:
            raise ValueError(f"prerequisite cycle among: {sorted(pending)}")
        result.append(ready)
        del pending[ready]
        for deps in pending.values():
            deps.discard(ready)
    return result
