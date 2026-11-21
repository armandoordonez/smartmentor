"""E8 report: latency, invalid JSON, timeouts, tokens and cost of the LLM calls.

Reads the log that the API exposes to administrators (``GET /api/v1/llm-call-logs``, read only)
or a JSON file exported from it, and cuts it by task, by course and by moment (before/after the
fix of B-013, which raised the LLM timeout from 120 s to 240 s).

Usage (from ``ai/``)::

    SMARTMENTOR_TOKEN=<access token> python -m eval.llm_report --base-url http://localhost:8020
    python -m eval.llm_report --logs-file logs.json --enrollments-file enrollments.json

The token comes only from the environment or from ``--token-file``; it is never printed. The
output is Markdown tables with no personal data (the log has none: only task, model, ids).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Moment B-013 was fixed (BUGS.md: 2026-11-13 10:31, America/Bogota = UTC-5).
DEFAULT_CUTOFF = "2026-11-13T15:31:00Z"
# E8 targets (docs/cohorte_1/evaluation/metrics.md): p95 < 20 s and invalid JSON < 2 %.
P95_TARGET_MS = 20_000.0
INVALID_TARGET_PCT = 2.0
NO_COURSE = "sin curso"
UNKNOWN_COURSE = "curso sin inscripción visible"

Row = Mapping[str, Any]


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp (``Z`` suffix allowed); naive values are taken as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def percentile(values: Sequence[float], q: float) -> float | None:
    """Percentile ``q`` (0-100) by linear interpolation, like ``numpy.percentile``."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def is_timeout(row: Row) -> bool:
    return str(row.get("error_message") or "").startswith("LlmTimeoutError")


def is_invalid(row: Row) -> bool:
    """Invalid output: JSON that does not parse or fails the schema/item checks."""
    return row.get("json_valid") is False or row.get("status") == "invalid_output"


@dataclass(frozen=True)
class Stats:
    calls: int
    provider_calls: int  # calls that reached the provider (not served from cache)
    p50_ms: float | None
    p95_ms: float | None
    max_ms: float | None
    invalid: int
    invalid_pct: float | None
    unparsable: int  # json_valid = false (strict reading of the E8 formula)
    retries: int  # attempts after the first one
    retries_pct: float | None
    timeouts: int
    errors: int  # every call with status "error" (timeouts included)
    input_tokens: int
    output_tokens: int
    cost_usd: float


def summarise(rows: Iterable[Row]) -> Stats:
    """Compute the E8 figures for a group of log rows (latency excludes cache hits)."""
    items = list(rows)
    live = [r for r in items if not r.get("from_cache")]
    latencies = [float(r["latency_ms"]) for r in live if r.get("latency_ms") is not None]
    invalid = sum(is_invalid(r) for r in live)
    retries = sum(int(r.get("call_attempt") or 1) > 1 for r in live)
    return Stats(
        calls=len(items),
        provider_calls=len(live),
        p50_ms=percentile(latencies, 50),
        p95_ms=percentile(latencies, 95),
        max_ms=max(latencies) if latencies else None,
        invalid=invalid,
        invalid_pct=100 * invalid / len(live) if live else None,
        unparsable=sum(r.get("json_valid") is False for r in live),
        retries=retries,
        retries_pct=100 * retries / len(live) if live else None,
        timeouts=sum(is_timeout(r) for r in live),
        errors=sum(r.get("status") == "error" for r in live),
        input_tokens=sum(int(r.get("input_tokens") or 0) for r in items),
        output_tokens=sum(int(r.get("output_tokens") or 0) for r in items),
        cost_usd=sum(float(r.get("cost_usd") or 0) for r in items),
    )


def course_by_enrollment(enrollments: Iterable[Row]) -> dict[int, str]:
    """Map enrollment id -> course name (the learning path carries the course name)."""
    return {int(e["id"]): str(e["learning_path"]["name"]) for e in enrollments}


def course_of(row: Row, courses: Mapping[int, str]) -> str:
    enrollment_id = row.get("enrollment_id")
    if enrollment_id is None:
        return NO_COURSE
    return courses.get(int(enrollment_id), UNKNOWN_COURSE)


def split_by_moment(rows: Iterable[Row], cutoff: datetime) -> dict[str, list[Row]]:
    """Rows before and from ``cutoff`` (rows without ``created_at`` are left out)."""
    moments: dict[str, list[Row]] = {"antes": [], "despues": []}
    for row in rows:
        created = row.get("created_at")
        if not created:
            continue
        moments["antes" if parse_timestamp(str(created)) < cutoff else "despues"].append(row)
    return moments


def group_stats(rows: Iterable[Row], key: Any) -> dict[str, Stats]:
    """Stats per group, where ``key(row)`` gives the group name; sorted by name."""
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return {name: summarise(groups[name]) for name in sorted(groups)}


def build_report(
    logs: Sequence[Row], enrollments: Sequence[Row], cutoff: datetime
) -> dict[str, Any]:
    """All the cuts of E8: total, per task, per course, per moment and task x moment."""
    courses = course_by_enrollment(enrollments)
    moments = split_by_moment(logs, cutoff)
    return {
        "total": summarise(logs),
        "by_task": group_stats(logs, lambda r: r["task"]),
        "by_course": group_stats(logs, lambda r: course_of(r, courses)),
        "by_moment": {name: summarise(rows) for name, rows in moments.items()},
        "by_task_moment": {
            name: group_stats(rows, lambda r: r["task"]) for name, rows in moments.items()
        },
        "by_model": group_stats(logs, lambda r: r.get("model") or "?"),
        "period": (
            min(str(r["created_at"]) for r in logs if r.get("created_at")) if logs else None,
            max(str(r["created_at"]) for r in logs if r.get("created_at")) if logs else None,
        ),
    }


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value / 1000:.1f}".replace(".", ",")


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} %".replace(".", ",")


def _money(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def table(label: str, groups: Mapping[str, Stats], total: Stats | None = None) -> str:
    """Markdown table with one row per group (and an optional total row)."""
    header = (
        f"| {label} | Llamadas | p50 (s) | p95 (s) | Máx (s) | JSON inválido | Reintentos "
        "| Timeouts | Tokens (ent./sal.) | Costo (US$) |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )

    def line(name: str, s: Stats) -> str:
        return (
            f"| {name} | {s.calls} | {_seconds(s.p50_ms)} | {_seconds(s.p95_ms)} "
            f"| {_seconds(s.max_ms)} | {s.invalid} ({_pct(s.invalid_pct)}) "
            f"| {s.retries} ({_pct(s.retries_pct)}) | {s.timeouts} "
            f"| {_thousands(s.input_tokens)} / {_thousands(s.output_tokens)} "
            f"| {_money(s.cost_usd)} |"
        )

    rows = [line(f"`{n}`" if label == "Tarea" else n, s) for n, s in groups.items()]
    if total is not None:
        rows.append(line("**Total**", total))
    return "\n".join([header, *rows])


def summary_course_table(summary: Mapping[str, Any]) -> str:
    """Calls and cost per course as the API computes them (it knows the job's course)."""
    lines = [
        "| Curso (id) | Llamadas | Costo (US$) |",
        "| --- | ---: | ---: |",
    ]
    for item in summary.get("by_course", []):
        course = item["course_id"] if item["course_id"] is not None else NO_COURSE
        lines.append(f"| {course} | {item['calls']} | {_money(float(item['cost_usd']))} |")
    return "\n".join(lines)


def render_markdown(report: Mapping[str, Any], summary: Mapping[str, Any] | None = None) -> str:
    """The report as Markdown tables (no prose: the conclusions are written by a person)."""
    total: Stats = report["total"]
    parts = [
        f"Periodo del log: {report['period'][0]} a {report['period'][1]}.",
        "### Por tarea\n\n" + table("Tarea", report["by_task"], total),
        "### Por curso (solo llamadas ligadas a una inscripción)\n\n"
        + table("Curso", report["by_course"], total),
        "### Por modelo\n\n" + table("Modelo", report["by_model"], total),
        "### Antes y después de B-013\n\n" + table("Momento", report["by_moment"]),
    ]
    for name, groups in report["by_task_moment"].items():
        parts.append(f"### Por tarea, {name} de B-013\n\n" + table("Tarea", groups))
    if summary is not None:
        parts.append(
            "### Llamadas y costo por curso según el resumen de la API\n\n"
            + summary_course_table(summary)
        )
    return "\n\n".join(parts) + "\n"


def _get_json(url: str, token: str) -> Any:
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme: {url}")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def fetch_all(base_url: str, path: str, token: str, page_size: int = 100) -> list[Row]:
    """Read every page of a paginated list endpoint. Only GET requests are made."""
    items: list[Row] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({"limit": page_size, "offset": offset})
        page = _get_json(f"{base_url.rstrip('/')}/api/v1{path}?{query}", token)
        items.extend(page["items"])
        offset += page_size
        if offset >= page["total"]:
            return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.llm_report", description=__doc__)
    parser.add_argument("--base-url", help="API base URL, e.g. http://localhost:8020")
    parser.add_argument("--token-file", type=Path, help="file with the access token")
    parser.add_argument("--logs-file", type=Path, help="JSON list exported from llm-call-logs")
    parser.add_argument("--summary-file", type=Path, help="JSON of llm-call-logs/summary")
    parser.add_argument("--enrollments-file", type=Path, help="JSON list of {id, learning_path}")
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF, help="ISO 8601 instant (B-013 fix)")
    parser.add_argument(
        "--save-raw-dir", type=Path, help="where to save what was read (outside the repo)"
    )
    args = parser.parse_args(argv)

    summary: Mapping[str, Any] | None = None
    if args.logs_file:
        if args.summary_file:
            summary = json.loads(args.summary_file.read_text(encoding="utf-8"))
        logs = json.loads(args.logs_file.read_text(encoding="utf-8"))
        enrollments = (
            json.loads(args.enrollments_file.read_text(encoding="utf-8"))
            if args.enrollments_file
            else []
        )
    elif args.base_url:
        token = (
            args.token_file.read_text(encoding="utf-8").strip()
            if args.token_file
            else os.environ.get("SMARTMENTOR_TOKEN", "")
        )
        if not token:
            print("falta el token: SMARTMENTOR_TOKEN o --token-file", file=sys.stderr)  # noqa: T201
            return 2
        logs = fetch_all(args.base_url, "/llm-call-logs", token)
        enrollments = [
            {"id": e["id"], "learning_path": e["learning_path"]}
            for e in fetch_all(args.base_url, "/enrollments", token)
        ]
        summary = _get_json(f"{args.base_url.rstrip('/')}/api/v1/llm-call-logs/summary", token)
        if args.save_raw_dir:
            args.save_raw_dir.mkdir(parents=True, exist_ok=True)
            (args.save_raw_dir / "logs.json").write_text(json.dumps(logs), encoding="utf-8")
            (args.save_raw_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            (args.save_raw_dir / "enrollments.json").write_text(
                json.dumps(enrollments), encoding="utf-8"
            )
    else:
        parser.error("use --base-url or --logs-file")

    report = build_report(logs, enrollments, parse_timestamp(args.cutoff))
    print(render_markdown(report, summary))  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
