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
* Inscripciones (AD5): la API manda `user_id` con `full_name` y `pilot_consent` (aditivos); la
  pantalla quiere `user` y `consent_accepted`. Un brazo del piloto desconocido se muestra vacío.
* Métricas (AD3): `/metrics/evaluation` manda los valores sueltos y, desde 2026-11-12, `groups`
  (el catálogo con meta y estado, que decide la API). La pantalla solo usa `groups`: no hay
  cohorte en la API y nunca son datos de ejemplo.

El piloto (AD4 y AD4b) no tiene pantalla: lo definen los dueños fuera de la app (F-013).

Lo que ya trae la forma de la pantalla (los fixtures) pasa sin cambios.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
