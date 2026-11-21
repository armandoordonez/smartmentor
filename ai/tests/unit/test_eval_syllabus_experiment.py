"""E2: emparejamiento por nombre, F1, rechazo de la caché y formato de las hojas (sin red ni LLM)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from eval import syllabus_experiment as e2

GOLD_ROWS = [
    {"course_key": "curso", "kind": "topic", "name": "Regresión lineal", "prerequisite_of": ""},
    {"course_key": "curso", "kind": "topic", "name": "Regresión logística", "prerequisite_of": ""},
    {
        "course_key": "curso",
        "kind": "topic",
        "name": "Evaluación de modelos",
        "prerequisite_of": "",
    },
    {
        "course_key": "curso",
        "kind": "prerequisite",
        "name": "regresión   lineal",
        "prerequisite_of": "Regresión logística",
    },
]


def _record(*, from_cache: bool = False, model: str = "m1", rep: int = 1) -> dict[str, Any]:
    def topic(topic_id: str, name: str, prerequisites: list[str]) -> dict[str, Any]:
        return {"id": topic_id, "name": name, "prerequisites": prerequisites}

    return {
        "course_key": "curso",
        "requested_model": model,
        "repetition": rep,
        "cost_usd": "0.0123",
        "latency_ms": 4000,
        "syllabus": {
            "topics": [
                topic("lineal", "Modelo lineal", []),
                topic("logistica", "Clasificación logística", ["lineal"]),
                topic("extra", "Tema inventado", ["logistica"]),
            ],
            "meta": {"model": model, "from_cache": from_cache},
        },
    }


MAPPING = {
    "lineal": "Regresión lineal",
    "logistica": "regresión logística",
    "extra": None,
}


def test_gold_reads_names_and_checks_the_pairs() -> None:
    gold = e2.read_gold(GOLD_ROWS)["curso"]
    assert set(gold.topics) == {"regresión lineal", "regresión logística", "evaluación de modelos"}
    assert gold.prerequisites == {("regresión lineal", "regresión logística")}
    bad = [*GOLD_ROWS, {**GOLD_ROWS[3], "name": "Inexistente"}]
    with pytest.raises(ValueError, match="tema ausente"):
        e2.read_gold(bad)


def test_empty_gold_template_is_ignored() -> None:
    assert e2.read_gold(e2.gold_sheet_rows(["curso"])) == {}


def test_matching_gives_f1_of_topics_and_prerequisites() -> None:
    run = e2.parse_run(_record())
    gold = e2.read_gold(GOLD_ROWS)["curso"]
    scores = e2.score_extraction(run, gold, MAPPING)
    # 2 de 3 predichos aciertan; 2 de 3 de oro se encuentran.
    assert scores.topics.precision == pytest.approx(2 / 3)
    assert scores.topics.recall == pytest.approx(2 / 3)
    assert scores.topics.f1 == pytest.approx(2 / 3)
    # Predichos: (lineal>logística) acierta; (logística>extra) cae en el tema sin pareja.
    assert scores.prerequisites.precision == pytest.approx(1 / 2)
    assert scores.prerequisites.recall == 1.0
    assert (scores.unmatched, scores.extracted) == (1, 3)


def test_two_extracted_topics_on_the_same_gold_topic_count_once() -> None:
    run = e2.parse_run(_record())
    gold = e2.read_gold(GOLD_ROWS)["curso"]
    scores = e2.score_extraction(run, gold, {**MAPPING, "extra": "Regresión lineal"})
    assert scores.topics.precision == pytest.approx(1.0)
    assert scores.unmatched == 0


def test_mapping_errors() -> None:
    run = e2.parse_run(_record())
    gold = e2.read_gold(GOLD_ROWS)["curso"]
    with pytest.raises(e2.MappingError, match="falta"):
        e2.score_extraction(run, gold, None)
    with pytest.raises(e2.MappingError, match="sin entrada"):
        e2.score_extraction(run, gold, {"lineal": "Regresión lineal"})
    with pytest.raises(e2.MappingError, match="no es un tema de oro"):
        e2.score_extraction(run, gold, {**MAPPING, "extra": "Otro tema"})


def test_from_cache_true_fails() -> None:
    with pytest.raises(e2.FromCacheError):
        e2.validate_run(_record(from_cache=True))
    e2.validate_run(_record())
    with pytest.raises(ValueError, match="meta"):
        e2.validate_run({"syllabus": {}})


def test_worker_env_sets_the_model_only_in_the_copy() -> None:
    base = {"AI_LLM_MODEL_DEFAULT": "otro", "AI_LLM_PROVIDER": "gemini"}
    env = e2.worker_env(base, "gemini-3.5-flash-lite")
    assert env["AI_LLM_MODEL_DEFAULT"] == "gemini-3.5-flash-lite"
    assert env["AI_EVAL_LIVE"] == "1"
    assert base["AI_LLM_MODEL_DEFAULT"] == "otro"


def test_run_refuses_other_providers(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="gemini"):
        e2.run_experiment(
            tmp_path / "s.md", ["m"], 1, tmp_path, environ={"AI_LLM_PROVIDER": "fake"}
        )


def _write_runs(run_dir: Path) -> None:
    for model, rep in (("m1", 1), ("m1", 2), ("m2", 1)):
        path = e2.run_path(run_dir, "curso", model, rep)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_record(model=model, rep=rep)), encoding="utf-8")


def test_sheets_and_report_round_trip(tmp_path: Path) -> None:
    gold_csv = tmp_path / "oro.csv"
    e2._write_csv(gold_csv, e2.GOLD_COLUMNS, GOLD_ROWS)
    _write_runs(tmp_path / "runs")

    template = tmp_path / "plantilla.csv"
    assert e2.main(["export-gold-sheet", "--course-key", "curso", "--out", str(template)]) == 0
    with template.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == ("course_key", "kind", "name", "prerequisite_of")
        assert {r["kind"] for r in reader} == {"topic", "prerequisite"}

    sheet_path = tmp_path / "emparejar.json"
    args = ["--gold", str(gold_csv), "--run-dir", str(tmp_path / "runs"), "--out", str(sheet_path)]
    assert e2.main(["export-matching-sheet", *args]) == 0
    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    assert [i["extraction_id"] for i in sheet["extractions"]] == [
        "curso/m1/rep1",
        "curso/m1/rep2",
        "curso/m2/rep1",
    ]
    first = sheet["extractions"][0]
    assert first["mapping"] == {"lineal": None, "logistica": None, "extra": None}
    assert first["gold_topics"] == [
        "Evaluación de modelos",
        "Regresión lineal",
        "Regresión logística",
    ]
    assert "gold" not in json.dumps(first["extracted_topics"])  # el oro va aparte

    for item in sheet["extractions"]:
        item["mapping"].update(MAPPING)
    sheet_path.write_text(json.dumps(sheet), encoding="utf-8")
    out = tmp_path / "resultado.md"
    code = e2.main(
        [
            "match",
            "--gold",
            str(gold_csv),
            "--run-dir",
            str(tmp_path / "runs"),
            "--mapping",
            str(sheet_path),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "| curso | m1 | 2 | 0,667 | 0,667 |" in text  # media y rango por curso y modelo
    assert "| m1 | 2 | 0,667 | 0,667 a 0,667 |" in text
    assert "1 de 3" in text  # temas sin emparejar


def test_mapping_accepts_a_plain_dict() -> None:
    assert e2.load_mapping({"curso/m1/rep1": {"a": "X", "b": None}}) == {
        "curso/m1/rep1": {"a": "X", "b": None}
    }
