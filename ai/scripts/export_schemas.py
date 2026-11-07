"""Export the Pydantic contracts to ``prompts/schemas/*.v1.json``.

Usage (from ``ai/``)::

    uv run python -m scripts.export_schemas            # write the files
    uv run python -m scripts.export_schemas --check    # exit 1 if a file is missing or stale

The output is deterministic (same models -> same bytes), so a second run leaves no diff.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.domain.contracts.registry import all_schemas, build_schema, schema_relative_path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "prompts" / "schemas"


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def expected_files() -> dict[str, str]:
    """Relative path -> file content for every registered schema."""
    return {
        schema_relative_path(name, kind): render(build_schema(name, kind, model))
        for name, kind, model in all_schemas()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="only compare, do not write")
    args = parser.parse_args(argv)
    output: Path = args.output

    stale: list[str] = []
    for relative, content in expected_files().items():
        target = output / relative
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == content:
            continue
        stale.append(relative)
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    if args.check and stale:
        sys.stderr.write("Stale schemas (run scripts.export_schemas): " + ", ".join(stale) + "\n")
        return 1
    action = "would update" if args.check else "updated"
    sys.stdout.write(f"{len(expected_files())} schemas, {len(stale)} {action}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
