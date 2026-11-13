"""Traduce las respuestas de administración de la API a los modelos de AD1 y AD2.

Como los demás adaptadores, es el único punto que conoce las dos formas:

* Usuarios (AD1): `/users` es el CRUD genérico y no trae roles; los roles llegan aparte (los
  reúne `StaffApiOps`). Aquí solo se junta cada usuario con sus roles.
* Log del LLM (AD2): la API guarda tokens de entrada y salida por separado y puede dejar vacíos el
  modelo, el prompt, el costo o la latencia (una llamada que falló). La pantalla quiere el total de
  tokens y textos: lo vacío se muestra como texto vacío o 0. La etiqueta de la tarea es su código:
  la página la traduce.
* Resumen del LLM: las latencias p50 y p95 llegan como `percentile_cont` (decimales o vacías) y la
  pantalla las quiere en milisegundos enteros.
* Piloto (AD4): la API trae `learning_path_id`, la ruta (`learning_path`) y los brazos (`arms`);
  los consentimientos y los temas con ítems equivalentes los manda `readiness`. Sin sorteo
  (borrador y brazos en 0) no hay grupos que mostrar. Un tema tiene ítems equivalentes si alguno de
  sus `equivalence_group` tiene dos o más versiones paralelas (final y retención), como define
  `docs/evaluation/metrics.md`.
* Inscripciones (AD5): la API manda `user_id` con `full_name` y `pilot_consent` (aditivos); la
  pantalla quiere `user` y `consent_accepted`. Un brazo del piloto desconocido se muestra vacío.
* Métricas (AD3): `/metrics/evaluation` manda los valores sueltos y, desde 2026-11-12, `groups`
  (el catálogo con meta y estado, que decide la API). La pantalla solo usa `groups`: no hay
  cohorte en la API y nunca son datos de ejemplo.
* Vista previa de la ruta fija (AD4b): `learning_path.v1` trae `topic_id` como texto y umbrales
  decimales; la pantalla los quiere enteros.

Lo que ya trae la forma de la pantalla (los fixtures) pasa sin cambios.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DEFAULT_PILOT_ID = 1
"""El piloto de los fixtures (hay uno por cohorte)."""
_PILOT_STATUSES = frozenset({"draft", "randomized", "running", "closed"})
_PILOT_ARMS = frozenset({"personalized", "fixed"})


def admin_user_from_api(user: dict[str, Any], roles: Sequence[str]) -> dict[str, Any]:
    if "roles" in user:
        return user
    return {
        "id": int(user["id"]),
        "email": user.get("email") or "",
        "full_name": user.get("full_name") or "",
        "roles": list(roles),
        "active": bool(user.get("active", True)),
    }


def _ms(value: Any) -> int:
    return 0 if value is None else round(float(value))


def llm_log_from_api(log: dict[str, Any]) -> dict[str, Any]:
    if "tokens" in log:
        return log
    return {
        "id": int(log["id"]),
        "task": log.get("task") or "",
        "task_label": log.get("task") or "",
        "model": log.get("model") or "",
        "prompt_id": log.get("prompt_id") or "",
        "prompt_version": log.get("prompt_version") or "",
        "tokens": int(log.get("input_tokens") or 0) + int(log.get("output_tokens") or 0),
        "cost_usd": float(log.get("cost_usd") or 0.0),
        "latency_ms": _ms(log.get("latency_ms")),
        "created_at": log["created_at"],
    }


def llm_logs_page_from_api(data: dict[str, Any]) -> dict[str, Any]:
    """La página de logs; una llamada sin fecha (no debería existir) no se muestra."""
    items = [i for i in data.get("items") or [] if "tokens" in i or i.get("created_at")]
    return {**data, "items": [llm_log_from_api(i) for i in items]}


def llm_summary_from_api(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "by_task": [
            {
                **task,
                "latency_p50_ms": _ms(task.get("latency_p50_ms")),
                "latency_p95_ms": _ms(task.get("latency_p95_ms")),
            }
            for task in data.get("by_task") or []
        ],
        "total_cost_usd": float(data.get("total_cost_usd") or 0.0),
    }


def pilot_to_show(pilots: Sequence[dict[str, Any]]) -> int | None:
    """El piloto que AD4 abre: el más reciente que no cerró; si todos cerraron, el más reciente."""
    if not pilots:
        return None
    ordered = sorted(pilots, key=lambda p: int(p["id"]), reverse=True)
    open_ = [p for p in ordered if p.get("status") != "closed"]
    return int((open_ or ordered)[0]["id"])


def is_api_pilot(data: Any) -> bool:
    return isinstance(data, dict) and "arms" in data


def pilot_from_api(data: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    path = data.get("learning_path") or {}
    arms = data.get("arms") or {}
    personalized, fixed = int(arms.get("personalized", 0)), int(arms.get("fixed", 0))
    status = data.get("status")
    drawn = status != "draft" or personalized > 0 or fixed > 0
    return {
        "id": int(data["id"]),
        "learning_path": {
            "id": int(path.get("id", data["learning_path_id"])),
            "name": path.get("name") or f"Ruta {data['learning_path_id']}",
            "group_label": path.get("group_label"),
        },
        "status": status if status in _PILOT_STATUSES else "draft",
        "starts_on": data.get("starts_on"),
        "ends_on": data.get("ends_on"),
        "delayed_posttest_on": data.get("delayed_posttest_on"),
        "random_seed": data.get("random_seed"),
        "groups": {"personalized": personalized, "fixed": fixed} if drawn else None,
        "consents": {
            "accepted": int(readiness.get("consents_accepted", 0)),
            "total": int(readiness.get("consents_total", 0)),
        },
        "equivalent_items_topics": int(readiness.get("topics_with_equivalent_items", 0)),
        "topics_total": int(readiness.get("topics_total", 0)),
    }


def fixed_path_preview_from_api(data: dict[str, Any]) -> dict[str, Any]:
    steps = data.get("steps") or []
    if "algorithm" not in data and isinstance(data.get("final_pass_threshold"), int):
        return data  # ya tiene la forma de la pantalla (fixtures)
    return {
        "pilot_arm": data.get("pilot_arm") or "fixed",
        "steps": [
            {
                "step_order": int(step["step_order"]),
                "topic_id": int(step["topic_id"]),
                "name": step.get("name") or "",
            }
            for step in steps
            if step.get("status") != "skipped"
        ],
        "final_pass_threshold": round(float(data.get("final_pass_threshold") or 0)),
        "mastery_skip_threshold": round(float(data.get("mastery_skip_threshold") or 0)),
    }


def admin_enrollment_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "user" in data:
        return data
    path = data.get("learning_path") or {}
    arm = data.get("pilot_arm")
    return {
        "id": int(data["id"]),
        "user": {"id": int(data["user_id"]), "full_name": data.get("full_name") or ""},
        "learning_path": {
            "id": int(path["id"]),
            "name": path.get("name") or "",
            "group_label": path.get("group_label"),
        },
        "pilot_arm": arm if arm in _PILOT_ARMS else None,
        "consent_accepted": bool(data.get("pilot_consent", False)),
        "status": data["status"],
        "analysis_included": bool(data.get("analysis_included", True)),
    }


def admin_enrollments_page_from_api(data: dict[str, Any]) -> dict[str, Any]:
    return {**data, "items": [admin_enrollment_from_api(i) for i in data.get("items") or []]}


def metrics_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "cohort" in data:
        return data
    return {"cohort": "", "is_sample_data": False, "groups": list(data.get("groups") or [])}
