"""Tests for ``eval.llm_report`` with synthetic log rows (hand-computed values)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eval import llm_report as r

CUTOFF = r.parse_timestamp("2026-11-13T15:31:00Z")


def row(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "task": "items.generate_quiz_bank",
        "model": "m1",
        "enrollment_id": 1,
        "json_valid": True,
        "call_attempt": 1,
        "from_cache": False,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.5,
        "latency_ms": 1000,
        "status": "success",
        "error_message": None,
        "created_at": "2026-11-12T10:00:00Z",
    }
    return base | kw


def test_percentile_linear_interpolation() -> None:
    assert r.percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert r.percentile([10, 20, 30, 40, 50], 95) == pytest.approx(48.0)
    assert r.percentile([7], 95) == 7
    assert r.percentile([], 50) is None


def test_summarise_counts_and_excludes_cache_from_latency() -> None:
    rows = [
        row(latency_ms=1000),
        row(latency_ms=3000),
        row(latency_ms=0, from_cache=True),
        row(status="invalid_output", latency_ms=2000, call_attempt=2),
        row(
            status="error",
            json_valid=None,
            latency_ms=120_000,
            cost_usd=0,
            error_message="LlmTimeoutError: gemini did not answer in time",
        ),
        row(json_valid=False, status="invalid_output", latency_ms=4000),
    ]
    s = r.summarise(rows)
    assert (s.calls, s.provider_calls) == (6, 5)
    assert s.p50_ms == 3000
    assert s.max_ms == 120_000
    assert (s.invalid, s.unparsable) == (2, 1)
    assert s.invalid_pct == pytest.approx(40.0)
    assert (s.retries, s.timeouts, s.errors) == (1, 1, 1)
    assert s.input_tokens == 600
    assert s.cost_usd == pytest.approx(2.5)


def test_summarise_empty_group() -> None:
    s = r.summarise([])
    assert s.calls == 0
    assert s.p95_ms is None
    assert s.invalid_pct is None


def test_only_cache_hits_have_no_latency() -> None:
    s = r.summarise([row(from_cache=True, latency_ms=None)])
    assert s.p50_ms is None
    assert s.provider_calls == 0


def test_split_by_moment_uses_cutoff_and_skips_undated() -> None:
    rows = [
        row(created_at="2026-11-13T15:30:59Z"),
        row(created_at="2026-11-13T15:31:00Z"),
        row(created_at="2026-11-14T00:00:00Z"),
        row(created_at=None),
    ]
    moments = r.split_by_moment(rows, CUTOFF)
    assert (len(moments["antes"]), len(moments["despues"])) == (1, 2)


def test_build_report_cuts_by_course_task_and_moment() -> None:
    logs = [
        row(task="a", enrollment_id=1, cost_usd=1.0),
        row(task="a", enrollment_id=2, cost_usd=2.0, created_at="2026-11-14T00:00:00Z"),
        row(task="b", enrollment_id=None, cost_usd=0.25),
        row(task="b", enrollment_id=99, cost_usd=0.25),
    ]
    enrollments = [
        {"id": 1, "learning_path": {"id": 5, "name": "Curso X"}},
        {"id": 2, "learning_path": {"id": 6, "name": "Curso Y"}},
    ]
    report = r.build_report(logs, enrollments, CUTOFF)
    assert report["by_course"]["Curso X"].cost_usd == pytest.approx(1.0)
    assert report["by_course"]["Curso Y"].calls == 1
    assert report["by_course"][r.NO_COURSE].calls == 1
    assert report["by_course"][r.UNKNOWN_COURSE].calls == 1
    assert report["by_task"]["a"].calls == 2
    assert report["by_moment"]["despues"].cost_usd == pytest.approx(2.0)
    assert set(report["by_task_moment"]["antes"]) == {"a", "b"}
    assert report["total"].cost_usd == pytest.approx(3.5)
    assert report["period"] == ("2026-11-12T10:00:00Z", "2026-11-14T00:00:00Z")


def test_render_markdown_has_tables_and_spanish_numbers() -> None:
    report = r.build_report([row(latency_ms=1500)], [], CUTOFF)
    text = r.render_markdown(report)
    assert "### Por tarea" in text
    assert "| `items.generate_quiz_bank` | 1 | 1,5 | 1,5 | 1,5 | 0 (0,0 %)" in text
    assert "**Total**" in text


def test_main_reads_exported_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    logs = tmp_path / "logs.json"
    logs.write_text(json.dumps([row()]), encoding="utf-8")
    assert r.main(["--logs-file", str(logs)]) == 0
    assert "Por curso" in capsys.readouterr().out


def test_main_without_token_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMARTMENTOR_TOKEN", raising=False)
    assert r.main(["--base-url", "http://localhost:1"]) == 2


def test_summary_course_table_renders_api_summary() -> None:
    summary = {
        "by_course": [
            {"course_id": 2, "calls": 89, "cost_usd": 0.481789},
            {"course_id": None, "calls": 107, "cost_usd": 0.095841},
        ]
    }
    text = r.render_markdown(r.build_report([row()], [], CUTOFF), summary)
    assert "| 2 | 89 | 0,482 |" in text
    assert "| sin curso | 107 | 0,096 |" in text
