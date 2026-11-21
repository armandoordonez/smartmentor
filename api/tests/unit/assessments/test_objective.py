"""Verbos de Bloom del objetivo y propuesta guardada aparte (B-033)."""

from dataclasses import replace

import pytest

from app.domains.assessments.objective import (
    ALLOWED_BLOOM_VERBS,
    BLOOM_VERBS_BY_LEVEL,
    canonical_bloom_verb,
    normalize_proposal,
    objective_proposal,
)
from app.domains.learning_paths.entities import Enrollment


def test_the_six_levels_lead_each_group_and_there_are_no_duplicates() -> None:
    leaders = [verbs[0] for verbs in BLOOM_VERBS_BY_LEVEL.values()]
    assert leaders == ["Recordar", "Comprender", "Aplicar", "Analizar", "Evaluar", "Crear"]
    assert len(ALLOWED_BLOOM_VERBS) == len(set(ALLOWED_BLOOM_VERBS))
    assert all(len(v) <= 60 for v in ALLOWED_BLOOM_VERBS)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("Aplicar", "Aplicar"),
        ("  aplicar ", "Aplicar"),
        ("DISENAR", "Diseñar"),
        ("construir", "Construir"),
        ("Implementar", "Implementar"),
        ("Hackear", None),
        ("Construir y evaluar", None),
        ("", None),
    ],
)
def test_canonical_bloom_verb(given: str, expected: str | None) -> None:
    assert canonical_bloom_verb(given) == expected


def test_a_compound_verb_keeps_the_first_and_moves_the_rest_to_the_content() -> None:
    verb, content = normalize_proposal("Construir y evaluar", "un modelo de regresión logística")
    assert verb == "Construir"
    assert content == "y evaluar un modelo de regresión logística"
    assert f"{verb} {content}" == "Construir y evaluar un modelo de regresión logística"


def test_a_listed_verb_is_canonicalised_and_an_unknown_one_is_kept() -> None:
    assert normalize_proposal("aplicar", "x") == ("Aplicar", "x")
    assert normalize_proposal("Dominar", "x") == ("Dominar", "x")


def _enrollment(**changes: str | None) -> Enrollment:
    base = Enrollment(
        user_id=1,
        learning_path_id=1,
        objective_bloom_verb="Construir",
        objective_content="un modelo propio",
        objective_criterion="con 90 %",
        objective_origin="learner_edited",
    )
    return replace(base, **changes)


def test_the_stored_proposal_survives_the_learner_edit() -> None:
    enrollment = _enrollment(
        objective_proposal_bloom_verb="Aplicar",
        objective_proposal_content="la regresión",
        objective_proposal_criterion="con 80 %",
        objective_proposal_origin="llm_proposed",
    )
    assert objective_proposal(enrollment) == {
        "bloom_verb": "Aplicar",
        "content": "la regresión",
        "criterion": "con 80 %",
        "origin": "llm_proposed",
    }


def test_legacy_rows_use_the_objective_unless_the_learner_edited_it() -> None:
    assert objective_proposal(_enrollment()) is None
    legacy = _enrollment(objective_origin="path_default")
    proposal = objective_proposal(legacy)
    assert proposal is not None
    assert proposal["origin"] == "path_default"
    assert proposal["bloom_verb"] == "Construir"
