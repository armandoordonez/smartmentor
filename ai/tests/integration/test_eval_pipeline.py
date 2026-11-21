"""``eval.run_pipeline`` with the fakes produces a coherent package (phase 5 deliverable)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from eval.__main__ import main
from eval.consistency import Package, verify_consistency
from eval.pipeline import (
    DEFAULT_SYLLABUS,
    PipelineOptions,
    log_metrics,
    percentile,
    run_pipeline,
)
from eval.runtime import LiveEvaluationNotAllowedError, build_fake_runtime, build_live_runtime


def options(out: Path) -> PipelineOptions:
    return PipelineOptions(syllabus_text=DEFAULT_SYLLABUS.read_text(encoding="utf-8"), out_dir=out)


async def test_the_package_is_complete_and_consistent(tmp_path: Path) -> None:
    report = await run_pipeline(options(tmp_path), build_fake_runtime())
    assert report.issues == []
    for name in ("syllabus.json", "final_bank.json", "badge.json", "metrics.json", "llm_log.jsonl"):
        assert (tmp_path / name).is_file()
    assert len(list((tmp_path / "explanations").glob("*.json"))) == 3
    assert len(list((tmp_path / "quiz_banks").glob("*.json"))) == 3
    assert len(list((tmp_path / "videos").glob("*.json"))) == 3
    assert len(list((tmp_path / "learners").iterdir())) == 2
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["live"] is False
    assert metrics["jobs"] == {"succeeded": 11}
    assert metrics["quiz_items"] == {"1": 23, "2": 23, "3": 23}
    assert metrics["faithfulness_mean"] == 1.0
    assert metrics["videos_selected"] == 3
    assert metrics["llm"]["invalid_json_rate"] == 0.0
    assert metrics["consistency_issues"] == []
    assert report.as_result()["output_dir"] == str(tmp_path)


async def test_the_log_has_one_line_per_call_with_job_ids(tmp_path: Path) -> None:
    await run_pipeline(options(tmp_path), build_fake_runtime())
    lines = (tmp_path / "llm_log.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert rows and {"task", "prompt_id", "status", "latency_ms", "cost_usd"} <= set(rows[0])
    assert any(r["ai_job_id"] for r in rows)
    assert {r["status"] for r in rows} == {"success"}


async def test_the_run_is_deterministic(tmp_path: Path) -> None:
    await run_pipeline(options(tmp_path / "a"), build_fake_runtime())
    await run_pipeline(options(tmp_path / "b"), build_fake_runtime())
    for name in ("final_bank.json", "quiz_banks/3.json", "explanations/2.json"):
        a = json.loads((tmp_path / "a" / name).read_text(encoding="utf-8"))
        b = json.loads((tmp_path / "b" / name).read_text(encoding="utf-8"))
        a["meta"].pop("generated_at")
        b["meta"].pop("generated_at")
        assert a == b


async def test_the_consistency_check_finds_what_is_missing() -> None:
    from app.ports.catalog import TopicRecord

    issues = verify_consistency(Package(topics=[TopicRecord("1", 1, "T", "d")]))
    assert "1: no explanation" in issues
    assert "1: no quiz bank" in issues
    assert "no final bank" in issues


def test_percentile() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([5], 0.5) == 5.0
    assert percentile(list(range(1, 101)), 0.95) == 95.0
    assert log_metrics([])["llm_calls"] == 0


def test_the_live_run_needs_the_owner_to_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(LiveEvaluationNotAllowedError, match="AI_EVAL_LIVE"):
        build_live_runtime(Settings(ai_eval_live=False))


def test_the_live_run_is_refused_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    with pytest.raises(LiveEvaluationNotAllowedError, match="CI"):
        build_live_runtime(Settings(ai_eval_live=True))


def test_the_live_run_needs_the_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(LiveEvaluationNotAllowedError, match="incomplete configuration"):
        build_live_runtime(Settings(ai_eval_live=True, ai_llm_provider=None))


def test_the_command_line_writes_a_package_and_refuses_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AI_EVAL_LIVE", raising=False)
    assert main(["--out", str(tmp_path / "run")]) == 0
    assert (tmp_path / "run" / "metrics.json").is_file()
    assert main(["--live", "--out", str(tmp_path / "live")]) == 2
