"""Traduce `GET /learning-paths/{id}/dashboard` de la API al modelo `Dashboard` de la pantalla D3.

El contrato (api-v2.md) solo dice «KPI, aprendices, matriz de dominio, temas críticos»; la API y
la interfaz eligieron formas distintas. Este adaptador es el único punto que conoce las dos:

* Las tasas de la API vienen en porcentaje (0 a 100); la pantalla las usa como fracción (0 a 1).
* El tema actual y su puntaje salen de la matriz de dominio: el primer tema, en el orden de la
  ruta, que el aprendiz no aprobó ni omitió.
* «Badge emitido» se deduce de la inscripción `completed` (el badge se emite al aprobar la final).
* Los abandonos por tema no los calcula la API todavía: se muestran en 0.

Si la respuesta ya trae la forma de la pantalla (los fixtures), pasa sin cambios.
"""

from __future__ import annotations

from typing import Any

# Estados de celda que la pantalla sabe dibujar (`MasteryStatus` en models_staff.py).
_CELL_STATUSES = frozenset(
    {
        "skipped",
        "passed",
        "in_progress",
        "reinforce",
        "attempts_exhausted",
        "pending",
        "blocked",
        "on_hold",
    }
)
_DONE = frozenset({"passed", "skipped"})


def is_api_dashboard(data: Any) -> bool:
    return isinstance(data, dict) and "kpi" in data and "mastery_matrix" in data


def _fraction(percent: Any) -> float | None:
    return None if percent is None else round(float(percent) / 100, 4)


def _settings(raw: dict[str, Any]) -> dict[str, Any]:
    objective = raw.get("default_objective") or {}
    has_objective = any(objective.get(k) for k in ("bloom_verb", "content", "criterion"))
    return {
        "topic_pass_threshold": round(float(raw["topic_pass_threshold"])),
        "final_pass_threshold": round(float(raw["final_pass_threshold"])),
        "mastery_skip_threshold": round(float(raw["mastery_skip_threshold"])),
        "max_attempts": int(raw["max_attempts"]),
        "short_answer_min_ratio": float(raw["short_answer_min_ratio"]),
        "level_weights": raw["level_weights"],
        "default_objective": objective if has_objective else None,
    }


def dashboard_from_api(data: dict[str, Any]) -> dict[str, Any]:
    """Documento con la forma de `Dashboard` (models_staff.py) a partir de `DashboardResponse`."""
    topics = data.get("topics") or []
    names = {int(t["id"]): t["name"] for t in topics}
    order = [int(t["id"]) for t in topics]
    cells_by_enrollment: dict[int, dict[int, dict[str, Any]]] = {
        int(row["enrollment_id"]): {int(c["topic_id"]): c for c in row.get("cells") or []}
        for row in data.get("mastery_matrix") or []
    }

    learners: list[dict[str, Any]] = []
    for learner in data.get("learners") or []:
        enrollment_id = int(learner["enrollment_id"])
        cells = cells_by_enrollment.get(enrollment_id, {})
        current = next(
            (cells[t] for t in order if t in cells and cells[t].get("status") not in _DONE), None
        )
        learners.append(
            {
                "enrollment_id": enrollment_id,
                "full_name": learner.get("full_name") or "",
                "status": learner["status"],
                "steps_done": learner.get("steps_done", 0),
                "steps_total": learner.get("steps_total", 0),
                "current_topic": names.get(int(current["topic_id"])) if current else None,
                "current_score": current.get("best_score") if current else None,
                "badge_issued": learner["status"] == "completed",
            }
        )

    full_names = {item["enrollment_id"]: item["full_name"] for item in learners}
    mastery = [
        {
            "enrollment_id": enrollment_id,
            "full_name": full_names.get(enrollment_id, ""),
            "cells": [
                status
                if (status := cells.get(t, {}).get("status")) in _CELL_STATUSES
                else "pending"
                for t in order
            ],
        }
        for enrollment_id, cells in cells_by_enrollment.items()
    ]

    kpi = data.get("kpi") or {}
    path = data.get("learning_path") or {}
    return {
        "course_id": data["course_id"],
        "learning_path": {
            "id": path.get("id", data.get("learning_path_id")),
            "name": path.get("name", ""),
            "group_label": path.get("group_label"),
        },
        "published": path.get("status") == "published",
        "pilot_running": bool(data.get("pilot_running", False)),
        "settings": _settings(data["settings"]),
        "kpis": {
            "enrolled": kpi.get("learners", 0),
            "completion_rate": _fraction(kpi.get("completion_rate")) or 0.0,
            "badges_issued": sum(1 for item in learners if item["badge_issued"]),
            "attempts_per_topic": kpi.get("attempts_per_topic"),
        },
        "learners": learners,
        "topics": [
            {"topic_id": t, "position": index, "name": names[t]}
            for index, t in enumerate(order, start=1)
        ],
        "mastery": mastery,
        "topic_stats": [
            {
                "topic_id": int(stat["topic_id"]),
                "first_attempt_pass_rate": _fraction(stat.get("first_attempt_pass_rate")),
                "avg_attempts": stat.get("average_attempts"),
                "abandonments": 0,
            }
            for stat in data.get("topic_stats") or []
        ],
        "critical_topic_ids": [int(c["topic_id"]) for c in data.get("critical_topics") or []],
        "unread_alerts": 0,
    }
