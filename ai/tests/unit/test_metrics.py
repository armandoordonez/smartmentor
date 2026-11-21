"""Pruebas de ``app.domain.metrics`` contra valores calculados a mano."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.domain import metrics as m


class TestCohenKappa:
    def test_hand_computed(self) -> None:
        # po = 3/4; pe = 0.5*0.25 + 0.5*0.75 = 0.5 -> kappa = 0.5
        assert m.cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)

    def test_perfect_agreement(self) -> None:
        assert m.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == pytest.approx(1.0)

    def test_total_disagreement(self) -> None:
        assert m.cohen_kappa([0, 0, 1, 1], [1, 1, 0, 0]) == pytest.approx(-1.0)

    def test_single_label_both_raters(self) -> None:
        assert m.cohen_kappa([1, 1, 1], [1, 1, 1]) == 1.0

    def test_empty_and_mismatched(self) -> None:
        with pytest.raises(ValueError, match="vacía"):
            m.cohen_kappa([], [])
        with pytest.raises(ValueError, match="largo distinto"):
            m.cohen_kappa([1], [1, 0])


class TestQuadraticWeightedKappa:
    def test_hand_computed(self) -> None:
        # Observado: 0.5; esperado: 1.0 -> QWK = 0.5
        assert m.quadratic_weighted_kappa([0, 1, 2], [0, 2, 1]) == pytest.approx(0.5)

    def test_perfect(self) -> None:
        assert m.quadratic_weighted_kappa([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)

    def test_extreme_disagreement_is_negative(self) -> None:
        assert m.quadratic_weighted_kappa([0, 0, 4, 4], [4, 4, 0, 0]) == pytest.approx(-1.0)

    def test_constant_scores(self) -> None:
        assert m.quadratic_weighted_kappa([3, 3], [3, 3]) == 1.0

    def test_explicit_range_changes_weights(self) -> None:
        # Con rango 0..2 el desacuerdo 0 vs 1 pesa 1/4; con 0..1 pesa 1.
        wide = m.quadratic_weighted_kappa([0, 1, 0, 1], [1, 1, 0, 0], 0, 2)
        narrow = m.quadratic_weighted_kappa([0, 1, 0, 1], [1, 1, 0, 0], 0, 1)
        assert wide == pytest.approx(narrow)  # el cociente de pesos se cancela

    def test_invalid_inputs(self) -> None:
        with pytest.raises(ValueError, match="vacía"):
            m.quadratic_weighted_kappa([], [])
        with pytest.raises(ValueError, match="fuera del rango"):
            m.quadratic_weighted_kappa([1, 9], [1, 2], 0, 5)
        with pytest.raises(ValueError, match="max_rating"):
            m.quadratic_weighted_kappa([1], [1], 5, 0)


class TestSetF1:
    def test_hand_computed(self) -> None:
        scores = m.set_f1({"a", "b", "c"}, {"b", "c", "d", "e"})
        assert scores.precision == pytest.approx(2 / 3)
        assert scores.recall == pytest.approx(1 / 2)
        assert scores.f1 == pytest.approx(4 / 7)

    def test_prerequisite_pairs_and_duplicates(self) -> None:
        predicted = [("a", "b"), ("a", "b"), ("b", "c")]
        gold = [("a", "b"), ("c", "d")]
        assert m.set_f1(predicted, gold).f1 == pytest.approx(0.5)

    def test_both_empty(self) -> None:
        assert m.set_f1([], []) == m.SetScores(1.0, 1.0, 1.0)

    def test_one_empty(self) -> None:
        assert m.set_f1([], ["a"]) == m.SetScores(0.0, 0.0, 0.0)
        assert m.set_f1(["a"], []) == m.SetScores(0.0, 0.0, 0.0)

    def test_disjoint(self) -> None:
        assert m.set_f1(["a"], ["b"]).f1 == 0.0


class TestRanking:
    def test_precision_at_k(self) -> None:
        assert m.precision_at_k([1, 0, 1], 3) == pytest.approx(2 / 3)
        assert m.precision_at_k([True, True, True, False], 3) == 1.0

    def test_precision_short_list_counts_missing_as_not_relevant(self) -> None:
        assert m.precision_at_k([1], 3) == pytest.approx(1 / 3)
        assert m.precision_at_k([], 3) == 0.0

    def test_invalid_k(self) -> None:
        with pytest.raises(ValueError, match="k"):
            m.precision_at_k([1], 0)
        with pytest.raises(ValueError, match="k"):
            m.ndcg_at_k([1], 0)

    def test_ndcg_hand_computed(self) -> None:
        dcg = 1 / math.log2(3) + 1 / math.log2(4)
        ideal = 1 + 1 / math.log2(3)
        assert m.ndcg_at_k([0, 1, 1], 3) == pytest.approx(dcg / ideal)

    def test_ndcg_perfect_and_zero(self) -> None:
        assert m.ndcg_at_k([1, 1, 0], 3) == pytest.approx(1.0)
        assert m.ndcg_at_k([0, 0, 0], 3) == 0.0

    def test_ndcg_with_ideal_pool_beyond_k(self) -> None:
        # El mejor candidato (grado 2) quedó fuera del top 3: el ideal lo cuenta.
        value = m.ndcg_at_k([0, 1, 0], 3, ideal_relevances=[0, 1, 0, 2])
        dcg = 1 / math.log2(3)
        ideal = 2 + 1 / math.log2(3)
        assert value == pytest.approx(dcg / ideal)


class TestHake:
    def test_hand_computed(self) -> None:
        assert m.hake_gain(40, 70) == pytest.approx(0.5)

    def test_negative_gain(self) -> None:
        assert m.hake_gain(50, 25) == pytest.approx(-0.5)

    def test_ceiling_is_undefined(self) -> None:
        assert m.hake_gain(100, 100) is None

    def test_custom_max_score(self) -> None:
        assert m.hake_gain(2, 4, max_score=10) == pytest.approx(0.25)

    def test_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="entre 0"):
            m.hake_gain(-1, 5)
        with pytest.raises(ValueError, match="max_score"):
            m.hake_gain(1, 2, max_score=0)

    def test_mean_is_per_person_then_average(self) -> None:
        # g = 0.5 y 0.0 (la persona con pre = 100 se excluye) -> media 0.25, n = 2
        mean, n = m.mean_hake_gain([(40, 70), (50, 50), (100, 100)])
        assert mean == pytest.approx(0.25)
        assert n == 2

    def test_mean_without_defined_gains(self) -> None:
        with pytest.raises(ValueError, match="ganancia"):
            m.mean_hake_gain([(100, 100)])
        with pytest.raises(ValueError, match="ganancia"):
            m.mean_hake_gain([])


class TestSus:
    def test_best(self) -> None:
        assert m.sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0

    def test_worst(self) -> None:
        assert m.sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0

    def test_neutral(self) -> None:
        assert m.sus_score([3] * 10) == 50.0

    def test_hand_computed(self) -> None:
        # impares: 4,4,3,4,5 -> 3+3+2+3+4 = 15; pares: 2,2,1,2,2 -> 3+3+4+3+3 = 16; 31*2.5
        assert m.sus_score([4, 2, 4, 2, 3, 1, 4, 2, 5, 2]) == pytest.approx(77.5)

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="10"):
            m.sus_score([3] * 9)
        with pytest.raises(ValueError, match="entre 1 y 5"):
            m.sus_score([3] * 9 + [6])


class TestCohensD:
    def test_hand_computed(self) -> None:
        # medias 4 y 2; varianzas muestrales 1 y 1 -> sp = 1 -> d = 2
        assert m.cohens_d([3, 4, 5], [1, 2, 3]) == pytest.approx(2.0)

    def test_sign_and_zero(self) -> None:
        assert m.cohens_d([1, 2, 3], [3, 4, 5]) == pytest.approx(-2.0)
        assert m.cohens_d([1, 2, 3], [1, 2, 3]) == 0.0

    def test_zero_variance(self) -> None:
        assert m.cohens_d([2, 2], [2, 2]) == 0.0
        assert m.cohens_d([3, 3], [2, 2]) == math.inf
        assert m.cohens_d([1, 1], [2, 2]) == -math.inf

    def test_too_small(self) -> None:
        with pytest.raises(ValueError, match="2 observaciones"):
            m.cohens_d([1], [1, 2])

    def test_bootstrap_ci_is_deterministic_and_contains_point(self) -> None:
        treatment = [62, 70, 75, 68, 80, 72, 77, 66, 74, 71]
        control = [55, 60, 63, 58, 70, 61, 65, 57, 62, 59]
        first = m.cohens_d_with_ci(treatment, control, seed=7)
        second = m.cohens_d_with_ci(treatment, control, seed=7)
        assert first == second
        assert first.ci_low < first.d < first.ci_high
        assert first.confidence == 0.95
        assert first.n_bootstrap == 2000
        assert m.cohens_d_with_ci(treatment, control, seed=8) != first

    def test_bootstrap_invalid(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            m.cohens_d_with_ci([1, 2], [3, 4], confidence=1.0)
        with pytest.raises(ValueError, match="n_bootstrap"):
            m.cohens_d_with_ci([1, 2], [3, 4], n_bootstrap=10)
        with pytest.raises(ValueError, match="finito"):
            m.cohens_d_with_ci([2, 2], [3, 3])


class TestAuc:
    def test_classic_example(self) -> None:
        # Positivos 0.35 y 0.8 frente a negativos 0.1 y 0.4: 3 de 4 pares -> 0.75
        assert m.auc_roc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)

    def test_perfect_and_inverted(self) -> None:
        assert m.auc_roc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
        assert m.auc_roc([1, 2, 3, 4], [1, 1, 0, 0]) == 0.0

    def test_all_ties(self) -> None:
        assert m.auc_roc([5, 5, 5, 5], [0, 1, 0, 1]) == 0.5

    def test_single_class(self) -> None:
        with pytest.raises(ValueError, match="positivo y un negativo"):
            m.auc_roc([1, 2], [1, 1])

    def test_empty(self) -> None:
        with pytest.raises(ValueError, match="vacía"):
            m.auc_roc([], [])


class TestItemStatistics:
    def test_difficulty(self) -> None:
        assert m.item_difficulty([1, 1, 0, 1]) == 0.75
        assert m.item_difficulty([False, False]) == 0.0
        with pytest.raises(ValueError, match="respuestas"):
            m.item_difficulty([])

    def test_point_biserial_hand_computed(self) -> None:
        # m1 = 2.5, m0 = 0.5, s = sqrt(1.25), p = 0.5 -> r = 2/sqrt(5)
        assert m.point_biserial([1, 1, 0, 0], [3, 2, 1, 0]) == pytest.approx(2 / math.sqrt(5))

    def test_point_biserial_degenerate(self) -> None:
        assert m.point_biserial([1, 1, 1], [1, 2, 3]) == 0.0
        assert m.point_biserial([1, 0, 1], [4, 4, 4]) == 0.0

    def test_discrimination_corrected_vs_raw(self) -> None:
        item = [1, 1, 0, 0]
        totals = [4, 3, 1, 0]
        raw = m.item_discrimination(item, totals, corrected=False)
        assert raw == pytest.approx(m.point_biserial(item, totals))
        # resto = [3, 2, 1, 0] -> el caso a mano de arriba
        assert m.item_discrimination(item, totals) == pytest.approx(2 / math.sqrt(5))

    def test_discrimination_negative(self) -> None:
        assert m.item_discrimination([0, 0, 1, 1], [5, 4, 1, 0], corrected=False) < 0

    def test_valid_question_rate(self) -> None:
        verdicts = [[True, True], [True, False], [True, True], [False, False]]
        assert m.valid_question_rate(verdicts) == 50.0

    def test_valid_question_rate_invalid(self) -> None:
        with pytest.raises(ValueError, match="ítems"):
            m.valid_question_rate([])
        with pytest.raises(ValueError, match="sin veredictos"):
            m.valid_question_rate([[True], []])


class TestLatency:
    def test_percentile_interpolates(self) -> None:
        assert m.percentile([1, 2, 3, 4, 5], 50) == 3.0
        assert m.percentile([5, 1, 4, 2, 3], 95) == pytest.approx(4.8)
        assert m.percentile([7], 95) == 7.0
        assert m.percentile([1, 9], 0) == 1.0
        assert m.percentile([1, 9], 100) == 9.0

    def test_percentile_invalid(self) -> None:
        with pytest.raises(ValueError, match="valores"):
            m.percentile([], 50)
        with pytest.raises(ValueError, match="entre 0 y 100"):
            m.percentile([1], 101)

    def test_latency_percentiles(self) -> None:
        result = m.latency_percentiles([100.0, 200.0, 300.0, 400.0, 500.0])
        assert result.p50 == 300.0
        assert result.p95 == pytest.approx(480.0)
        assert result.n == 5

    def test_latency_empty(self) -> None:
        with pytest.raises(ValueError, match="valores"):
            m.latency_percentiles([])


T0 = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)


def _at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _event(
    event_type: str,
    minute: float,
    *,
    enrollment_id: int = 7,
    topic_id: int | None = None,
    **payload: Any,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "enrollment_id": enrollment_id,
        "topic_id": topic_id,
        "occurred_at": _at(minute),
        "payload": payload or None,
    }


def _close(
    event_type: str, start: float, seconds: int, *, topic_id: int | None = None, **extra: Any
) -> dict[str, Any]:
    """Cierre de un tramo que empezó en el minuto ``start`` y duró ``seconds``."""
    return _event(
        event_type,
        start + seconds / 60,
        topic_id=topic_id,
        seconds=seconds,
        started_at=_at(start).isoformat(),
        **extra,
    )


class TestTimeOnTask:
    def test_closed_segments_by_topic_and_enrollment(self) -> None:
        events = [
            _event("path.view", 0, screen="E5", steps_total=3),
            _close("path.close", 0, 90),
            _event("topic.open", 2, topic_id=11, screen="E6", step_id=812),
            _event("resource.view", 2, topic_id=11, resource="explanation", resource_id=120),
            _close("topic.close", 2, 720, topic_id=11),
            _event("quiz.start", 14.1, topic_id=11, attempt_id=9001),
            _close("quiz.pause", 14.2, 300, topic_id=11, attempt_id=9001),
            _close("quiz.submit", 30, 600, topic_id=11, attempt_id=9001, items=5),
        ]
        result = m.time_on_task(events)
        # Tema 11: 720 + 300 + 600 = 1620 s = 27 min; ruta: 27 + 1,5 = 28,5 min.
        assert result.minutes_by_topic == {(7, 11): pytest.approx(27.0)}
        assert result.minutes_by_enrollment == {7: pytest.approx(28.5)}
        assert result.closed_segments == 4
        assert result.imputed_segments == 0

    def test_open_segment_imputed_with_median_and_next_event(self) -> None:
        events = [
            _event("topic.open", 0, topic_id=11),
            _close("topic.close", 0, 600, topic_id=11),
            _event("topic.open", 10, topic_id=12),
            _close("topic.close", 10, 1200, topic_id=12),
            # Tema 13 sin cierre; el siguiente evento de la inscripción llega 8 min después.
            _event("topic.open", 40, topic_id=13),
            _event("path.view", 48),
            _close("path.close", 48, 60),
        ]
        result = m.time_on_task(events)
        # Mediana de los temas cerrados: 900 s (15 min); el tope es el siguiente evento: 8 min.
        assert result.reference_seconds["topic"] == pytest.approx(900.0)
        assert result.minutes_by_topic[(7, 13)] == pytest.approx(8.0)
        assert result.imputed_segments == 1
        assert result.imputed_minutes == pytest.approx(8.0)
        assert result.minutes_by_enrollment[7] == pytest.approx(10 + 20 + 8 + 1)

    def test_open_segment_without_later_event_takes_the_median(self) -> None:
        events = [
            _event("topic.open", 0, topic_id=11),
            _close("topic.close", 0, 600, topic_id=11),
            _event("topic.open", 30, topic_id=12, enrollment_id=8),
        ]
        result = m.time_on_task(events)
        # La mediana es de la cohorte: la inscripción 8 toma los 10 min de la 7.
        assert result.minutes_by_topic[(8, 12)] == pytest.approx(10.0)

    def test_open_segment_without_reference_is_zero(self) -> None:
        result = m.time_on_task([_event("final.start", 0, attempt_id=5)])
        assert result.imputed_segments == 1
        assert result.minutes_by_enrollment == {7: 0.0}

    def test_quiz_paired_by_attempt(self) -> None:
        events = [
            _event("quiz.start", 0, topic_id=11, attempt_id=1),
            _close("quiz.pause", 0.01, 120, topic_id=11, attempt_id=1),
            _event("quiz.start", 10, topic_id=11, attempt_id=2),
        ]
        result = m.time_on_task(events)
        # El intento 1 cerró (no se imputa); el 2 queda abierto y toma la mediana: 2 min.
        assert result.imputed_segments == 1
        assert result.minutes_by_topic[(7, 11)] == pytest.approx(4.0)

    def test_capped_counts_at_cap_and_is_left_out_of_reference(self) -> None:
        events = [
            _close("topic.close", 0, 3600, topic_id=11, capped=True),
            _close("topic.close", 70, 300, topic_id=12),
            _close("topic.close", 80, 5000, topic_id=13),
        ]
        result = m.time_on_task(events)
        assert result.capped_segments == 2
        assert result.minutes_by_topic[(7, 11)] == pytest.approx(60.0)
        assert result.minutes_by_topic[(7, 13)] == pytest.approx(60.0)
        assert result.reference_seconds == {"topic": pytest.approx(300.0)}

    def test_duplicate_closes_count_once(self) -> None:
        close = _close("topic.close", 0, 600, topic_id=11)
        result = m.time_on_task([_event("topic.open", 0, topic_id=11), close, dict(close)])
        assert result.duplicate_closes == 1
        assert result.imputed_segments == 0
        assert result.minutes_by_topic[(7, 11)] == pytest.approx(10.0)

    def test_accepts_json_text_and_iso_dates(self) -> None:
        row = {
            "event_type": "path.close",
            "enrollment_id": 3,
            "topic_id": float("nan"),
            "occurred_at": "2026-11-09T14:05:00+00:00",
            "payload": '{"seconds": 300, "started_at": "2026-11-09T14:00:00+00:00"}',
        }
        float_topic = {**row, "event_type": "topic.close", "topic_id": 11.0}
        result = m.time_on_task([row, float_topic])
        assert result.minutes_by_enrollment == {3: pytest.approx(10.0)}
        # El primero es un cierre de ruta (sin tema); el segundo, de un tema con id en float.
        assert result.minutes_by_topic == {(3, 11): pytest.approx(5.0)}

    def test_rejects_naive_dates(self) -> None:
        row = _event("path.view", 0)
        row["occurred_at"] = datetime(2026, 11, 9, 14, 0)  # noqa: DTZ001 - sin zona a propósito
        with pytest.raises(ValueError, match="zona horaria"):
            m.time_on_task([row])

    def test_empty_input(self) -> None:
        result = m.time_on_task([])
        assert result.minutes_by_enrollment == {}
        assert result.closed_segments == 0
