"""Traduce `GET /learning-paths/{id}/learners/{enrollment_id}` al modelo `LearnerDetail` (D4, D4b).

El contrato (api-v2.md) solo dice «perfil reducido (A3c), niveles e intentos», y la API y la
interfaz eligieron formas distintas. Este adaptador es el único punto que conoce las dos:

* Los niveles por tema (`level_by_topic`) vienen tal como los guardó el diagnóstico, con
  `topic_id` como texto y sin nombre: el nombre sale de los pasos de la ruta.
* Los intentos traen `step_id` y no el tema: el tema sale del paso. Los de la evaluación final no
  tienen paso. Solo se listan los intentos entregados y calificados (con puntaje y resultado).
* Los pasos `attempts_exhausted` son los «intentos agotados» de D4b. El tope es el de la regla más
  los intentos extra ya habilitados. Mientras tanto, quedan «en espera» los pasos `on_hold` y el
  aprendiz puede seguir con los `pending` o `in_progress`. La API no dice qué tema espera a cuál:
  si hay más de un paso agotado, cada uno muestra todos los pasos en espera.
* El perfil reducido llega como códigos (`education_level`, `experience_band`, `job_title`); la
  página arma el texto con las etiquetas de la interfaz. La API no manda la hoja de vida.

Si la respuesta ya trae la forma de la pantalla (los fixtures), pasa sin cambios.
"""

from __future__ import annotations

from typing import Any, get_args

from clients.models import EducationLevel, ExperienceBand, ObjectiveOrigin, TopicClassification

# Los valores que la pantalla sabe dibujar salen de los tipos del contrato (`clients/models.py`).
_EDUCATION_LEVELS: frozenset[str] = frozenset(get_args(EducationLevel))
_EXPERIENCE_BANDS: frozenset[str] = frozenset(get_args(ExperienceBand))
_CLASSIFICATIONS: frozenset[str] = frozenset(get_args(TopicClassification))
_ORIGINS: frozenset[str] = frozenset(get_args(ObjectiveOrigin))
_WAITING = frozenset({"on_hold"})
_CAN_CONTINUE = frozenset({"pending", "in_progress"})
FINAL_ASSESSMENT_NAME = "Evaluación final"


def is_api_learner_detail(data: Any) -> bool:
    return isinstance(data, dict) and "steps" in data and "level_by_topic" in data


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _known(value: Any, allowed: frozenset[str]) -> str | None:
    return str(value) if value in allowed else None


def _objective(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    origin = raw.get("origin")
    # Sin origen guardado, el objetivo es el de la ruta: la pantalla no muestra el origen.
    return {
        "statement": raw["statement"],
        "bloom_verb": raw["bloom_verb"],
        "content": raw["content"],
        "criterion": raw["criterion"],
        "origin": origin if origin in _ORIGINS else "path_default",
    }


def _topic_levels(data: dict[str, Any], names: dict[int, str]) -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []
    for raw in data.get("level_by_topic") or []:
        topic_id = _int(raw.get("topic_id"))
        level = raw.get("level")
        if topic_id is None or level is None:
            continue
        classification = raw.get("classification")
        levels.append(
            {
                "topic_id": topic_id,
                "name": names.get(topic_id) or raw.get("name") or f"Tema {topic_id}",
                "level": float(level),
                "classification": classification
                if classification in _CLASSIFICATIONS
                else "to_learn",
            }
        )
    order = {topic_id: index for index, topic_id in enumerate(names)}
    return sorted(levels, key=lambda item: order.get(item["topic_id"], len(order)))


def _attempts(data: dict[str, Any], step_names: dict[int, str]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for raw in data.get("attempts") or []:
        if raw.get("score") is None or raw.get("passed") is None or not raw.get("submitted_at"):
            continue
        step_id = _int(raw.get("step_id"))
        topic_name = FINAL_ASSESSMENT_NAME if step_id is None else step_names.get(step_id, "")
        attempts.append(
            {
                "attempt_id": int(raw["id"]),
                "step_id": step_id,
                "topic_name": topic_name,
                "attempt_number": int(raw["attempt_number"]),
                "score": float(raw["score"]),
                "passed": bool(raw["passed"]),
                "submitted_at": raw["submitted_at"],
                "extra_grant": bool(raw.get("uses_extra_grant", False)),
            }
        )
    return attempts


def _exhausted(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    waiting = [s["name"] for s in steps if s.get("status") in _WAITING]
    can_continue = [s["name"] for s in steps if s.get("status") in _CAN_CONTINUE]
    return [
        {
            "step_id": int(step["step_id"]),
            "topic_name": step["name"],
            "attempts_used": int(step.get("attempts_used", 0)),
            "max_attempts": int(step.get("max_attempts", 0))
            + int(step.get("extra_attempts_granted", 0)),
            "best_score": step.get("best_score"),
            "waiting_topic_names": waiting,
            "continue_topic_names": can_continue,
        }
        for step in steps
        if step.get("status") == "attempts_exhausted"
    ]


def learner_detail_from_api(data: dict[str, Any], path_id: int) -> dict[str, Any]:
    """Documento con la forma de `LearnerDetail` (models_staff.py) a partir de la respuesta."""
    steps = sorted(data.get("steps") or [], key=lambda s: s.get("step_order", 0))
    topic_names = {int(s["topic_id"]): s["name"] for s in steps}
    step_names = {int(s["step_id"]): s["name"] for s in steps}
    profile = data.get("profile") or {}
    path = data.get("learning_path") or {}
    return {
        "enrollment_id": int(data["enrollment_id"]),
        "user": {"id": int(data["user_id"]), "full_name": data.get("full_name") or ""},
        "learning_path": {
            "id": int(path.get("id", path_id)),
            "name": path.get("name", ""),
            "group_label": path.get("group_label"),
        },
        "status": data["status"],
        "profile_summary": None,
        "resume_summary": None,
        # Un código que la interfaz no conoce se omite en lugar de romper la pantalla.
        "education_level": _known(profile.get("education_level"), _EDUCATION_LEVELS),
        "experience_band": _known(profile.get("experience_band"), _EXPERIENCE_BANDS),
        "job_title": profile.get("job_title") or None,
        "objective": _objective(data.get("objective")),
        "topic_levels": _topic_levels(data, topic_names),
        "attempts": _attempts(data, step_names),
        "exhausted_steps": _exhausted(steps),
    }
