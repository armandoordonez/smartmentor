"""Salidas deterministas de `FakeAiService` para los trabajos de contenido.

Cada una cumple el JSON Schema de `prompts/schemas/` (lo comprueba la prueba de contrato). Solo usa
la biblioteca estándar: `ai_gateway/fake.py` las registra sin crear importaciones circulares.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

ResultFactory = Callable[[dict[str, Any]], dict[str, Any]]

VIDEO_IDS = ("EXAMPLE0001", "EXAMPLE0002", "EXAMPLE0003")


def _meta(prompt_id: str, seed: str) -> dict[str, Any]:
    return {
        "prompt_id": prompt_id,
        "prompt_version": "v1",
        "model": "fake-model",
        "generated_at": datetime(2026, 11, 7, 15, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "input_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "from_cache": False,
    }


def fake_explain_topic(input_: dict[str, Any]) -> dict[str, Any]:
    topic_id = str(input_.get("topic_id", "0"))
    return {
        "topic_id": topic_id,
        "kind": "main",
        "audience": "all_learners",
        "version": "1.0",
        "title": f"Explicación del tema {topic_id}",
        "sections": [
            {"heading": "Idea central", "body": "Texto de la idea central [1]."},
            {"heading": "Aplicación", "body": "Texto de la aplicación [1]."},
        ],
        "worked_example": "Ejemplo resuelto paso a paso.",
        "summary": "Resumen del tema.",
        "reflection_questions": ["¿Dónde aplicarías esto?"],
        "gaps_detected": [],
        "sources": [
            {
                "n": 1,
                "source_id": f"chunk-{topic_id}-1",
                "title": "Fuente abierta",
                "url": "https://example.org/fuente",
                "license": "CC-BY",
            }
        ],
        "faithfulness": 0.95,
        "unsupported_claims": [],
        "meta": _meta("topic_explanation", f"explain:{topic_id}"),
    }


def fake_check_faithfulness(input_: dict[str, Any]) -> dict[str, Any]:
    return {
        "claims": [
            {"text": "Afirmación respaldada.", "citations": [1], "supported": True, "comment": ""},
            {
                "text": "Afirmación sin respaldo.",
                "citations": [],
                "supported": False,
                "comment": "x",
            },
        ],
        "faithfulness": 0.5,
        "unsupported_claims": ["Afirmación sin respaldo."],
        "meta": _meta("rag_faithfulness", str(input_.get("text", ""))),
    }


def _item(key: str, topic_id: str, source: str, kind: str, n: int) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": key,
        "topic_id": topic_id,
        "outcome_id": "0",
        "source": source,
        "bloom_level": "understand",
        "difficulty": 2,
        "stem": f"Pregunta {key} del tema {topic_id} ({source}, {n})",
        "equivalence_group": f"eq_{key}" if source in ("final", "retention") else None,
    }
    if kind == "multiple_choice":
        return {
            **base,
            "item_type": "multiple_choice",
            "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
            "correct_option": n % 4,
            "model_answer": "La opción correcta es la acertada porque sí.",
            "rubric": [],
        }
    return {
        **base,
        "item_type": "short_answer",
        "options": [],
        "correct_option": None,
        "model_answer": "Respuesta esperada.",
        "rubric": [
            {"criterion": "Define el concepto", "points": 0.5},
            {"criterion": "Da un ejemplo", "points": 0.5},
        ],
    }


def _bank(
    topic_ids: list[str], source: str, n_mc: int, n_sa: int, bank_topic: str | None, seed: str
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for topic_id in topic_ids:
        for n in range(n_mc):
            items.append(
                _item(f"{source[0]}{topic_id}m{n}", topic_id, source, "multiple_choice", n)
            )
        for n in range(n_sa):
            items.append(_item(f"{source[0]}{topic_id}s{n}", topic_id, source, "short_answer", n))
    return {
        "topic_id": bank_topic,
        "items": items,
        "item_reviews": [
            {
                "item_id": i["id"],
                "single_correct_answer": True,
                "clear_stem": True,
                "bloom_matches": True,
                "aligned_with_outcome": True,
                "issues": [],
            }
            for i in items
        ],
        "discarded_item_ids": [],
        "meta": _meta("topic_quiz", seed),
    }


def fake_quiz_bank(input_: dict[str, Any]) -> dict[str, Any]:
    topic_id = str(input_.get("topic_id", "0"))
    return _bank(
        [topic_id],
        "topic_quiz",
        int(input_.get("n_multiple_choice", 4)),
        int(input_.get("n_short_answer", 1)),
        topic_id,
        f"quiz:{topic_id}",
    )


def fake_final_bank(input_: dict[str, Any]) -> dict[str, Any]:
    topics = [str(t) for t in input_.get("topic_ids", [])] or ["0"]
    return _bank(topics, "final", 1, int(input_.get("n_short_answer", 1)), None, "final")


def fake_diagnostic_bank(input_: dict[str, Any]) -> dict[str, Any]:
    topics = [str(t) for t in input_.get("topic_ids", [])] or [str(input_.get("topic_id", "0"))]
    return _bank(topics, "diagnostic", 2, 0, None, "diagnostic")


def fake_item_review(input_: dict[str, Any]) -> dict[str, Any]:
    items = input_.get("items", [])
    return {
        "reviews": [
            {
                "item_id": str(i["item_id"]),
                "single_correct_answer": True,
                "clear_stem": True,
                "bloom_matches": True,
                "aligned_with_outcome": True,
                "issues": [],
            }
            for i in items
        ]
        or [
            {
                "item_id": "0",
                "single_correct_answer": True,
                "clear_stem": True,
                "bloom_matches": True,
                "aligned_with_outcome": True,
                "issues": [],
            }
        ],
        "discarded_item_ids": [],
        "meta": _meta("item_review", "review"),
    }


def fake_video_candidates(input_: dict[str, Any]) -> dict[str, Any]:
    topic_id = str(input_.get("topic_id", "0"))
    return {
        "topic_id": topic_id,
        "origin": "youtube_api",
        "embedding_model": "fake-embedding",
        "candidates": [
            {
                "youtube_video_id": vid,
                "title": f"Video {n + 1} del tema {topic_id}",
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": "Canal de ejemplo",
                "origin": "youtube_api",
                "duration_seconds": 600 + n * 60,
                "language": "es",
                "has_captions": True,
                "characterization": "Subtemas del tema",
                "characterization_source": "metadata",
                "similarity": round(0.9 - n * 0.1, 2),
                "rank": n + 1,
            }
            for n, vid in enumerate(VIDEO_IDS)
        ],
        "selected_video_id": VIDEO_IDS[0],
        "backup_video_ids": list(VIDEO_IDS[1:]),
    }


CONTENT_RESULTS: dict[str, tuple[str | None, ResultFactory]] = {
    "content.explain_topic": ("topic_explanation.v1", fake_explain_topic),
    "content.check_faithfulness": ("faithfulness_check.v1", fake_check_faithfulness),
    "items.generate_quiz_bank": ("assessment_item_bank.v1", fake_quiz_bank),
    "items.generate_final_bank": ("assessment_item_bank.v1", fake_final_bank),
    "diagnostic.generate_items": ("assessment_item_bank.v1", fake_diagnostic_bank),
    "items.review": ("item_review.v1", fake_item_review),
    "video.collect_candidates": ("video_resource.v1", fake_video_candidates),
}
