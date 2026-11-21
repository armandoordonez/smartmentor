"""E2: ¿qué tanto de los temas y prerrequisitos de un syllabus extrae bien cada modelo?

Todo sale de archivos locales: no toca la base, la API ni los contenedores, y no usa datos
personales. Subcomandos:

1. ``run``: corre ``EvalWorld.structure_syllabus`` N veces por modelo, **cada vez en un proceso
   nuevo** (la caché en memoria del arnés nace vacía, así cada repetición es independiente).
   ``AI_LLM_MODEL_DEFAULT`` se fija solo en el entorno del subproceso. Guarda por repetición
   ``<out>/<curso>/<modelo>/rep<N>.json`` con la salida completa (``Syllabus``), costo y latencia.
   Si una repetición sale de la caché (``meta.from_cache``), el experimento falla.
   Usa los proveedores reales: pide ``AI_EVAL_LIVE=1`` y ``AI_LLM_PROVIDER=gemini``, y la clave
   llega por el entorno (nunca se imprime ni se guarda).
2. ``export-gold-sheet``: plantilla CSV (``course_key,kind,name,prerequisite_of``) para que un
   agente-instructor escriba el oro, a ciegas, como **nombres** de temas y prerrequisitos.
3. ``export-matching-sheet``: por extracción, los temas extraídos y los de oro, para que un juez
   diga qué tema extraído equivale a cuál de oro.
4. ``match``: aplica ese emparejamiento y calcula precisión, recall y F1 (``set_f1``) de temas y de
   prerrequisitos, por modelo y repetición, con media y rango.

Uso (desde ``ai/``)::

    python -m eval.syllabus_experiment run --syllabus s.md --model gemini-3.8-flash --out e2/
    python -m eval.syllabus_experiment export-gold-sheet --course-key s --out e2/oro.csv
    python -m eval.syllabus_experiment export-matching-sheet --gold e2/oro.csv \
        --run-dir e2/ --out e2/emparejar.json
    python -m eval.syllabus_experiment match --gold e2/oro.csv --run-dir e2/ \
        --mapping e2/emparejar.json --out e2/resultado.md
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.metrics import SetScores, set_f1

DEFAULT_REPETITIONS = 3
GOLD_COLUMNS = ("course_key", "kind", "name", "prerequisite_of")
KIND_TOPIC = "topic"
KIND_PREREQUISITE = "prerequisite"
F1_TARGET = 0.85
WORKER_TIMEOUT_SECONDS = 900
UNMATCHED_PREFIX = "\u0000sin_emparejar:"  # no puede chocar con un nombre de oro


class FromCacheError(RuntimeError):
    """Una repetición salió de la caché: no es independiente y el experimento no vale."""


class MappingError(ValueError):
    """El archivo de emparejamiento es incompleto o nombra temas que no están en el oro."""


# --------------------------------------------------------------------------------------------
# Texto y nombres
# --------------------------------------------------------------------------------------------


def normalize(name: str) -> str:
    """Forma de comparar nombres: sin mayúsculas ni espacios de más."""
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _num(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


# --------------------------------------------------------------------------------------------
# run (proceso padre) y worker (proceso hijo)
# --------------------------------------------------------------------------------------------


def worker_env(base: Mapping[str, str], model: str) -> dict[str, str]:
    """Entorno del subproceso: el modelo y el permiso de uso real, sin tocar el del padre."""
    env = dict(base)
    env["AI_LLM_MODEL_DEFAULT"] = model
    env["AI_EVAL_LIVE"] = "1"
    return env


def run_path(out_dir: Path, course_key: str, model: str, repetition: int) -> Path:
    return out_dir / course_key / model / f"rep{repetition}.json"


def validate_run(record: Mapping[str, Any]) -> None:
    """Falla si la repetición vino de la caché o no trae la salida completa."""
    syllabus = record.get("syllabus")
    if not isinstance(syllabus, Mapping) or not isinstance(syllabus.get("meta"), Mapping):
        raise ValueError("la repetición no trae `syllabus.meta`")
    if syllabus["meta"].get("from_cache") is not False:
        raise FromCacheError(
            f"{record.get('course_key')}/{record.get('requested_model')} "
            f"rep{record.get('repetition')}: `meta.from_cache` no es false"
        )


def _redact(text: str, secrets: Iterable[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def run_experiment(
    syllabus: Path,
    models: Sequence[str],
    repetitions: int,
    out_dir: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    """``repetitions`` procesos nuevos por modelo; devuelve los JSON escritos."""
    base = dict(os.environ if environ is None else environ)
    if base.get("AI_LLM_PROVIDER") != "gemini":
        raise RuntimeError("E2 se corre solo con AI_LLM_PROVIDER=gemini")
    course_key = syllabus.stem
    secrets = [base.get("GEMINI_API_KEY", ""), base.get("YOUTUBE_API_KEY", "")]
    written: list[Path] = []
    for model in models:
        for repetition in range(1, repetitions + 1):
            target = run_path(out_dir, course_key, model, repetition)
            target.parent.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable,
                "-m",
                "eval.syllabus_experiment",
                "worker",
                "--syllabus",
                str(syllabus),
                "--out",
                str(target),
                "--model",
                model,
                "--repetition",
                str(repetition),
            ]
            done = subprocess.run(  # noqa: S603 (comando fijo, sin shell)
                command,
                env=worker_env(base, model),
                capture_output=True,
                text=True,
                timeout=WORKER_TIMEOUT_SECONDS,
                check=False,
            )
            if done.returncode != 0:
                tail = _redact("\n".join(done.stderr.strip().splitlines()[-5:]), secrets)
                raise RuntimeError(
                    f"{course_key}/{model} rep{repetition}: el proceso terminó con "
                    f"código {done.returncode}\n{tail}"
                )
            validate_run(json.loads(target.read_text(encoding="utf-8")))
            written.append(target)
    return written


async def _structure(syllabus: Path, text: str, model: str, repetition: int) -> dict[str, Any]:
    # Importes tardíos: los demás subcomandos no necesitan el arnés ni los proveedores.
    from app.core.config import get_settings
    from eval.pipeline import EvalWorld, PipelineOptions
    from eval.runtime import build_live_runtime

    runtime = build_live_runtime(get_settings())
    world = EvalWorld(PipelineOptions(syllabus_text=text, out_dir=Path("/nonexistent")), runtime)
    result = await world.structure_syllabus()
    rows = world.logs.rows
    return {
        "course_key": syllabus.stem,
        "requested_model": model,
        "repetition": repetition,
        "syllabus": result.model_dump(mode="json"),
        "llm_calls": sum(not r.from_cache for r in rows),
        "cost_usd": str(sum((r.cost_usd or Decimal(0) for r in rows), Decimal(0))),
        "latency_ms": sum(r.latency_ms for r in rows if not r.from_cache),
    }


def worker(syllabus: Path, out: Path, model: str, repetition: int) -> None:
    text = syllabus.read_text(encoding="utf-8")
    record = asyncio.run(_structure(syllabus, text, model, repetition))
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------------
# Oro
# --------------------------------------------------------------------------------------------


def gold_sheet_rows(course_keys: Sequence[str]) -> list[dict[str, str]]:
    """Plantilla vacía: una fila de tema y una de prerrequisito por curso, para llenar y copiar."""
    rows: list[dict[str, str]] = []
    for key in course_keys:
        rows.append({"course_key": key, "kind": KIND_TOPIC, "name": "", "prerequisite_of": ""})
        rows.append(
            {"course_key": key, "kind": KIND_PREREQUISITE, "name": "", "prerequisite_of": ""}
        )
    return rows


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


@dataclass(frozen=True)
class Gold:
    topics: dict[str, str]  # nombre normalizado -> nombre escrito por el agente
    prerequisites: frozenset[tuple[str, str]]  # (prerrequisito, tema), normalizados


def read_gold(rows: Iterable[Mapping[str, str]]) -> dict[str, Gold]:
    """Oro por curso. Las filas sin nombre (la plantilla vacía) se ignoran."""
    topics: dict[str, dict[str, str]] = defaultdict(dict)
    pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        course = (row.get("course_key") or "").strip()
        name = (row.get("name") or "").strip()
        kind = (row.get("kind") or "").strip().lower()
        if not course or not name:
            continue
        if kind == KIND_TOPIC:
            topics[course][normalize(name)] = name
        elif kind == KIND_PREREQUISITE:
            owner = (row.get("prerequisite_of") or "").strip()
            if not owner:
                raise ValueError(f"{course}: el prerrequisito «{name}» no dice de qué tema es")
            pairs[course].add((normalize(name), normalize(owner)))
        else:
            raise ValueError(f"{course}: `kind` debe ser topic o prerequisite, no «{kind}»")
    gold: dict[str, Gold] = {}
    for course in topics:
        known = topics[course]
        for pre, owner in pairs[course]:
            if pre not in known or owner not in known:
                raise ValueError(f"{course}: el prerrequisito {pre} > {owner} usa un tema ausente")
        gold[course] = Gold(known, frozenset(pairs[course]))
    return gold


def read_gold_file(path: Path) -> dict[str, Gold]:
    with path.open(encoding="utf-8", newline="") as handle:
        return read_gold(csv.DictReader(handle))


# --------------------------------------------------------------------------------------------
# Extracciones y hoja de emparejamiento
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Extraction:
    extraction_id: str
    course_key: str
    model: str
    repetition: int
    topics: dict[str, str]  # id extraído -> nombre
    prerequisites: frozenset[tuple[str, str]]  # (id del prerrequisito, id del tema)
    cost_usd: Decimal
    latency_ms: int


def parse_run(record: Mapping[str, Any]) -> Extraction:
    validate_run(record)
    syllabus = record["syllabus"]
    course, model, rep = record["course_key"], record["requested_model"], int(record["repetition"])
    topics = {t["id"]: t["name"] for t in syllabus["topics"]}
    pairs = frozenset((p, t["id"]) for t in syllabus["topics"] for p in t["prerequisites"])
    return Extraction(
        extraction_id=f"{course}/{model}/rep{rep}",
        course_key=course,
        model=model,
        repetition=rep,
        topics=topics,
        prerequisites=pairs,
        cost_usd=Decimal(str(record.get("cost_usd", "0"))),
        latency_ms=int(record.get("latency_ms", 0)),
    )


def read_runs(run_dir: Path) -> list[Extraction]:
    paths = sorted(run_dir.glob("*/*/rep*.json"))
    if not paths:
        raise FileNotFoundError(f"no hay repeticiones en {run_dir} (<curso>/<modelo>/rep<N>.json)")
    runs = [parse_run(json.loads(p.read_text(encoding="utf-8"))) for p in paths]
    return sorted(runs, key=lambda e: (e.course_key, e.model, e.repetition))


def matching_sheet(runs: Sequence[Extraction], gold: Mapping[str, Gold]) -> dict[str, Any]:
    """Para cada extracción: temas extraídos, temas de oro y un ``mapping`` por llenar."""
    items: list[dict[str, Any]] = []
    for run in runs:
        if run.course_key not in gold:
            raise MappingError(f"el oro no tiene el curso {run.course_key}")
        items.append(
            {
                "extraction_id": run.extraction_id,
                "extracted_topics": [{"id": i, "name": n} for i, n in run.topics.items()],
                "gold_topics": sorted(gold[run.course_key].topics.values()),
                "mapping": dict.fromkeys(run.topics),
            }
        )
    return {
        "instructions": (
            "Para cada tema extraído, escribe en `mapping[<id>]` el nombre EXACTO del tema de oro "
            "que equivale, o deja null si ninguno equivale. Juzga por el sentido del nombre, no "
            "por la redacción. Dos temas extraídos pueden apuntar al mismo tema de oro."
        ),
        "extractions": items,
    }


def load_mapping(raw: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    """Acepta la hoja llenada (``extractions``) o un dict ``extraction_id -> mapping``."""
    if isinstance(raw.get("extractions"), list):
        return {item["extraction_id"]: dict(item["mapping"]) for item in raw["extractions"]}
    return {k: dict(v) for k, v in raw.items() if isinstance(v, Mapping)}


# --------------------------------------------------------------------------------------------
# Emparejamiento y F1
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scores:
    topics: SetScores
    prerequisites: SetScores
    unmatched: int
    extracted: int


def score_extraction(
    run: Extraction, gold: Gold, mapping: Mapping[str, str | None] | None
) -> Scores:
    """F1 de temas y prerrequisitos tras llevar cada tema extraído a su nombre de oro.

    Un tema sin pareja cuenta como predicho falso (baja la precisión). Si dos extraídos van al
    mismo tema de oro, cuentan una vez (el conjunto ignora duplicados).
    """
    if mapping is None:
        raise MappingError(f"{run.extraction_id}: falta en el emparejamiento")
    missing = [i for i in run.topics if i not in mapping]
    if missing:
        raise MappingError(f"{run.extraction_id}: sin entrada para {missing}")
    resolved: dict[str, str] = {}
    unmatched = 0
    for topic_id in run.topics:
        target = mapping[topic_id]
        if target is None or not target.strip():
            resolved[topic_id] = f"{UNMATCHED_PREFIX}{topic_id}"
            unmatched += 1
        elif normalize(target) in gold.topics:
            resolved[topic_id] = normalize(target)
        else:
            raise MappingError(f"{run.extraction_id}: «{target}» no es un tema de oro")
    topics = set_f1(set(resolved.values()), set(gold.topics))
    predicted_pairs = {(resolved[p], resolved[t]) for p, t in run.prerequisites}
    prerequisites = set_f1(predicted_pairs, set(gold.prerequisites))
    return Scores(topics, prerequisites, unmatched, len(run.topics))


@dataclass(frozen=True)
class Summary:
    mean: float
    low: float
    high: float


def summarize(values: Sequence[float]) -> Summary:
    return Summary(statistics.fmean(values), min(values), max(values))


@dataclass
class Group:
    course_key: str
    model: str
    runs: list[tuple[Extraction, Scores]] = field(default_factory=list)


def evaluate(
    runs: Sequence[Extraction],
    gold: Mapping[str, Gold],
    mappings: Mapping[str, Mapping[str, str | None]],
) -> list[Group]:
    groups: dict[tuple[str, str], Group] = {}
    for run in runs:
        if run.course_key not in gold:
            raise MappingError(f"el oro no tiene el curso {run.course_key}")
        scores = score_extraction(run, gold[run.course_key], mappings.get(run.extraction_id))
        group = groups.setdefault((run.course_key, run.model), Group(run.course_key, run.model))
        group.runs.append((run, scores))
    return list(groups.values())


def render(groups: Sequence[Group]) -> str:
    lines = [
        "# E2 · Estructuración del syllabus",
        "",
        "Resultados indicativos: el oro lo escribió un agente a ciegas y el emparejamiento lo "
        "hizo un juez por nombre. Meta de F1: ≥ " + _num(F1_TARGET) + ".",
        "",
        "## Por repetición",
        "",
        "| Curso | Modelo | Rep | P temas | R temas | F1 temas | P prerreq | R prerreq "
        "| F1 prerreq | Sin emparejar | Costo US$ | Latencia ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for g in groups:
        for run, s in sorted(g.runs, key=lambda item: item[0].repetition):
            lines.append(
                f"| {g.course_key} | {g.model} | {run.repetition} | {_num(s.topics.precision)} "
                f"| {_num(s.topics.recall)} | {_num(s.topics.f1)} "
                f"| {_num(s.prerequisites.precision)} "
                f"| {_num(s.prerequisites.recall)} | {_num(s.prerequisites.f1)} "
                f"| {s.unmatched} de {s.extracted} | {run.cost_usd:.4f} | {run.latency_ms} |"
            )
    lines += [
        "",
        "## Media y rango por curso y modelo",
        "",
        "| Curso | Modelo | Rep | F1 temas (media) | F1 temas (rango) | F1 prerreq (media) "
        "| F1 prerreq (rango) | Sin emparejar (total) | Costo medio US$ | Latencia media ms |",
        "| --- | --- | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for g in groups:
        t = summarize([s.topics.f1 for _, s in g.runs])
        p = summarize([s.prerequisites.f1 for _, s in g.runs])
        lines.append(
            f"| {g.course_key} | {g.model} | {len(g.runs)} | {_num(t.mean)} "
            f"| {_num(t.low)} a {_num(t.high)} | {_num(p.mean)} | {_num(p.low)} a {_num(p.high)} "
            f"| {sum(s.unmatched for _, s in g.runs)} "
            f"| {statistics.fmean(float(r.cost_usd) for r, _ in g.runs):.4f} "
            f"| {statistics.fmean(r.latency_ms for r, _ in g.runs):.0f} |"
        )
    lines += ["", "## Por modelo (todos los cursos)", ""]
    lines += [
        "| Modelo | Extracciones | F1 temas (media) | F1 temas (rango) | F1 prerreq (media) "
        "| F1 prerreq (rango) | Sin emparejar |",
        "| --- | ---: | ---: | --- | ---: | --- | ---: |",
    ]
    by_model: dict[str, list[Scores]] = defaultdict(list)
    for g in groups:
        by_model[g.model] += [s for _, s in g.runs]
    for model, scores in sorted(by_model.items()):
        t = summarize([s.topics.f1 for s in scores])
        p = summarize([s.prerequisites.f1 for s in scores])
        lines.append(
            f"| {model} | {len(scores)} | {_num(t.mean)} | {_num(t.low)} a {_num(t.high)} "
            f"| {_num(p.mean)} | {_num(p.low)} a {_num(p.high)} "
            f"| {sum(s.unmatched for s in scores)} de {sum(s.extracted for s in scores)} |"
        )
    return "\n".join(lines) + "\n"


def match(gold_csv: Path, run_dir: Path, mapping_json: Path) -> str:
    gold = read_gold_file(gold_csv)
    runs = read_runs(run_dir)
    mappings = load_mapping(json.loads(mapping_json.read_text(encoding="utf-8")))
    return render(evaluate(runs, gold, mappings))


# --------------------------------------------------------------------------------------------
# Línea de comandos
# --------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.syllabus_experiment", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="extracciones en procesos nuevos (usa el LLM real)")
    run.add_argument("--syllabus", type=Path, required=True)
    run.add_argument("--model", required=True, action="append", help="se puede repetir")
    run.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    run.add_argument("--out", type=Path, required=True)

    inner = commands.add_parser("worker", help="uso interno de `run`")
    inner.add_argument("--syllabus", type=Path, required=True)
    inner.add_argument("--out", type=Path, required=True)
    inner.add_argument("--model", required=True)
    inner.add_argument("--repetition", type=int, required=True)

    gold = commands.add_parser("export-gold-sheet", help="plantilla del oro (CSV)")
    gold.add_argument("--course-key", action="append", required=True, dest="course_keys")
    gold.add_argument("--out", type=Path, required=True)

    sheet = commands.add_parser("export-matching-sheet", help="hoja para el juez")
    sheet.add_argument("--gold", type=Path, required=True)
    sheet.add_argument("--run-dir", type=Path, required=True)
    sheet.add_argument("--out", type=Path, required=True)

    scoring = commands.add_parser("match", help="F1 de temas y prerrequisitos")
    scoring.add_argument("--gold", type=Path, required=True)
    scoring.add_argument("--run-dir", type=Path, required=True)
    scoring.add_argument("--mapping", type=Path, required=True)
    scoring.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.command == "worker":
        worker(args.syllabus, args.out, args.model, args.repetition)
        return 0
    if args.command == "run":
        paths = run_experiment(args.syllabus, args.model, args.repetitions, args.out)
        print(f"{len(paths)} repeticiones guardadas en {args.out}")  # noqa: T201
        return 0
    if args.command == "export-gold-sheet":
        _write_csv(args.out, GOLD_COLUMNS, gold_sheet_rows(args.course_keys))
        print(f"plantilla del oro: {args.out}")  # noqa: T201
        return 0
    if args.command == "export-matching-sheet":
        sheet_data = matching_sheet(read_runs(args.run_dir), read_gold_file(args.gold))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(sheet_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"hoja de emparejamiento ({len(sheet_data['extractions'])} extracciones): {args.out}")  # noqa: T201
        return 0
    text = match(args.gold, args.run_dir, args.mapping)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
