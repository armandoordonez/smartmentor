"""Carga de datos de ``metrics_cohort1.ipynb``.

``load_from_database`` lee la base con un usuario de **solo lectura** y devuelve los mismos marcos
de datos que ``synthetic_data.generate``. La URL llega por la variable de entorno
``METRICS_DATABASE_URL`` (nunca se escribe en el cuaderno ni en el repositorio).

Las consultas usan los nombres de columna de la sección 5.2.1 del plan (esquema ``v2.0.0``).
Los puntos que dependen de columnas que el plan no fija del todo están marcados con
``SUPUESTO`` y se verifican contra el changelog real al ejecutar la cohorte 1.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

ENV_VAR = "METRICS_DATABASE_URL"

# Solo se incluyen inscripciones marcadas para análisis (enrollments.analysis_included).
QUERIES: dict[str, str] = {
    # Temas y prerrequisitos: salida actual de la IA frente a lo que dejó el instructor.
    "syllabus_sets": """
        WITH predicted_topics AS (
            SELECT e.course_id, t.value ->> 'id' AS topic_key, t.value -> 'prerequisites' AS prereqs
            FROM syllabus_extractions e
            CROSS JOIN LATERAL jsonb_array_elements(e.raw_output -> 'topics') AS t(value)
            WHERE e.is_current
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
        SELECT p.course_id, 'prerequisite', 'predicted', pre.value #>> '{}' || '>' || p.topic_key
        FROM predicted_topics p
        CROSS JOIN LATERAL jsonb_array_elements(p.prereqs) AS pre(value)
        UNION ALL
        SELECT t.course_id, 'prerequisite', 'final', pre.topic_key || '>' || t.topic_key
        FROM topic_prerequisites tp
        JOIN final_topics t ON t.id = tp.topic_id
        JOIN final_topics pre ON pre.id = tp.prerequisite_topic_id
    """,
    "item_annotations": """
        SELECT assessment_item_id, evaluator_slot, single_correct, clear_stem, bloom_ok,
               plausible_distractors, verdict
        FROM item_annotations
    """,
    # SUPUESTO: attempt_answers.assessment_attempt_id y is_correct; solo intentos de la cohorte.
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
        WHERE aa.grader = 'llm_judge' AND aa.score IS NOT NULL
    """,
    # SUPUESTO: video_candidates.rank es la posición dentro del tema.
    "video_judgments": """
        SELECT vc.topic_id::text AS topic_id, vc.id AS video_candidate_id, vc.rank,
               j.judge_user_id AS judge_id, j.is_relevant
        FROM video_relevance_judgments j
        JOIN video_candidates vc ON vc.id = j.video_candidate_id
    """,
    # SUPUESTO: el nivel de inglés sale de user_profiles.languages (código 'en').
    "enrollments": """
        SELECT en.id AS enrollment_id, en.pilot_arm, en.status,
               EXISTS (SELECT 1 FROM badges b
                        WHERE b.enrollment_id = en.id AND b.active) AS badge_earned,
               (SELECT l ->> 'cefr_level'
                  FROM jsonb_array_elements(up.languages) AS l
                 WHERE l ->> 'code' = 'en' LIMIT 1) AS english_level,
               (up.resume_completed_at IS NOT NULL) AS has_resume
        FROM enrollments en
        LEFT JOIN user_profiles up ON up.user_id = en.user_id
        WHERE en.analysis_included
    """,
    # SUPUESTO: path_steps trae enrollment_id, topic_id, position, estimated_minutes (del tema),
    # y el primer intento se deduce de attempts_used > 0 con la primera nota guardada en
    # first_attempt_passed (a confirmar con la API; si no existe, se calcula desde
    # assessment_attempts).
    "path_steps": """
        SELECT ps.enrollment_id, ps.topic_id::text AS topic_id, ps.position,
               tp.estimated_minutes, ps.diagnostic_level, ps.inclusion_reason,
               ps.attempts_used, ps.first_attempt_passed,
               (ps.status = 'approved') AS passed, ps.best_score, ps.status
        FROM path_steps ps
        JOIN topics tp ON tp.id = ps.topic_id
        JOIN enrollments en ON en.id = ps.enrollment_id
        WHERE en.analysis_included
    """,
    # Pre-test: promedio de test_score del diagnóstico (0 a 1) por 100. Post-test: mejor nota
    # de la evaluación final.
    "learning_gain": """
        SELECT en.id AS enrollment_id, en.pilot_arm,
               100 * (SELECT AVG((v.value ->> 'test_score')::float)
                        FROM jsonb_each(d.level_by_topic) AS v) AS pre_score,
               (SELECT MAX(a.score) FROM assessment_attempts a
                 WHERE a.enrollment_id = en.id AND a.assessment_type = 'final') AS post_score
        FROM enrollments en
        JOIN diagnostics d ON d.enrollment_id = en.id
        WHERE en.analysis_included
    """,
    "surveys": """
        SELECT sr.enrollment_id, en.pilot_arm, sr.sus_items,
               (sr.likert ->> 'satisfaction')::int AS likert_satisfaction,
               (sr.likert ->> 'usefulness')::int AS likert_usefulness,
               (sr.likert ->> 'self_efficacy')::int AS likert_self_efficacy
        FROM survey_responses sr
        JOIN enrollments en ON en.id = sr.enrollment_id
        WHERE sr.survey_type = 'final' AND en.analysis_included
    """,
    # SUPUESTO: ai_jobs.enrollment_id existe y puede ser nulo (trabajos de curso).
    "llm_calls": """
        SELECT l.ai_job_id, l.task, j.enrollment_id, l.json_valid, l.from_cache, l.status,
               l.cost_usd, l.latency_ms
        FROM llm_call_logs l
        LEFT JOIN ai_jobs j ON j.id = l.ai_job_id
    """,
    "resources": """
        SELECT id AS resource_id, faithfulness FROM resources WHERE faithfulness IS NOT NULL
    """,
}


def load_from_database(url: str | None = None) -> dict[str, pd.DataFrame]:
    """Ejecuta ``QUERIES`` en una transacción de solo lectura.

    Raises:
        RuntimeError: si no hay URL (argumento ni variable de entorno).
    """
    from sqlalchemy import create_engine, text

    resolved = url or os.environ.get(ENV_VAR)
    if not resolved:
        raise RuntimeError(f"Falta {ENV_VAR} en el entorno")
    engine = create_engine(resolved)
    frames: dict[str, pd.DataFrame] = {}
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
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
