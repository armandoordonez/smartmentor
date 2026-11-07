"""Pruebas de ``app.domain.metrics`` contra valores calculados a mano."""

from __future__ import annotations

import math

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
