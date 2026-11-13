"""Traduce videos, anotación y calificación humana de la API a los modelos de D5b, D5c y D5e.

Como `content_adapter` y `dashboard_adapter`, es el único punto que conoce las dos formas:

* Videos: la API dice `has_captions`, `similarity` (0 a 1), `relevance_judgment` y el origen
  `youtube_api`; la pantalla dice `has_subtitles`, `relevance`, `is_relevant` y `youtube`. Duración
  e idioma pueden venir vacíos de YouTube: se muestran como 0 y sin idioma.
* Cola de calificación: la API devuelve una página de respuestas (`GradingQueuePage`) con
  `graded`; la pantalla quiere el «X de Y» de la muestra y los criterios como textos. El código
  de la respuesta es su número interno: no identifica al aprendiz.
* Resultado: la nota del LLM llega como `llm_grading` (puntaje y detalle por criterio); la
  pantalla muestra «X de Y criterios» y si coincide con lo que marcó el evaluador.
* Calidad de los videos (D5f): la API mide etiquetas («útil», audio, desactualizado, muy largo),
  vistas completas y un índice bayesiano de 0 a 1, y decide el estado. No mide la calificación
  de 1 a 5, el efecto en el quiz ni agrupa comentarios (F-012): esos campos quedan vacíos. Los
  «reportes» son las calificaciones que no dicen «útil», y las etiquetas van con su código para
  que la página las traduzca.
* Cola de anotación (D5b): la API devuelve una página de ítems (`AnnotationQueuePage`) con
  `annotated`; la pantalla quiere el «X de Y anotadas» y el puesto del evaluador. Las opciones
  pueden venir como textos u objetos con `text`. Un ítem sin puesto libre o ya anotado no se
  ofrece.

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


_QUALITY_STATUSES = frozenset({"recommended", "observation", "under_review", "measuring"})


def video_quality_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "rows" in data:
        return data
    needed = int(data.get("min_ratings", 0))
    rows: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    for item in data.get("items") or []:
        video = item.get("video") or {}
        by_rating = {str(k): int(v) for k, v in (item.get("by_rating") or {}).items()}
        ratings = int(item.get("ratings", sum(by_rating.values())))
        index = item.get("quality_index")
        status = item.get("status")
        rows.append(
            {
                "video_candidate_id": video["id"],
                "topic_id": video["topic_id"],
                "topic_label": f"{item.get('topic_name') or ''} · {video.get('title') or ''}",
                "index": None if index is None else round(float(index) * 100),
                "rating_average": None,
                "useful_rate": item.get("useful_rate"),
                "ratings_count": ratings,
                "ratings_needed": needed,
                "watched_fully_rate": (
                    round(int(item.get("watched_fully", 0)) / ratings, 4) if ratings else None
                ),
                "quiz_effect_points": None,
                "reports": ratings - by_rating.get("useful", 0),
                "status": status if status in _QUALITY_STATUSES else "measuring",
            }
        )
        problems = [(label, n) for label, n in by_rating.items() if label != "useful" and n]
        if problems:
            feedback.append(
                {
                    "video_candidate_id": video["id"],
                    "labels": [
                        {"label": label, "count": n}
                        for label, n in sorted(problems, key=lambda p: (-p[1], p[0]))
                    ],
                    "comments": [],
                    "comments_total": 0,
                }
            )
    return {"rows": rows, "feedback": feedback}


def _option_text(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("text", ""))
    return str(option)


def annotation_queue_from_api(data: dict[str, Any]) -> dict[str, Any]:
    if "limit" not in data:
        return data
    items = data.get("items") or []
    pending = int(data.get("total", len(items)))
    annotated = int(data.get("annotated", 0))
    return {
        "items": [
            {
                "item_id": item["id"],
                "topic_id": item["topic_id"],
                "topic_name": item.get("topic_name") or "",
                "bloom_level": item["bloom_level"],
                "stem": item.get("stem") or "",
                "options": [_option_text(o) for o in item.get("options") or []],
                "correct_option": item.get("correct_option"),
                "evaluator_slot": item["evaluator_slot"],
                "evaluator_slots_total": 2,
            }
            for item in items
            if item.get("evaluator_slot") is not None and item.get("own_annotation") is None
        ],
        "annotated": annotated,
        "total": annotated + pending,
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
