"""Traduce videos y calificación humana de la API a los modelos de las pantallas D5c y D6b.

Como `content_adapter` y `dashboard_adapter`, es el único punto que conoce las dos formas:

* Videos: la API dice `has_captions`, `similarity` (0 a 1), `relevance_judgment` y el origen
  `youtube_api`; la pantalla dice `has_subtitles`, `relevance`, `is_relevant` y `youtube`. Duración
  e idioma pueden venir vacíos de YouTube: se muestran como 0 y sin idioma.
* Cola de calificación: la API devuelve una página de respuestas (`GradingQueuePage`) con
  `graded`; la pantalla quiere el «X de Y» de la muestra y los criterios como textos. El código
  de la respuesta es su número interno: no identifica al aprendiz.
* Resultado: la nota del LLM llega como `llm_grading` (puntaje y detalle por criterio); la
  pantalla muestra «X de Y criterios» y si coincide con lo que marcó el evaluador.

Lo que ya trae la forma de la pantalla (los fixtures) pasa sin cambios.
"""

from __future__ import annotations

from typing import Any


def video_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "has_captions" not in data and "similarity" not in data:
        return data
    return {
        "id": data["id"],
        "youtube_video_id": data["youtube_video_id"],
        "title": data["title"],
        "channel": data.get("channel"),
        "duration_seconds": data.get("duration_seconds") or 0,
        "language": data.get("language") or "",
        "has_subtitles": bool(data.get("has_captions")),
        "relevance": data.get("similarity"),
        "status": data["status"],
        "is_relevant": data.get("relevance_judgment"),
        "origin": "instructor" if data.get("origin") == "instructor" else "youtube",
    }


def topic_videos_from_api(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic_id": data["topic_id"],
        "topic_name": data.get("topic_name") or "",
        "candidates": [video_from_api(c) for c in data.get("candidates") or []],
    }


def _criteria(rubric: Any) -> list[str]:
    return [str(r.get("criterion", "")) if isinstance(r, dict) else str(r) for r in rubric or []]


def grading_queue_from_api(data: dict[str, Any], sample: str) -> dict[str, Any]:
    if "sample_total" in data:
        return data
    items = data.get("items") or []
    pending = int(data.get("total", len(items)))
    graded = int(data.get("graded", 0))
    return {
        "items": [
            {
                "attempt_answer_id": item["attempt_answer_id"],
                "code": str(item["attempt_answer_id"]),
                "topic_name": item.get("topic_name") or "",
                "prompt": item.get("stem") or "",
                "answer": item.get("text_answer") or "",
                "criteria": _criteria(item.get("rubric")),
            }
            for item in items
        ],
        "sample_done": graded,
        "sample_total": graded + pending,
        "learner_requests": pending if sample == "learner_request" else 0,
        "sample_type": sample,
    }


def grading_result_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "llm_criteria_met" in data:
        return data
    llm = data.get("llm_grading") or {}
    detail = [d for d in llm.get("rubric_detail") or [] if isinstance(d, dict)]
    llm_met = sum(1 for d in detail if d.get("met"))
    human_met = sum(1 for c in data.get("criteria") or [] if isinstance(c, dict) and c.get("met"))
    return {
        "id": data["id"],
        "llm_criteria_met": llm_met,
        "llm_criteria_total": len(detail),
        "llm_rationale": llm.get("feedback") or "",
        "prompt_version": "",
        "agrees": bool(detail) and llm_met == human_met,
    }
