"""E6: hojas ciegas para los jueces y el cálculo de las cuatro ordenaciones."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from eval import video_experiment as e6

HEADER = (
    "topic_id,topic_name,video_candidate_id,youtube_video_id,title,language,duration_seconds,"
    "similarity,rank,search_position,origin,status"
)


def _candidates(tmp_path: Path) -> Path:
    rows = [
        # Tema 10: el recomendador pone primero lo pertinente; YouTube lo tenía al final.
        "10,Fundamentos,1,AAAAAAAAAA1,Bueno uno,es,600,0.90,1,4,youtube_api,in_use",
        "10,Fundamentos,2,AAAAAAAAAA2,Bueno dos,en,700,0.85,2,3,youtube_api,backup",
        "10,Fundamentos,3,AAAAAAAAAA3,Malo uno,es,800,0.80,3,2,youtube_api,backup",
        "10,Fundamentos,4,AAAAAAAAAA4,Malo dos,es,900,0.70,4,1,youtube_api,candidate",
        # Tema 11: solo dos candidatos, queda fuera.
        "11,Instalación,5,BBBBBBBBBB1,Uno,es,600,0.9,1,1,youtube_api,in_use",
        "11,Instalación,6,BBBBBBBBBB2,Dos,es,600,0.8,2,2,youtube_api,backup",
        # Un video del instructor y uno rechazado no se juzgan.
        "10,Fundamentos,7,AAAAAAAAAA7,Docente,es,600,,,,instructor,backup",
        "10,Fundamentos,8,AAAAAAAAAA8,Rechazado,es,600,0.6,5,5,youtube_api,rejected",
    ]
    path = tmp_path / "candidatos.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_writes_blind_sheets_and_the_key(tmp_path: Path) -> None:
    message = e6.export(_candidates(tmp_path), tmp_path / "e6", judges=2, seed=42)
    assert message.startswith("1 temas y 4 videos para juzgar; 1 temas quedaron fuera")
    one, two = _read(tmp_path / "e6" / "juez_1.csv"), _read(tmp_path / "e6" / "juez_2.csv")
    assert {r["youtube_video_id"] for r in one} == {f"AAAAAAAAAA{n}" for n in range(1, 5)}
    # Ciegas: sin puesto, puntaje ni posición de YouTube, y la respuesta vacía.
    assert set(one[0]) == set(e6.JUDGE_COLUMNS)
    assert all(r["is_relevant"] == "" for r in one)
    assert {r["judge_slot"] for r in one} == {"1"} and {r["judge_slot"] for r in two} == {"2"}
    key = _read(tmp_path / "e6" / "clave.csv")
    assert [(r["rank"], r["search_position"]) for r in key] == [
        ("1", "4"),
        ("2", "3"),
        ("3", "2"),
        ("4", "1"),
    ]


def test_each_judge_gets_a_different_order_and_it_is_reproducible(tmp_path: Path) -> None:
    candidates = _candidates(tmp_path)
    e6.export(candidates, tmp_path / "x", judges=2, seed=7)
    e6.export(candidates, tmp_path / "y", judges=2, seed=7)
    first = [r["youtube_video_id"] for r in _read(tmp_path / "x" / "juez_1.csv")]
    again = [r["youtube_video_id"] for r in _read(tmp_path / "y" / "juez_1.csv")]
    second = [r["youtube_video_id"] for r in _read(tmp_path / "x" / "juez_2.csv")]
    assert first == again
    assert first != second or first != sorted(first)


def _judge(tmp_path: Path, slot: int, relevant: dict[str, str]) -> Path:
    path = tmp_path / f"juez_{slot}.csv"
    rows = [
        {
            "topic_key": "10",
            "topic_name": "Fundamentos",
            "youtube_video_id": video,
            "title": "",
            "url": "",
            "judge_slot": str(slot),
            "is_relevant": answer,
        }
        for video, answer in relevant.items()
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(e6.JUDGE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_report_compares_the_four_orders(tmp_path: Path) -> None:
    e6.export(_candidates(tmp_path), tmp_path, judges=2, seed=42)
    answers = {
        "AAAAAAAAAA1": "true",
        "AAAAAAAAAA2": "sí",
        "AAAAAAAAAA3": "false",
        "AAAAAAAAAA4": "no",
    }
    judges = [_judge(tmp_path, 1, answers), _judge(tmp_path, 2, answers)]
    text = e6.report(tmp_path / "clave.csv", judges, seed=42)
    assert "κ de Cohen = 1,000 sobre 4 videos (meta ≥ 0,600: cumple)." in text
    # (d) puntaje vigente: los dos pertinentes arriba → P@3 = 2/3 y nDCG@3 = 1.
    assert "| (d) Puntaje vigente (similitud + idioma + duración) | 0,667 | 1,000 | 1 |" in text
    # (b) orden de YouTube: los pertinentes en las posiciones 3 y 4 → solo uno en el top 3.
    assert "| (b) Orden de YouTube | 0,333 |" in text
    # (c) solo similitud ordena igual que el puntaje vigente en este tema.
    assert "| (c) Solo similitud con el tema | 0,667 | 1,000 | 1 |" in text
    assert "Solo la similitud iguala al puntaje vigente" in text
    assert "| es | 1 | 2 |" in text and "| en | 1 | 1 |" in text


def test_random_order_expectation_is_the_share_of_relevant_videos() -> None:
    videos = [
        e6.Judged(
            e6.Candidate("t", "", f"v{n}", "", "es", n, None, 0.5),
            (n <= 2,),
        )
        for n in range(1, 5)
    ]
    p3, _ = e6.random_scores(videos, "seed")
    # Esperanza exacta: 3 posiciones x (2 pertinentes / 4 videos) / 3 = 0,5.
    assert p3 == pytest.approx(0.5, abs=0.02)


def test_without_youtube_positions_the_report_says_to_search_again(tmp_path: Path) -> None:
    key = [e6.Candidate("10", "", f"v{n}", "", "es", n, None, 1 - n / 10) for n in range(1, 4)]
    votes = {("10", f"v{n}"): {1: n == 1, 2: n == 1} for n in range(1, 4)}
    result = e6.analyse(key, votes, seed=1)
    assert "b" not in result.scores
    assert any("buscar los videos de nuevo (B-064)" in d for d in e6.decisions(result))


def test_blank_or_unknown_answers_are_skipped() -> None:
    votes = e6.read_judgments(
        [
            {"topic_key": "1", "youtube_video_id": "v", "judge_slot": "1", "is_relevant": ""},
            {"topic_key": "1", "youtube_video_id": "w", "judge_slot": "1", "is_relevant": "quizá"},
            {"topic_key": "1", "youtube_video_id": "x", "judge_slot": "1", "is_relevant": "TRUE"},
        ]
    )
    assert dict(votes) == {("1", "x"): {1: True}}
