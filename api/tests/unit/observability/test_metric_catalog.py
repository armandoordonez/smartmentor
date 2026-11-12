"""Catálogo de AD3: cada métrica con su meta y su estado, decididos en la API (ADR 0017)."""

from app.domains.observability.catalog import (
    LEARNERS,
    NOT_COMPUTED,
    OTHERS,
    SYSTEM,
    metric_catalog,
)
from app.domains.observability.service import (
    CourseExtraction,
    EvaluationMetrics,
    FaithfulnessMetrics,
    GradingMetrics,
    ItemValidityMetrics,
    LlmMetrics,
    StepMetrics,
    VideoMetrics,
)

FULL = EvaluationMetrics(
    learning_path_ids=[1],
    extraction=[CourseExtraction(1, topics_f1=0.9, prerequisites_f1=0.8, corrections=2)],
    item_validity=ItemValidityMetrics(
        items=10,
        annotated_items=8,
        valid_votes=12,
        invalid_votes=4,
        valid_rate=0.75,
        items_with_two_evaluators=6,
        cohen_kappa=0.64,
    ),
    grading=GradingMetrics(graded_by_human=30, qwk=0.61),
    faithfulness=FaithfulnessMetrics(versions_measured=25, mean=0.83),
    videos=VideoMetrics(topics_judged=5, topics_incomplete=0, precision_at_3=0.6, ndcg_at_3=0.7),
    llm=LlmMetrics(
        calls=412, invalid_json_rate=0.012, cache_hit_rate=0.1, latency_p95_ms=14200, cost_usd=1.5
    ),
    steps=StepMetrics(
        steps_passed=31, first_attempt_pass_rate=0.58, avg_attempts_used=1.6, attempts_exhausted=2
    ),
)


def _by_code(metrics: EvaluationMetrics) -> dict[str, dict[str, object]]:
    return {e["code"]: e for g in metric_catalog(metrics) for e in g["metrics"]}


def test_the_three_groups_keep_the_figma_order_and_codes() -> None:
    groups = metric_catalog(FULL)
    assert [g["title"] for g in groups] == [
        "Métricas del sistema",
        "Métricas de los aprendices",
        "Otras métricas del brief",
    ]
    codes = [e["code"] for g in groups for e in g["metrics"]]
    assert codes == [m.code for m in (*SYSTEM, *LEARNERS, *OTHERS)]
    assert len(set(codes)) == len(codes)


def test_each_measured_metric_is_compared_with_its_goal() -> None:
    found = _by_code(FULL)
    assert (found["m1"]["value"], found["m1"]["status"]) == (0.85, "meets")  # media 0,9 y 0,8
    assert found["m2"]["status"] == "not_met"  # 75 % < 80 %
    assert found["m3"]["status"] == "meets"
    assert found["m6"]["status"] == "not_met"  # 0,6 < 0,7
    assert (found["m9"]["value"], found["m9"]["status"]) == (14.2, "meets")  # segundos
    assert found["m10"]["status"] == "meets"  # 1,2 % < 2 %
    assert found["m17"]["status"] == "not_met"  # 58 % fuera de 60 a 85 %
    assert found["m18"]["status"] == "meets"
    # Sin meta numérica: se reporta.
    assert (found["m11"]["status"], found["m23"]["status"]) == ("report", "report")


def test_what_the_api_does_not_compute_has_no_data() -> None:
    found = _by_code(FULL)
    for code in ("m4", "m8", "m12", "m13", "m14", "m15", "m19", "m21", "m29"):
        assert found[code]["status"] == "no_data", code
        assert found[code]["value"] is None
    assert found["m4"]["detail"] == NOT_COMPUTED


def test_an_empty_scope_has_no_data_and_does_not_fail() -> None:
    found = _by_code(EvaluationMetrics(learning_path_ids=[]))
    assert {e["status"] for e in found.values()} == {"no_data"}
