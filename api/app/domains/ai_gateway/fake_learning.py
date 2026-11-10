"""Salidas deterministas de `FakeAiService` para la ruta del aprendiz (sin red ni LLM).

Imitan las reglas de `ai/` (nivel ponderado por dificultad, secuenciación topológica, calificación
por criterios) para que las pruebas recorran el flujo completo. La prueba de contrato valida cada
salida contra `prompts/schemas/*.json`.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

FAKE_ALGORITHM_LEVELS = "weighted_difficulty v1"
FAKE_ALGORITHM_PATH = "topological_threshold v1"
REINFORCE_CUTOFF = 50.0


def _meta(prompt_id: str, payload: Any) -> dict[str, Any]:
    seed = json.dumps(payload, sort_keys=True, default=str)
    return {
        "prompt_id": prompt_id,
        "prompt_version": "v1",
        "model": "fake-model",
        "generated_at": datetime(2026, 11, 7, 15, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "input_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "from_cache": False,
    }


def _weights(input_: dict[str, Any]) -> dict[str, float]:
    raw = input_.get("weights") or {"test": 0.8, "profile": 0.1, "resume": 0.1}
    return {k: float(raw.get(k, 0)) for k in ("test", "profile", "resume")}


def fake_levels_estimate(input_: dict[str, Any]) -> dict[str, Any]:
    """`levels.estimate`: aciertos ponderados por dificultad; «No lo sé» es no acierto.

    El fake no calcula similitud de perfil: todo el peso queda en la prueba (redistribución).
    """
    thresholds = input_.get("thresholds") or {}
    skip = float(thresholds.get("mastery_skip_threshold", 80))
    cutoff = float(thresholds.get("reinforce_cutoff", REINFORCE_CUTOFF))
    answers = {str(a["item_id"]): a for a in input_.get("answers", [])}
    levels: list[dict[str, Any]] = []
    for topic_id in input_["topic_ids"]:
        items = [i for i in input_.get("items", []) if str(i["topic_id"]) == str(topic_id)]
        total = sum(int(i.get("difficulty", 1)) for i in items)
        hits = 0
        for item in items:
            answer = answers.get(str(item["item_id"]))
            if (
                answer is not None
                and not answer.get("dont_know")
                and item.get("correct_option") is not None
                and answer.get("selected_option") == item.get("correct_option")
            ):
                hits += int(item.get("difficulty", 1))
        score = round(100 * hits / total, 2) if total else None
        level = score if score is not None else 0.0
        classification = (
            "mastered" if level >= skip else "to_reinforce" if level >= cutoff else "to_learn"
        )
        levels.append(
            {
                "topic_id": str(topic_id),
                "test_score": score,
                "profile_similarity": None,
                "profile_prior": None,
                "resume_prior": None,
                "weights": {"test": 1.0, "profile": 0.0, "resume": 0.0},
                "level": level,
                "classification": classification,
            }
        )
    overall = round(sum(t["level"] for t in levels) / len(levels), 2) if levels else 0.0
    return {
        "algorithm": FAKE_ALGORITHM_LEVELS,
        "configured_weights": _weights(input_),
        "thresholds": {"mastery_skip_threshold": skip, "reinforce_cutoff": cutoff},
        "level_by_topic": levels,
        "overall_score": overall,
    }


def fake_diagnostic_finalize(input_: dict[str, Any]) -> dict[str, Any]:
    """`diagnostic.finalize`: niveles más el objetivo (de la ruta o «propuesto por el LLM»)."""
    result = fake_levels_estimate(input_)
    gaps = [t["topic_id"] for t in result["level_by_topic"] if t["classification"] != "mastered"]
    parts = input_.get("path_objective_parts")
    if input_.get("objective_mode") == "path_default" and parts:
        objective = {
            "origin": "path_default",
            "statement": input_.get("path_objective") or " ".join(parts.values()),
            "bloom_verb": parts["bloom_verb"],
            "content": parts["content"],
            "criterion": parts["criterion"],
            "focus_topics": gaps,
            "rationale": "Objetivo por defecto de la ruta.",
            "meta": None,
        }
    else:
        objective = {
            "origin": "llm_proposed",
            "statement": (
                "Aplicar los temas de la ruta a un caso de tu trabajo con al menos 80 % en la "
                "evaluación final"
            ),
            "bloom_verb": "Aplicar",
            "content": "los temas de la ruta a un caso de tu trabajo",
            "criterion": "con al menos 80 % en la evaluación final",
            "focus_topics": gaps,
            "rationale": "Se enfoca en los temas con menor nivel en el diagnóstico.",
            "meta": _meta("learning_objective", input_),
        }
    return {"diagnostic_result": result, "objective": objective}


def fake_path_sequence(input_: dict[str, Any]) -> dict[str, Any]:
    """`path.sequence`: orden topológico que respeta `position`; omite lo dominado no obligatorio."""
    topics = sorted(
        enumerate(input_["topics"]), key=lambda pair: (pair[1].get("position", 0), pair[0])
    )
    by_id = {t["topic_id"]: t for _, t in topics}
    levels = {lv["topic_id"]: float(lv["level"]) for lv in input_.get("level_by_topic", [])}
    threshold = float(input_["mastery_skip_threshold"])
    fixed = input_.get("pilot_arm") == "fixed"
    order: list[str] = []
    pending = [t["topic_id"] for _, t in topics]
    while pending:
        for topic_id in pending:
            if all(p in order or p not in by_id for p in by_id[topic_id].get("prerequisites", [])):
                order.append(topic_id)
                pending.remove(topic_id)
                break
        else:  # ciclo: el fake no lo valida, conserva el orden del syllabus
            order.extend(pending)
            break
    skipped = {
        t
        for t in order
        if not fixed
        and not by_id[t].get("is_mandatory")
        and t in levels
        and levels[t] >= threshold
    }
    included = [t for t in order if t not in skipped]
    prerequisite_of_included = {p for t in included for p in by_id[t].get("prerequisites", [])}
    focus = set(input_.get("focus_topic_ids", []))
    steps = []
    for number, topic_id in enumerate(order, start=1):
        topic = by_id[topic_id]
        if topic_id in skipped:
            status, reason = "skipped", "skipped_mastered"
        else:
            waiting = any(p not in skipped for p in topic.get("prerequisites", []))
            status = "blocked" if waiting else "pending"
            if fixed:
                reason = "fixed_path"
            elif topic.get("is_mandatory"):
                reason = "mandatory"
            elif topic_id in focus:
                reason = "objective_focus"
            elif topic_id in prerequisite_of_included:
                reason = "weak_prerequisite"
            else:
                reason = "required_by_path"
        steps.append(
            {
                "step_order": number,
                "topic_id": topic_id,
                "status": status,
                "inclusion_reason": reason,
                "diagnostic_level": levels.get(topic_id),
            }
        )
    return {
        "algorithm": FAKE_ALGORITHM_PATH,
        "mastery_skip_threshold": threshold,
        "pilot_arm": input_.get("pilot_arm"),
        "steps": steps,
    }


def fake_grade_short_answer(input_: dict[str, Any]) -> dict[str, Any]:
    """`grading.short_answer`: un criterio se cumple si su primera palabra aparece en la respuesta."""
    answer = str(input_.get("answer_text") or "").casefold()
    ratio = float(input_.get("min_criteria_ratio") or 2 / 3)
    detail = []
    for criterion in input_.get("rubric", []):
        keyword = str(criterion["criterion"]).split()[0].casefold() if criterion["criterion"] else ""
        met = bool(keyword) and keyword in answer
        points = float(criterion["points"])
        detail.append(
            {
                "criterion": criterion["criterion"],
                "met": met,
                "points": points,
                "points_awarded": points if met else 0.0,
                "evidence": "Aparece en la respuesta." if met else "No aparece en la respuesta.",
            }
        )
    met_count = sum(1 for d in detail if d["met"])
    total = len(detail)
    score = round(100 * sum(d["points_awarded"] for d in detail), 2)
    return {
        "item_id": str(input_["item_id"]),
        "item_type": "short_answer",
        "grader": "llm_judge",
        "approval_rule": "min_criteria_ratio",
        "min_criteria_ratio": ratio,
        "score": min(score, 100.0),
        "is_correct": total > 0 and met_count / total >= ratio - 1e-9,
        "criteria_met": met_count,
        "criteria_total": total,
        "rubric_detail": detail,
        "feedback": "Revisa los criterios que no se cumplieron.",
        "meta": _meta("short_answer_grading", input_),
    }


def fake_quiz_bank(input_: dict[str, Any]) -> dict[str, Any]:
    """`items.generate_quiz_bank`: ítems nuevos del tema (el último de cada lote es respuesta corta)."""
    topic_id = str(input_["topic_id"])
    n_choice = int(input_.get("n_multiple_choice", 4))
    n_short = int(input_.get("n_short_answer", 1))
    offset = len(input_.get("previous_stems", []))
    items: list[dict[str, Any]] = []
    for n in range(n_choice + n_short):
        number = offset + n + 1
        short = n >= n_choice
        items.append(
            {
                "id": f"q{number}",
                "topic_id": topic_id,
                "outcome_id": "",
                "source": "topic_quiz",
                "item_type": "short_answer" if short else "multiple_choice",
                "bloom_level": "apply" if short else "understand",
                "difficulty": 2 if short else 1,
                "stem": f"Pregunta generada {number} del tema {topic_id}",
                "options": [] if short else ["Opción A", "Opción B", "Opción C", "Opción D"],
                "correct_option": None if short else number % 4,
                "model_answer": "Concepto clave, ejemplo y conclusión.",
                "rubric": (
                    [
                        {"criterion": "concepto clave", "points": 0.4},
                        {"criterion": "ejemplo aplicado", "points": 0.3},
                        {"criterion": "conclusión clara", "points": 0.3},
                    ]
                    if short
                    else []
                ),
                "equivalence_group": None,
            }
        )
    return {
        "topic_id": topic_id,
        "items": items,
        "item_reviews": [
            {
                "item_id": item["id"],
                "single_correct_answer": True,
                "clear_stem": True,
                "bloom_matches": True,
                "aligned_with_outcome": True,
                "issues": [],
            }
            for item in items
        ],
        "discarded_item_ids": [],
        "meta": _meta("topic_quiz", input_),
    }


LEARNING_JOB_RESULTS: dict[str, tuple[str, Any]] = {
    "diagnostic.finalize": ("diagnostic_finalization.v1", fake_diagnostic_finalize),
    "grading.short_answer": ("grading.v1", fake_grade_short_answer),
    "items.generate_quiz_bank": ("assessment_item_bank.v1", fake_quiz_bank),
}

LEARNING_TASK_RESULTS: dict[str, Any] = {
    "levels.estimate": fake_levels_estimate,
    "path.sequence": fake_path_sequence,
}
