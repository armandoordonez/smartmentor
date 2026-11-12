"""Traduce los recursos y los ítems de la API a los modelos de la pantalla D5 (revisión).

El contrato dice `[Resource]` y `assessment_item.v1` sin fijar todos los campos; la API y la
interfaz eligieron nombres distintos. Este adaptador es el único punto que conoce las dos:

* Recurso: la API separa `resource_type` (`text`, `video`) y `kind` (`main`, `remedial`,
  `personal_example`); la pantalla usa `explanation`, `alternate_explanation` y `video`. El título
  sale del contenido; la versión es la etiqueta `1.n` (`version_label`); las fuentes citadas se
  muestran por su título.
* Ítem: la API dice de qué banco viene (`diagnostic`, `topic_quiz`, `final`, `retention`); la
  pantalla quiere saber si lo escribió la IA o el instructor. La rúbrica llega como
  `{criterion, points}` y la revisión automática como las casillas de `item_review.v1`.

Lo que ya trae la forma de la pantalla (los fixtures) pasa sin cambios.
"""

from __future__ import annotations

from typing import Any

_RESOURCE_STATUSES = frozenset({"pending_review", "approved", "retired"})
_REVIEW_CHECKS = ("single_correct_answer", "clear_stem", "bloom_matches", "aligned_with_outcome")


def resource_from_api(data: dict[str, Any]) -> dict[str, Any]:
    """Documento con la forma de `Resource` (models_staff.py) a partir de `ResourceResponse`."""
    if "resource_type" not in data:
        return data
    content = data.get("content") or {}
    is_video = data["resource_type"] == "video"
    if is_video:
        kind, fallback = "video", "Video del tema"
    elif data.get("kind") == "main":
        kind, fallback = "explanation", "Explicación del tema"
    else:
        kind, fallback = "alternate_explanation", "Explicación alternativa"
    # Cada fragmento citado es una fuente; los del mismo documento se muestran una vez.
    sources = list(
        dict.fromkeys(
            str(s.get("title") or s.get("url") or s.get("source_id"))
            if isinstance(s, dict)
            else str(s)
            for s in data.get("sources") or []
        )
    )
    status = data.get("review_status")
    return {
        "id": data["id"],
        "topic_id": data["topic_id"],
        "kind": kind,
        "title": content.get("title") or fallback,
        "version": data.get("version_label") or str(data.get("version", "")),
        "prompt_version": data.get("prompt_version"),
        "sources": sources,
        "faithfulness": data.get("faithfulness"),
        "relevance": None,
        "review_status": status if status in _RESOURCE_STATUSES else "pending_review",
        "edited_by_user_id": data.get("edited_by_user_id"),
        "content": None if is_video else (data.get("content") or None),
    }


def _auto_review(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if "verdict" in raw:
        return raw
    passed = all(raw.get(check, True) for check in _REVIEW_CHECKS)
    return {"verdict": "ok" if passed else "observaciones", "issues": list(raw.get("issues") or [])}


def item_from_api(data: dict[str, Any]) -> dict[str, Any]:
    """Documento con la forma de `ReviewItem` (models_staff.py) a partir de `ItemResponse`."""
    if data.get("source") in ("llm", "instructor"):
        return data
    return {
        "id": data["id"],
        "topic_id": data["topic_id"],
        "stem": data["stem"],
        "item_type": data["item_type"],
        "bloom_level": data["bloom_level"],
        "options": list(data.get("options") or []),
        "correct_option": data.get("correct_option"),
        "model_answer": data.get("model_answer"),
        "rubric": [
            str(r.get("criterion", "")) if isinstance(r, dict) else str(r)
            for r in data.get("rubric") or []
        ],
        # Un ítem sin versión de prompt lo escribió el instructor.
        "source": "llm" if data.get("prompt_version") else "instructor",
        "review_status": data["review_status"],
        "auto_review": _auto_review(data.get("auto_review")),
    }


def item_patch_for_api(body: dict[str, Any]) -> dict[str, Any]:
    """La rúbrica de la pantalla son textos; la API pide `{criterion, points}` (puntos iguales)."""
    rubric = body.get("rubric")
    if not rubric or isinstance(rubric[0], dict):
        return body
    points = round(1 / len(rubric), 4)
    return {**body, "rubric": [{"criterion": c, "points": points} for c in rubric]}
