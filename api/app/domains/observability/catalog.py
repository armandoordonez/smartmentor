"""Catálogo de métricas del brief para AD3: meta, prioridad y estado de cada una.

Decidir si una métrica «cumple» es una regla de evaluación, así que vive en la API (ADR 0017) y no
en la interfaz. Las metas salen de `docs/evaluation/metrics.md` y las métricas, de la pantalla AD3
de Figma. Lo que la API todavía no calcula en SQL (lo del notebook, la encuesta o el piloto) sale como
`no_data`: sin muestra no hay valor.

Cada métrica: `code`, `name`, `priority` (P1 a P3, la del brief), `status` (`meets`, `not_met`,
`report` o `no_data`), `value` (número o `None`), `unit` (cómo la muestra la interfaz), `goal`
(texto de la meta) y `detail` (tamaño de la muestra o de dónde sale).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domains.observability.service import EvaluationMetrics

MetricCheck = Callable[[float], bool]

NOT_COMPUTED = "Todavía no se calcula en la API (notebook o piloto)"


def _at_least(limit: float) -> MetricCheck:
    return lambda value: value >= limit


def _below(limit: float) -> MetricCheck:
    return lambda value: value < limit


def _at_most(limit: float) -> MetricCheck:
    return lambda value: value <= limit


def _between(low: float, high: float) -> MetricCheck:
    return lambda value: low <= value <= high


@dataclass(frozen=True)
class MetricDef:
    code: str
    name: str
    priority: str
    unit: str
    goal: str
    check: MetricCheck | None = None
    """`None`: solo se reporta (no tiene meta numérica)."""


SYSTEM: tuple[MetricDef, ...] = (
    MetricDef("m1", "F1 de temas y prerrequisitos", "P3", "ratio", "≥ 0,85", _at_least(0.85)),
    MetricDef("m2", "Preguntas válidas", "P3", "percent", "≥ 80 %", _at_least(0.8)),
    MetricDef("m3", "Acuerdo entre expertos (κ)", "P3", "ratio", "≥ 0,6", _at_least(0.6)),
    MetricDef("m4", "Discriminación de ítems", "P1", "ratio", "≥ 0,2", _at_least(0.2)),
    MetricDef("m5", "Fidelidad del RAG", "P3", "ratio", "≥ 0,8", _at_least(0.8)),
    MetricDef("m6", "Precision@3 de videos", "P2", "ratio", "≥ 0,7", _at_least(0.7)),
    MetricDef("m7", "Acuerdo LLM vs. humano (QWK)", "P3", "ratio", "≥ 0,6", _at_least(0.6)),
    MetricDef("m8", "Validez del diagnóstico (AUC)", "P1", "ratio", "≥ 0,7", _at_least(0.7)),
    MetricDef("m9", "Latencia p95", "P3", "seconds", "< 20 s", _below(20)),
    MetricDef("m10", "JSON inválido", "P3", "percent", "< 2 %", _below(0.02)),
    # La API suma el costo del periodo; el costo por aprendiz-ruta lo calcula el notebook.
    MetricDef("m11", "Costo del LLM", "P3", "usd", "Reportar"),
    MetricDef("m12", "Eficiencia de la personalización", "P2", "text", "Reportar"),
    MetricDef("m13", "Usabilidad (SUS)", "P3", "count", "≥ 68", _at_least(68)),
)
LEARNERS: tuple[MetricDef, ...] = (
    MetricDef("m14", "Ganancia de Hake (media)", "P2", "ratio", "g ≥ 0,3", _at_least(0.3)),
    MetricDef("m15", "d de Cohen (IC 95 %)", "P2", "ratio", "Reportar"),
    MetricDef("m16", "Dominio por tema", "P1", "text", "Reportar por tema"),
    MetricDef(
        "m17",
        "Aprobación al primer intento",
        "P2",
        "percent",
        "Entre 60 % y 85 %",
        _between(0.6, 0.85),
    ),
    MetricDef("m18", "Intentos por tema", "P2", "ratio", "≤ 1,8", _at_most(1.8)),
    MetricDef("m19", "Finalización", "P2", "percent", "≥ 60 %", _at_least(0.6)),
    MetricDef("m20", "Abandono", "P2", "text", "Identificar temas críticos"),
    MetricDef("m21", "Percepción", "P2", "ratio", "Media ≥ 4", _at_least(4)),
)
OTHERS: tuple[MetricDef, ...] = (
    MetricDef("m22", "Tasa de errores de la API", "P3", "percent", "Reportar"),
    MetricDef("m23", "nDCG@3 de videos", "P2", "ratio", "Reportar"),
    MetricDef("m24", "Índice de dificultad de ítems", "P1", "ratio", "Reportar"),
    MetricDef("m25", "Relevancia de la respuesta (RAGAS)", "P3", "ratio", "Reportar"),
    MetricDef("m26", "Precisión del contexto (RAGAS)", "P3", "ratio", "Reportar"),
    MetricDef("m27", "Tiempo en tarea", "P2", "minutes", "Reportar"),
    MetricDef("m28", "Certificación (badge)", "P2", "percent", "Reportar"),
    MetricDef("m29", "Retención (post-test diferido)", "P2", "ratio", "Reportar"),
)


def _status(metric: MetricDef, value: float | None) -> str:
    if value is None:
        return "no_data"
    if metric.check is None:
        return "report"
    return "meets" if metric.check(value) else "not_met"


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def measured(m: EvaluationMetrics) -> dict[str, tuple[float | None, str]]:
    """(valor, detalle) de cada métrica que la API calcula; las demás no aparecen."""
    validity, grading, faith = m.item_validity, m.grading, m.faithfulness
    videos, llm, steps = m.videos, m.llm, m.steps
    f1 = [v for e in m.extraction for v in (e.topics_f1, e.prerequisites_f1) if v is not None]
    calls = f"n = {llm.calls} llamadas · log del LLM" if llm else "Log del LLM"
    has_calls = llm is not None and llm.calls > 0
    p95 = llm.latency_p95_ms if llm is not None else None
    judged = videos.topics_judged if videos else 0
    passed = steps.steps_passed if steps else 0
    return {
        "m1": (_mean(f1), f"n = {len(m.extraction)} cursos · corrección del instructor (D2)"),
        "m2": (
            validity.valid_rate if validity else None,
            f"n = {validity.annotated_items if validity else 0} ítems · rúbrica (D5b)",
        ),
        "m3": (
            validity.cohen_kappa if validity else None,
            f"n = {validity.items_with_two_evaluators if validity else 0} ítems con 2 expertos",
        ),
        "m5": (
            faith.mean if faith else None,
            f"n = {faith.versions_measured if faith else 0} textos",
        ),
        "m6": (
            videos.precision_at_3 if videos else None,
            f"n = {judged} temas · juicio de expertos (D5e)",
        ),
        "m7": (
            grading.qwk if grading else None,
            f"n = {grading.graded_by_human if grading else 0} respuestas (D5c)",
        ),
        "m9": (round(p95 / 1000, 2) if p95 is not None else None, calls),
        "m10": (llm.invalid_json_rate if llm else None, calls),
        "m11": (round(llm.cost_usd, 4) if llm is not None and has_calls else None, calls),
        "m17": (
            steps.first_attempt_pass_rate if steps else None,
            f"n = {passed} temas aprobados",
        ),
        "m18": (steps.avg_attempts_used if steps else None, f"n = {passed} temas aprobados"),
        "m23": (
            videos.ndcg_at_3 if videos else None,
            f"n = {judged} temas · juicio de expertos (D5e)",
        ),
    }


def _group(title: str, defs: tuple[MetricDef, ...], values: dict[str, Any]) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    for metric in defs:
        value, detail = values.get(metric.code, (None, NOT_COMPUTED))
        metrics.append(
            {
                "code": metric.code,
                "name": metric.name,
                "priority": metric.priority,
                "status": _status(metric, value),
                "value": value,
                "value_text": None,
                "unit": metric.unit,
                "goal": metric.goal,
                "detail": detail,
            }
        )
    return {"title": title, "metrics": metrics}


def metric_catalog(m: EvaluationMetrics) -> list[dict[str, Any]]:
    """Los tres grupos de AD3, en el orden de Figma."""
    values = measured(m)
    return [
        _group("Métricas del sistema", SYSTEM, values),
        _group("Métricas de los aprendices", LEARNERS, values),
        _group("Otras métricas del brief", OTHERS, values),
    ]
