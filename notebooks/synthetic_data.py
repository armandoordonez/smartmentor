"""Datos sintéticos para ejecutar ``metrics_cohort1.ipynb`` sin base de datos.

Genera, con una semilla fija, los mismos marcos de datos que entrega
``metrics_data.load_from_database``. No hay personas reales: los identificadores son enteros
consecutivos y los valores salen de distribuciones inventadas. Los números que produce el
cuaderno con estos datos **no son resultados del piloto**; solo demuestran que el cálculo corre
de punta a punta y que los gráficos funcionan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

DEFAULT_SEED = 20260507

TOPICS = [
    ("t_variables", 30),
    ("t_conditionals", 35),
    ("t_loops", 40),
    ("t_functions", 45),
    ("t_data_structures", 50),
]
PREREQUISITES = [
    ("t_variables", "t_conditionals"),
    ("t_conditionals", "t_loops"),
    ("t_variables", "t_functions"),
    ("t_loops", "t_data_structures"),
    ("t_functions", "t_data_structures"),
]
ENGLISH_LEVELS = ["A2", "B1", "B2", "C1"]
TASKS = ["syllabus.structure", "diagnostic.generate_items", "items.review", "content.generate"]


def _syllabus_sets(rng: np.random.Generator) -> pd.DataFrame:
    """Temas y prerrequisitos predichos por la IA frente a los finales del instructor."""
    rows: list[dict[str, object]] = []
    final_topics = [name for name, _ in TOPICS] + ["t_recursion"]
    predicted_topics = [t for t in final_topics if t != "t_recursion"] + ["t_oop"]
    final_prereqs = [f"{a}>{b}" for a, b in PREREQUISITES]
    predicted_prereqs = [p for p in final_prereqs if rng.random() > 0.15] + ["t_loops>t_functions"]
    for kind, side, keys in (
        ("topic", "final", final_topics),
        ("topic", "predicted", predicted_topics),
        ("prerequisite", "final", final_prereqs),
        ("prerequisite", "predicted", predicted_prereqs),
    ):
        rows.extend({"course_id": 1, "kind": kind, "side": side, "key": key} for key in keys)
    return pd.DataFrame(rows)


def _item_annotations(rng: np.random.Generator, n_items: int) -> pd.DataFrame:
    """Dos evaluadores por ítem; el segundo coincide con el primero con probabilidad 0,88."""
    rows: list[dict[str, object]] = []
    for item_id in range(1, n_items + 1):
        first_valid = bool(rng.random() < 0.84)
        for slot in (1, 2):
            agree = slot == 1 or rng.random() < 0.88
            valid = first_valid if agree else not first_valid
            rows.append(
                {
                    "assessment_item_id": item_id,
                    "evaluator_slot": slot,
                    "single_correct": bool(valid or rng.random() < 0.4),
                    "clear_stem": bool(valid or rng.random() < 0.5),
                    "bloom_ok": bool(valid or rng.random() < 0.5),
                    "plausible_distractors": bool(valid or rng.random() < 0.5),
                    "verdict": "valid" if valid else "invalid",
                }
            )
    return pd.DataFrame(rows)


def _cohort(
    rng: np.random.Generator, n_learners: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Inscripciones, pasos de ruta y ganancia pre/post de un piloto de dos brazos."""
    enrollments: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    gains: list[dict[str, object]] = []
    for enrollment_id in range(1, n_learners + 1):
        arm = "personalized" if enrollment_id % 2 == 1 else "fixed"
        ability = float(rng.normal(0.0, 1.0))
        english = str(rng.choice(ENGLISH_LEVELS, p=[0.2, 0.35, 0.3, 0.15]))
        has_resume = bool(rng.random() < 0.6)
        abandoned_at = int(rng.integers(2, 6)) if rng.random() < 0.15 else None
        completed_steps = 0
        for position, (topic, minutes) in enumerate(TOPICS, start=1):
            level = float(np.clip(0.55 + 0.18 * ability + rng.normal(0, 0.1), 0.02, 0.98))
            skipped = arm == "personalized" and level >= 0.8
            row: dict[str, object] = {
                "enrollment_id": enrollment_id,
                "topic_id": topic,
                "position": position,
                "estimated_minutes": minutes,
                "diagnostic_level": level,
                "inclusion_reason": "fixed_path" if arm == "fixed" else "objective_focus",
                "attempts_used": 0,
                "first_attempt_passed": None,
                "passed": False,
                "best_score": None,
                "status": "pending",
            }
            if skipped:
                row.update(inclusion_reason="skipped_mastered", status="skipped")
            elif abandoned_at is not None and position >= abandoned_at:
                row.update(status="pending")
            else:
                p_pass = 1.0 / (1.0 + np.exp(-(3.0 * (level - 0.5) + 0.6 * ability + 0.5)))
                attempts = 0
                passed = False
                first_passed = False
                best = 0.0
                while attempts < 3 and not passed:
                    attempts += 1
                    score = float(np.clip(100 * (level + rng.normal(0.1 * attempts, 0.12)), 0, 100))
                    best = max(best, score)
                    passed = bool(score >= 70 or rng.random() < p_pass * 0.3)
                    if attempts == 1:
                        first_passed = passed
                row.update(
                    attempts_used=attempts,
                    first_attempt_passed=first_passed,
                    passed=passed,
                    best_score=best,
                    status="passed" if passed else "attempts_exhausted",
                )
                completed_steps += int(passed)
            steps.append(row)
        finished = abandoned_at is None
        badge = bool(finished and rng.random() < 0.8)
        enrollments.append(
            {
                "enrollment_id": enrollment_id,
                "pilot_arm": arm,
                "status": "completed" if finished else "abandoned",
                "badge_earned": badge,
                "english_level": english,
                "has_resume": has_resume,
            }
        )
        if finished:
            pre = float(np.clip(45 + 9 * ability + rng.normal(0, 7), 5, 95))
            boost = 24 if arm == "personalized" else 17
            post = float(np.clip(pre + boost + 3 * ability + rng.normal(0, 8), 5, 100))
            gains.append(
                {
                    "enrollment_id": enrollment_id,
                    "pilot_arm": arm,
                    "pre_score": pre,
                    "post_score": post,
                }
            )
    return pd.DataFrame(enrollments), pd.DataFrame(steps), pd.DataFrame(gains)


def _item_responses(rng: np.random.Generator, n_items: int, n_learners: int) -> pd.DataFrame:
    """Respuestas del piloto: cada intento responde 10 ítems al azar del banco."""
    difficulty = rng.uniform(-1.5, 1.5, n_items)
    discrimination = rng.uniform(0.2, 1.6, n_items)
    discrimination[:4] = 0.0  # cuatro ítems defectuosos: no discriminan
    rows: list[dict[str, object]] = []
    attempt_id = 0
    for _ in range(n_learners):
        ability = float(rng.normal(0, 1))
        for _attempt in range(int(rng.integers(2, 5))):
            attempt_id += 1
            for item in rng.choice(n_items, size=10, replace=False):
                p = 1.0 / (1.0 + np.exp(-discrimination[item] * (ability - difficulty[item])))
                rows.append(
                    {
                        "attempt_id": attempt_id,
                        "assessment_item_id": int(item) + 1,
                        "is_correct": int(rng.random() < p),
                    }
                )
    return pd.DataFrame(rows)


def _grading_pairs(rng: np.random.Generator, n_pairs: int) -> pd.DataFrame:
    """Calificación del LLM y de una persona sobre una muestra aleatoria de respuestas cortas."""
    human = np.clip(np.round(rng.beta(2.5, 1.8, n_pairs) * 100 / 25) * 25, 0, 100)
    noise = rng.normal(0, 14, n_pairs)
    llm = np.clip(np.round((human + noise) / 25) * 25, 0, 100)
    return pd.DataFrame(
        {
            "attempt_answer_id": np.arange(1, n_pairs + 1),
            "sample_type": rng.choice(["random", "learner_request"], n_pairs, p=[0.85, 0.15]),
            "llm_score": llm,
            "human_score": human,
        }
    )


def _video_judgments(rng: np.random.Generator) -> pd.DataFrame:
    """Dos jueces sobre los 6 candidatos mejor rankeados de cada tema."""
    rows: list[dict[str, object]] = []
    candidate_id = 0
    for topic, _ in TOPICS:
        for rank in range(1, 7):
            candidate_id += 1
            p_relevant = max(0.2, 0.9 - 0.1 * rank)
            for judge in (1, 2):
                rows.append(
                    {
                        "topic_id": topic,
                        "video_candidate_id": candidate_id,
                        "rank": rank,
                        "judge_id": judge,
                        "is_relevant": bool(rng.random() < p_relevant),
                    }
                )
    return pd.DataFrame(rows)


def _likert(rng: np.random.Generator, quality: float, offset: float, noise: float) -> int:
    return int(np.clip(round(4 * quality + offset + rng.normal(0, noise)), 1, 5))


def _surveys(rng: np.random.Generator, enrollments: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, enrollment in enrollments[enrollments["status"] == "completed"].iterrows():
        quality = float(rng.normal(0.72, 0.1))
        sus_items: list[int] = []
        for index in range(10):
            positive = index % 2 == 0
            target = quality if positive else 1 - quality
            sus_items.append(int(np.clip(round(1 + 4 * target + rng.normal(0, 0.6)), 1, 5)))
        rows.append(
            {
                "enrollment_id": int(enrollment["enrollment_id"]),
                "pilot_arm": enrollment["pilot_arm"],
                "sus_items": sus_items,
                "likert_satisfaction": _likert(rng, quality, 1.0, 0.5),
                "likert_usefulness": _likert(rng, quality, 1.2, 0.5),
                "likert_self_efficacy": _likert(rng, quality, 0.8, 0.6),
            }
        )
    return pd.DataFrame(rows)


def _llm_calls(rng: np.random.Generator, n_calls: int, n_enrollments: int) -> pd.DataFrame:
    task = rng.choice(TASKS, n_calls, p=[0.05, 0.25, 0.3, 0.4])
    base = {"syllabus.structure": 9.0, "diagnostic.generate_items": 7.0, "items.review": 4.0}
    scale = np.array([base.get(str(t), 6.0) for t in task])
    latency_ms = rng.lognormal(np.log(scale * 1000), 0.45)
    return pd.DataFrame(
        {
            "ai_job_id": np.arange(1, n_calls + 1),
            "task": task,
            "enrollment_id": rng.integers(1, n_enrollments + 1, n_calls),
            "json_valid": rng.random(n_calls) > 0.012,
            "from_cache": rng.random(n_calls) < 0.08,
            "status": np.where(rng.random(n_calls) > 0.01, "success", "invalid_output"),
            "cost_usd": np.round(rng.gamma(2.0, 0.0009, n_calls), 6),
            "latency_ms": np.round(latency_ms, 1),
        }
    )


def _resources(rng: np.random.Generator, n_resources: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "resource_id": np.arange(1, n_resources + 1),
            "faithfulness": np.clip(rng.normal(0.88, 0.08, n_resources), 0, 1).round(3),
        }
    )


EVENTS_START = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)
SEGMENT_CAP_SECONDS = 3600  # igual que la app (app/src/core/usage_events.py)


class _EventLog:
    """Eventos de una inscripción en orden, con el reloj y el formato de la app."""

    def __init__(self, enrollment_id: int, start: datetime) -> None:
        self.enrollment_id = enrollment_id
        self.now = start
        self.rows: list[dict[str, object]] = []

    def emit(self, event_type: str, topic_id: str | None, payload: dict[str, object]) -> None:
        self.rows.append(
            {
                "enrollment_id": self.enrollment_id,
                "event_type": event_type,
                "topic_id": topic_id,
                "payload": payload,
                "occurred_at": self.now,
            }
        )

    def visit(
        self,
        open_type: str | None,
        close_type: str | None,
        topic_id: str | None,
        payload: dict[str, object],
        seconds: float,
        shown: dict[str, object] | None = None,
    ) -> None:
        """Abre una visita y, si ``close_type`` no es nulo, la cierra tras ``seconds``.

        ``shown`` es el ``resource.view`` que sale con la misma hora que la apertura.
        """
        started = self.now
        if open_type is not None:
            self.emit(open_type, topic_id, dict(payload))
        if shown is not None:
            self.emit("resource.view", topic_id, {**payload, **shown})
        self.now = started + timedelta(seconds=float(seconds))
        if close_type is None:  # pestaña cerrada: tramo abierto
            return
        elapsed = round(seconds)
        body: dict[str, object] = {
            **payload,
            "seconds": min(elapsed, SEGMENT_CAP_SECONDS),
            "started_at": started.isoformat(),
        }
        if elapsed > SEGMENT_CAP_SECONDS:
            body["capped"] = True
        self.emit(close_type, topic_id, body)

    def wait(self, seconds: float) -> None:
        self.now += timedelta(seconds=float(seconds))


def _interaction_events(
    rng: np.random.Generator, enrollments: pd.DataFrame, path_steps: pd.DataFrame
) -> pd.DataFrame:
    """Eventos de uso (``POST /me/events``) coherentes con los pasos y los intentos sintéticos.

    Incluye los casos que trata la regla de m27: tramos recortados (``capped``), tramos abiertos
    (pestaña cerrada sin cierre) y un cierre duplicado (el endpoint no es idempotente).
    """
    rows: list[dict[str, object]] = []
    attempt_id = 0
    for _, enrollment in enrollments.iterrows():
        enrollment_id = int(enrollment["enrollment_id"])
        log = _EventLog(enrollment_id, EVENTS_START + timedelta(hours=int(rng.integers(0, 72))))
        steps = path_steps[path_steps["enrollment_id"] == enrollment_id].sort_values("position")
        path_payload: dict[str, object] = {"screen": "E5", "steps_total": len(steps)}
        for _, step in steps.iterrows():
            log.visit("path.view", "path.close", None, path_payload, rng.uniform(20, 150))
            attempts = int(step["attempts_used"])
            if attempts == 0:
                continue
            topic_id = str(step["topic_id"])
            step_id = 100 * enrollment_id + int(step["position"])
            for attempt_number in range(1, attempts + 1):
                topic_payload: dict[str, object] = {
                    "screen": "E6",
                    "step_id": step_id,
                    "step_status": "in_progress",
                }
                minutes = float(step["estimated_minutes"]) * rng.lognormal(-0.4, 0.5)
                if attempt_number > 1:
                    minutes *= 0.4  # repaso antes de otro intento
                closes = rng.random() > 0.06
                log.visit(
                    "topic.open",
                    "topic.close" if closes else None,
                    topic_id,
                    topic_payload,
                    minutes * 60,
                    shown={"resource": "explanation", "resource_id": step_id},
                )
                if not closes:
                    log.wait(rng.uniform(3600, 86400))  # vuelve otro día
                attempt_id += 1
                quiz_payload: dict[str, object] = {
                    "screen": "E6b",
                    "attempt_id": attempt_id,
                    "step_id": step_id,
                    "attempt_number": attempt_number,
                }
                log.emit("quiz.start", topic_id, dict(quiz_payload))
                if rng.random() < 0.2:  # sale a mitad del quiz y vuelve
                    log.visit(None, "quiz.pause", topic_id, quiz_payload, rng.uniform(60, 300))
                    log.wait(rng.uniform(300, 7200))
                submit = {**quiz_payload, "items": 5, "grading": "done"}
                log.visit(None, "quiz.submit", topic_id, submit, rng.uniform(240, 900))
                log.wait(rng.uniform(30, 600))
        if enrollment["status"] == "completed":
            attempt_id += 1
            final_payload: dict[str, object] = {
                "screen": "E8",
                "attempt_id": attempt_id,
                "attempt_number": 1,
            }
            log.emit("final.start", None, dict(final_payload))
            final_body = {**final_payload, "items": 10, "grading": "done"}
            log.visit(None, "final.submit", None, final_body, rng.uniform(900, 2400))
        rows.extend(log.rows)
    closes = [i for i, r in enumerate(rows) if r["event_type"] == "topic.close"]
    if closes:
        rows.append(dict(rows[closes[0]]))  # reintento tras un 503 que sí había llegado
    columns = ["enrollment_id", "event_type", "topic_id", "payload", "occurred_at"]
    return pd.DataFrame(rows, columns=columns)


def generate(seed: int = DEFAULT_SEED, n_learners: int = 24) -> dict[str, pd.DataFrame]:
    """Genera todos los marcos de datos que consume el cuaderno, de forma determinista."""
    rng = np.random.default_rng(seed)
    n_items = 80
    enrollments, path_steps, learning_gain = _cohort(rng, n_learners)
    return {
        "syllabus_sets": _syllabus_sets(rng),
        "item_annotations": _item_annotations(rng, n_items),
        "item_responses": _item_responses(rng, n_items, n_learners),
        "grading_pairs": _grading_pairs(rng, 60),
        "video_judgments": _video_judgments(rng),
        "enrollments": enrollments,
        "path_steps": path_steps,
        "learning_gain": learning_gain,
        "surveys": _surveys(rng, enrollments),
        "llm_calls": _llm_calls(rng, 400, n_learners),
        "resources": _resources(rng, 40),
        # Generador aparte para no cambiar los demás marcos de la misma semilla.
        "interaction_events": _interaction_events(
            np.random.default_rng(seed + 27), enrollments, path_steps
        ),
    }
