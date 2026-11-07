"""Carga de datos de ``metrics_cohort1.ipynb``.

``load_from_database`` lee la base con el usuario de **solo lectura** ``smartmentor_metrics``
(ADR 0019; sus permisos los da el changeset ``v2.0.0-049``) y devuelve los mismos marcos de datos
que ``synthetic_data.generate``. La URL llega por la variable de entorno ``METRICS_DATABASE_URL``
(nunca se escribe en el cuaderno ni en el repositorio); el usuario y la clave de ese rol son
``METRICS_DATABASE_USER`` y ``METRICS_DATABASE_PASSWORD`` del ``.env``.

Las consultas se contrastaron con el esquema ``v2.0.0`` (rama ``feature/database-v2-rebase``). Dos
columnas son ``jsonb`` libres que fija la API, no el esquema, y quedan marcadas ``SUPUESTO``:
``diagnostics.level_by_topic`` y ``survey_responses.likert``. ``check_shapes`` falla con un mensaje
claro si la forma real es otra.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

ENV_VAR = "METRICS_DATABASE_URL"


class UnexpectedShapeError(RuntimeError):
    """Un ``jsonb`` libre no tiene la forma que el cuaderno espera."""


LIKERT_KEYS = ("satisfaction", "usefulness", "self_efficacy")

# Solo se incluyen inscripciones marcadas para análisis (enrollments.analysis_included).
QUERIES: dict[str, str] = {
    # Temas y prerrequisitos: salida actual de la IA frente a lo que dejó el instructor.
    "syllabus_sets": """
        WITH predicted_topics AS (
            SELECT e.course_id, t.value ->> 'id' AS topic_key, t.value -> 'prerequisites' AS prereqs
            FROM syllabus_extractions e
            CROSS JOIN LATERAL jsonb_array_elements(e.raw_output -> 'topics') AS t(value)
            WHERE e.is_current AND e.active
        ),
        final_topics AS (
            SELECT course_id, id,
                   COALESCE(extraction_key, 'added:' || id::text) AS topic_key
            FROM topics
            WHERE review_status <> 'deleted' AND active
        )
        SELECT course_id, 'topic' AS kind, 'predicted' AS side, topic_key AS key
        FROM predicted_topics
        UNION ALL
        SELECT course_id, 'topic', 'final', topic_key FROM final_topics
        UNION ALL
        SELECT p.course_id, 'prerequisite', 'predicted', (pre.value #>> '{}') || '>' || p.topic_key
        FROM predicted_topics p
        CROSS JOIN LATERAL jsonb_array_elements(p.prereqs) AS pre(value)
        UNION ALL
        SELECT t.course_id, 'prerequisite', 'final', pre.topic_key || '>' || t.topic_key
        FROM topic_prerequisites tp
        JOIN final_topics t ON t.id = tp.topic_id
        JOIN final_topics pre ON pre.id = tp.prerequisite_topic_id
        WHERE tp.active
    """,
    "item_annotations": """
        SELECT assessment_item_id, evaluator_slot, single_correct, clear_stem, bloom_ok,
               plausible_distractors, verdict
        FROM item_annotations
        WHERE active
    """,
    # Respuestas calificadas de intentos de la cohorte; is_correct nulo = sin calificar.
    "item_responses": """
        SELECT aa.assessment_attempt_id AS attempt_id, aa.assessment_item_id,
               aa.is_correct::int AS is_correct
        FROM attempt_answers aa
        JOIN assessment_attempts at ON at.id = aa.assessment_attempt_id
        JOIN enrollments en ON en.id = at.enrollment_id
        WHERE en.analysis_included AND aa.is_correct IS NOT NULL
    """,
    "grading_pairs": """
        SELECT aa.id AS attempt_answer_id, hg.sample_type, aa.score AS llm_score,
               hg.score AS human_score
        FROM human_gradings hg
        JOIN attempt_answers aa ON aa.id = hg.attempt_answer_id
        WHERE aa.grader = 'llm_judge' AND aa.score IS NOT NULL AND hg.active
    """,
    # video_candidates.rank es la posición dentro del tema (puede ser nula en candidatos nuevos).
    "video_judgments": """
        SELECT vc.topic_id::text AS topic_id, vc.id AS video_candidate_id, vc.rank,
               j.judge_user_id AS judge_id, j.is_relevant
        FROM video_relevance_judgments j
        JOIN video_candidates vc ON vc.id = j.video_candidate_id
        WHERE j.active AND vc.rank IS NOT NULL
    """,
    # El nivel de inglés sale de user_profiles.languages (código 'en'); puede ser nulo.
    "enrollments": """
        SELECT en.id AS enrollment_id, en.pilot_arm, en.status,
               EXISTS (SELECT 1 FROM badges b
                        WHERE b.enrollment_id = en.id AND b.active) AS badge_earned,
               (SELECT l ->> 'cefr_level'
                  FROM jsonb_array_elements(COALESCE(up.languages, '[]'::jsonb)) AS l
                 WHERE l ->> 'code' = 'en' LIMIT 1) AS english_level,
               (up.resume_completed_at IS NOT NULL) AS has_resume
        FROM enrollments en
        LEFT JOIN user_profiles up ON up.user_id = en.user_id
        WHERE en.analysis_included
    """,
    # path_steps no guarda el primer intento: se toma de assessment_attempts (attempt_number = 1
    # del quiz del tema; nulo si todavía no está calificado). El estado aprobado es 'passed'.
    "path_steps": """
        SELECT ps.enrollment_id, ps.topic_id::text AS topic_id, ps.step_order AS position,
               tp.estimated_minutes, ps.diagnostic_level, ps.inclusion_reason,
               ps.attempts_used, fa.passed AS first_attempt_passed,
               (ps.status = 'passed') AS passed, ps.best_score, ps.status
        FROM path_steps ps
        JOIN topics tp ON tp.id = ps.topic_id
        JOIN enrollments en ON en.id = ps.enrollment_id
        LEFT JOIN assessment_attempts fa
               ON fa.path_step_id = ps.id AND fa.assessment_type = 'topic'
              AND fa.attempt_number = 1 AND fa.active
        WHERE en.analysis_included AND ps.active
    """,
    # SUPUESTO: diagnostics.level_by_topic es un objeto con el id del tema como clave y, por
    # tema, test_score entre 0 y 1 (plan 5.2.1). Pre-test = media de test_score por 100.
    # Post-test: mejor nota de la evaluación final (assessment_type = 'final').
    "learning_gain": """
        SELECT en.id AS enrollment_id, en.pilot_arm,
               100 * (SELECT AVG((v.value ->> 'test_score')::float)
                        FROM jsonb_each(
                               CASE WHEN jsonb_typeof(d.level_by_topic) = 'object'
                                    THEN d.level_by_topic ELSE '{}'::jsonb END) AS v
                     ) AS pre_score,
               (SELECT MAX(a.score) FROM assessment_attempts a
                 WHERE a.enrollment_id = en.id AND a.assessment_type = 'final') AS post_score
        FROM enrollments en
        JOIN diagnostics d ON d.enrollment_id = en.id
        WHERE en.analysis_included AND d.active
    """,
    # SUPUESTO: survey_responses.likert es un objeto con las claves de LIKERT_KEYS (1 a 5).
    "surveys": """
        SELECT sr.enrollment_id, en.pilot_arm, sr.sus_items,
               (sr.likert ->> 'satisfaction')::int AS likert_satisfaction,
               (sr.likert ->> 'usefulness')::int AS likert_usefulness,
               (sr.likert ->> 'self_efficacy')::int AS likert_self_efficacy
        FROM survey_responses sr
        JOIN enrollments en ON en.id = sr.enrollment_id
        WHERE sr.survey_type = 'final' AND en.analysis_included AND sr.active
          AND sr.sus_items IS NOT NULL
    """,
    # ai_jobs.enrollment_id es nulo en los trabajos de curso. Los estados de llm_call_logs son
    # success, error, invalid_output y budget_exceeded.
    "llm_calls": """
        SELECT l.ai_job_id, l.task, COALESCE(l.enrollment_id, j.enrollment_id) AS enrollment_id,
               l.json_valid, l.from_cache, l.status, l.cost_usd, l.latency_ms
        FROM llm_call_logs l
        LEFT JOIN ai_jobs j ON j.id = l.ai_job_id
    """,
    "resources": """
        SELECT id AS resource_id, faithfulness FROM resources
        WHERE faithfulness IS NOT NULL AND active
    """,
}

# Comprobaciones de forma de los jsonb libres: cada una devuelve (filas malas, filas totales).
SHAPE_CHECKS: dict[str, tuple[str, str]] = {
    "diagnostics.level_by_topic": (
        """
        SELECT COUNT(*) FILTER (WHERE jsonb_typeof(level_by_topic) <> 'object'
                                   OR EXISTS (SELECT 1 FROM jsonb_each(
                                          CASE WHEN jsonb_typeof(level_by_topic) = 'object'
                                               THEN level_by_topic ELSE '{}'::jsonb END) v
                                       WHERE jsonb_typeof(v.value) <> 'object'
                                          OR (v.value ->> 'test_score') IS NULL)),
               COUNT(*)
        FROM diagnostics WHERE level_by_topic IS NOT NULL AND active
        """,
        "un objeto {id_del_tema: {test_score: 0..1, ...}}",
    ),
    "survey_responses.likert": (
        """
        SELECT COUNT(*) FILTER (WHERE jsonb_typeof(likert) <> 'object'
                                   OR NOT (likert ?& ARRAY['satisfaction', 'usefulness',
                                                           'self_efficacy'])),
               COUNT(*)
        FROM survey_responses WHERE likert IS NOT NULL AND active
        """,
        "un objeto con las claves satisfaction, usefulness y self_efficacy (1 a 5)",
    ),
}


def check_shapes(connection: Any) -> None:
    """Falla con un mensaje claro si un ``jsonb`` libre no tiene la forma esperada.

    Raises:
        UnexpectedShapeError: si alguna fila no cumple la forma (se indica cuántas y cuál es
            la forma esperada). No incluye valores de las filas.
    """
    from sqlalchemy import text

    problems: list[str] = []
    for name, (sql, expected) in SHAPE_CHECKS.items():
        bad, total = connection.execute(text(sql)).one()
        if bad:
            problems.append(f"{name}: {bad} de {total} filas no son {expected}")
    if problems:
        raise UnexpectedShapeError(
            "La forma de datos de la API no coincide con la que espera el cuaderno. "
            + "; ".join(problems)
            + ". Ajuste las consultas de metrics_data.py (marcadas SUPUESTO) a la forma real."
        )


def load_from_database(url: str | None = None) -> dict[str, pd.DataFrame]:
    """Ejecuta ``QUERIES`` en una transacción de solo lectura.

    Raises:
        RuntimeError: si no hay URL (argumento ni variable de entorno).
        UnexpectedShapeError: si un ``jsonb`` libre no tiene la forma esperada.
    """
    from sqlalchemy import create_engine, text

    resolved = url or os.environ.get(ENV_VAR)
    if not resolved:
        raise RuntimeError(f"Falta {ENV_VAR} en el entorno")
    engine = create_engine(resolved)
    frames: dict[str, pd.DataFrame] = {}
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        check_shapes(connection)
        for name, sql in QUERIES.items():
            frames[name] = pd.read_sql_query(text(sql), connection)
    engine.dispose()
    return frames


def load(prefer_database: bool = True, seed: int | None = None) -> tuple[dict[str, Any], str]:
    """Devuelve ``(marcos, modo)``: ``'database'`` si hay URL, si no ``'synthetic'``."""
    if prefer_database and os.environ.get(ENV_VAR):
        return load_from_database(), "database"
    import synthetic_data

    frames = synthetic_data.generate() if seed is None else synthetic_data.generate(seed)
    return frames, "synthetic"
