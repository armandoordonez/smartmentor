"""Shared helpers for the contract tests: repository paths and prompt file parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"
SCHEMAS_DIR = PROMPTS_DIR / "schemas"
EXAMPLES_DIR = PROMPTS_DIR / "examples"
CATALOG_PATH = PROMPTS_DIR / "catalog.yaml"

_FRONT_MATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_SECTIONS = re.compile(r"^## system\n(?P<system>.*?)^## user\n(?P<user>.*)\Z", re.DOTALL | re.M)


@dataclass(frozen=True)
class PromptFile:
    path: Path
    meta: dict[str, Any]
    system: str
    user: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")))


def parse_prompt(path: Path) -> PromptFile:
    """Parse ``<id>/v<n>.md``: YAML front matter, then ``## system`` and ``## user``."""
    text = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError(f"{path}: missing front matter")
    sections = _SECTIONS.search(match["body"])
    if sections is None:
        raise ValueError(f"{path}: missing '## system' or '## user' section")
    meta = cast(dict[str, Any], yaml.safe_load(match["meta"]))
    return PromptFile(path, meta, sections["system"].strip(), sections["user"].strip())
