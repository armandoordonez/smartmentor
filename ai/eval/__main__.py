"""``python -m eval``: run the evaluation pipeline and print where the package was saved.

Offline by default (fake LLM and embeddings). ``--live`` needs ``AI_EVAL_LIVE=1`` and the real
configuration; it is never used in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from eval.pipeline import DEFAULT_SYLLABUS, PipelineOptions, run_pipeline
from eval.runtime import LiveEvaluationNotAllowedError, build_fake_runtime, build_live_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__)
    parser.add_argument("--syllabus", type=Path, default=DEFAULT_SYLLABUS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--live", action="store_true", help="real providers (AI_EVAL_LIVE=1)")
    args = parser.parse_args(argv)
    if args.live:
        try:
            runtime = build_live_runtime(get_settings())
        except LiveEvaluationNotAllowedError as exc:
            print(f"live run refused: {exc}", file=sys.stderr)  # noqa: T201
            return 2
    else:
        runtime = build_fake_runtime()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    out = args.out or REPO_ROOT / "data" / "examples" / f"ai-run-{stamp}"
    options = PipelineOptions(syllabus_text=args.syllabus.read_text(encoding="utf-8"), out_dir=out)
    report = asyncio.run(run_pipeline(options, runtime))
    print(f"package: {report.output_dir}")  # noqa: T201
    print(f"consistency issues: {len(report.issues)}")  # noqa: T201
    return 0 if not report.issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
