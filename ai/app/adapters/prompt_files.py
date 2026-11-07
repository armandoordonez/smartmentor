"""``FilePromptStore``: reads ``prompts/catalog.yaml``, ``prompts/<id>/v<n>.md`` and the schemas.

Everything is loaded once at start-up. Problems (a file whose SHA-256 differs from the catalog,
a missing file or schema, a front matter that disagrees) are collected and reported by
``verify()``, which ``/ready`` uses; a prompt with problems is not served.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

import yaml

from app.ports.prompts import (
    ModelTier,
    PromptCatalogEntry,
    PromptNotFoundError,
    PromptTemplate,
)

_FRONT_MATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_SECTIONS = re.compile(
    r"^## system\n(?P<system>.*?)^## user\n(?P<user>.*)\Z", re.DOTALL | re.MULTILINE
)


def _tier(value: object) -> ModelTier:
    if value == "default" or value == "small":
        return value
    raise ValueError(f"unknown model_tier {value!r}")


class FilePromptStore:
    def __init__(self, prompts_dir: Path) -> None:
        self._dir = prompts_dir
        self._issues: list[str] = []
        self._entries: dict[str, PromptCatalogEntry] = {}
        self._templates: dict[tuple[str, int], PromptTemplate] = {}
        self._load()

    # ---------- loading ----------

    def _load(self) -> None:
        catalog_path = self._dir / "catalog.yaml"
        try:
            catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            self._issues.append(f"cannot read {catalog_path.name}: {exc.__class__.__name__}")
            return
        for raw in catalog.get("prompts", []):
            try:
                entry = PromptCatalogEntry(
                    id=str(raw["id"]),
                    name_es=str(raw["name_es"]),
                    task=str(raw["task"]),
                    current_version=int(raw["current_version"]),
                    model_tier=_tier(raw["model_tier"]),
                    temperature=float(raw["temperature"]),
                    output_schema=str(raw["output_schema"]),
                    contract=str(raw["contract"]),
                    screens=tuple(str(s) for s in raw.get("screens", [])),
                    versions={int(k): str(v) for k, v in raw["versions"].items()},
                )
            except (KeyError, TypeError, ValueError) as exc:
                self._issues.append(f"invalid catalog entry {raw!r:.60}: {exc}")
                continue
            self._entries[entry.id] = entry
            for version, digest in entry.versions.items():
                template = self._load_version(entry, version, digest)
                if template is not None:
                    self._templates[(entry.id, version)] = template

    def _load_version(
        self, entry: PromptCatalogEntry, version: int, digest: str
    ) -> PromptTemplate | None:
        path = self._dir / entry.id / f"v{version}.md"
        tag = f"{entry.id}/v{version}.md"
        try:
            content = path.read_bytes()
        except OSError:
            self._issues.append(f"{tag}: file is missing")
            return None
        if hashlib.sha256(content).hexdigest() != digest:
            self._issues.append(f"{tag}: sha256 differs from catalog.yaml")
            return None
        match = _FRONT_MATTER.match(content.decode("utf-8"))
        sections = _SECTIONS.search(match["body"]) if match else None
        if match is None or sections is None:
            self._issues.append(f"{tag}: missing front matter or system/user sections")
            return None
        meta: dict[str, Any] = yaml.safe_load(match["meta"])
        if meta.get("id") != entry.id or meta.get("version") != version:
            self._issues.append(f"{tag}: front matter id or version disagrees with its path")
            return None
        schema = self._schema(tag, str(meta.get("output_schema", "")))
        if schema is None:
            return None
        variables: dict[str, Any] = meta.get("variables") or {}
        return PromptTemplate(
            id=entry.id,
            version=version,
            name_es=str(meta.get("name_es", entry.name_es)),
            task=str(meta.get("task", entry.task)),
            temperature=float(meta.get("temperature", entry.temperature)),
            model_tier=_tier(meta.get("model_tier", entry.model_tier)),
            output_schema_name=str(meta["output_schema"]),
            output_schema=schema,
            contract=str(meta.get("contract", entry.contract)),
            data_variables=tuple(variables.get("data") or ()),
            parameter_variables=tuple(variables.get("parameters") or ()),
            system=sections["system"].strip(),
            user=sections["user"].strip(),
            sha256=digest,
        )

    def _schema(self, tag: str, relative: str) -> dict[str, Any] | None:
        path = self._dir / "schemas" / relative
        try:
            return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            self._issues.append(f"{tag}: output schema {relative} is missing or invalid")
            return None

    # ---------- port ----------

    def get(self, prompt_id: str, version: int | None = None) -> PromptTemplate:
        entry = self._entries.get(prompt_id)
        if entry is None:
            raise PromptNotFoundError(prompt_id)
        template = self._templates.get((prompt_id, version or entry.current_version))
        if template is None:
            raise PromptNotFoundError(f"{prompt_id} v{version or entry.current_version}")
        return template

    def catalog(self) -> list[PromptCatalogEntry]:
        return list(self._entries.values())

    def verify(self) -> list[str]:
        issues = list(self._issues)
        if not self._entries and not issues:
            issues.append("catalog.yaml has no prompts")
        return issues
