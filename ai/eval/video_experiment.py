"""E6: does the per-topic ranking put relevant videos in the top three, better than simple orders?

Two steps, both from files (no database access and no personal data):

1. ``export``: from the candidates of every topic (a CSV exported from ``video_candidates``,
   see ``docs/cohorte_1/evaluation/e6-videos.md``) it writes one sheet per judge, with the
   videos of each topic in a random order (a different one per judge, fixed seed) and
   **without** their rank, score or YouTube position, plus a key file with that information.
   The judges only fill ``is_relevant`` with ``true`` or ``false``.
2. ``report``: with the key and the judges' sheets it computes the agreement between judges
   (Cohen's kappa), and Precision@3 and nDCG@3 of four orders over the same judged candidates:

   a. random (the expected value over seeded permutations),
   b. YouTube's order (``search_position``),
   c. similarity with the topic only,
   d. the current score (``rank``).

   Relevance is graded: the share of judges that marked the video relevant (nDCG@3). For P@3 a
   video counts as relevant when at least half of the judges marked it so.

Usage (from ``ai/``, plain Python 3.12+ is enough: the metrics use the standard library)::

    python -m eval.video_experiment export --candidates candidatos.csv --out e6/
    python -m eval.video_experiment report --key e6/clave.csv \
        --judges e6/juez_1.csv e6/juez_2.csv --out e6/resultado.md
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.metrics import cohen_kappa, ndcg_at_k, precision_at_k

K = 3
MIN_CANDIDATES = 3  # P@3 is not defined with fewer than 3 judged candidates in the topic
MAX_CANDIDATES = 10  # E6 design: up to 10 candidates per topic
DEFAULT_SEED = 42
RANDOM_PERMUTATIONS = 2000
P3_TARGET = 0.7
KAPPA_TARGET = 0.6
TRUE_WORDS = {"true", "1", "si", "sí", "yes", "pertinente"}
FALSE_WORDS = {"false", "0", "no", "no pertinente"}

JUDGE_COLUMNS = (
    "topic_key",
    "topic_name",
    "youtube_video_id",
    "title",
    "url",
    "judge_slot",
    "is_relevant",
)
KEY_COLUMNS = ("topic_key", "youtube_video_id", "language", "rank", "search_position", "similarity")


@dataclass(frozen=True)
class Candidate:
    topic_key: str
    topic_name: str
    youtube_video_id: str
    title: str
    language: str
    rank: int
    search_position: int | None
    similarity: float | None


# --------------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------------


def _int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(float(value)) if value else None


def _float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def read_candidates(rows: Iterable[Mapping[str, str]]) -> list[Candidate]:
    """Candidates found by YouTube that passed the filters (with ``rank``), not rejected."""
    found: list[Candidate] = []
    for row in rows:
        rank = _int(row.get("rank"))
        if rank is None or (row.get("origin") or "youtube_api") != "youtube_api":
            continue
        if (row.get("status") or "") == "rejected":
            continue
        found.append(
            Candidate(
                topic_key=str(row["topic_id"]).strip(),
                topic_name=(row.get("topic_name") or "").strip(),
                youtube_video_id=row["youtube_video_id"].strip(),
                title=(row.get("title") or "").strip(),
                language=(row.get("language") or "").strip() or "?",
                rank=rank,
                search_position=_int(row.get("search_position")),
                similarity=_float(row.get("similarity")),
            )
        )
    return found


def by_topic(candidates: Iterable[Candidate]) -> dict[str, list[Candidate]]:
    """Up to ``MAX_CANDIDATES`` per topic, by rank; topics with fewer than 3 are left out."""
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.topic_key].append(candidate)
    return {
        topic: sorted(videos, key=lambda c: c.rank)[:MAX_CANDIDATES]
        for topic, videos in sorted(grouped.items(), key=lambda item: _sort_key(item[0]))
        if len(videos) >= MIN_CANDIDATES
    }


def _sort_key(topic: str) -> tuple[int, str]:
    return (int(topic), "") if topic.isdigit() else (sys.maxsize, topic)


def judge_sheet(
    topics: Mapping[str, list[Candidate]], slot: int, seed: int
) -> list[dict[str, str]]:
    """The sheet of one judge: each topic's videos in a random order of their own (blind)."""
    rows: list[dict[str, str]] = []
    for topic, videos in topics.items():
        shuffled = list(videos)
        random.Random(f"{seed}-{slot}-{topic}").shuffle(shuffled)  # noqa: S311 (not crypto)
        rows.extend(
            {
                "topic_key": topic,
                "topic_name": video.topic_name,
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
                "url": f"https://www.youtube.com/watch?v={video.youtube_video_id}",
                "judge_slot": str(slot),
                "is_relevant": "",
            }
            for video in shuffled
        )
    return rows


def key_rows(topics: Mapping[str, list[Candidate]]) -> list[dict[str, str]]:
    return [
        {
            "topic_key": topic,
            "youtube_video_id": v.youtube_video_id,
            "language": v.language,
            "rank": str(v.rank),
            "search_position": "" if v.search_position is None else str(v.search_position),
            "similarity": "" if v.similarity is None else str(v.similarity),
        }
        for topic, videos in topics.items()
        for v in videos
    ]


def _write(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def export(candidates_csv: Path, out_dir: Path, *, judges: int, seed: int) -> str:
    with candidates_csv.open(encoding="utf-8", newline="") as handle:
        candidates = read_candidates(csv.DictReader(handle))
    topics = by_topic(candidates)
    out_dir.mkdir(parents=True, exist_ok=True)
    for slot in range(1, judges + 1):
        _write(out_dir / f"juez_{slot}.csv", JUDGE_COLUMNS, judge_sheet(topics, slot, seed))
    _write(out_dir / "clave.csv", KEY_COLUMNS, key_rows(topics))
    skipped = len({c.topic_key for c in candidates}) - len(topics)
    videos = sum(len(v) for v in topics.values())
    return (
        f"{len(topics)} temas y {videos} videos para juzgar; {skipped} temas quedaron fuera por "
        f"tener menos de {MIN_CANDIDATES} candidatos. Hojas: "
        + ", ".join(f"juez_{s}.csv" for s in range(1, judges + 1))
        + f"; clave: clave.csv (semilla {seed})."
    )


# --------------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------------


def parse_relevance(value: str) -> bool | None:
    text = (value or "").strip().lower()
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    return None


@dataclass(frozen=True)
class Judged:
    candidate: Candidate
    votes: tuple[bool, ...]

    @property
    def graded(self) -> float:
        """Share of the judges that marked the video relevant (gain for nDCG@3)."""
        return sum(self.votes) / len(self.votes)

    @property
    def relevant(self) -> bool:
        """Relevant for P@3 when at least half of the judges said so."""
        return self.graded >= 0.5


Order = Callable[[list[Judged]], list[Judged] | None]


def _by_rank(videos: list[Judged]) -> list[Judged]:
    return sorted(videos, key=lambda j: j.candidate.rank)


def _by_similarity(videos: list[Judged]) -> list[Judged] | None:
    if any(j.candidate.similarity is None for j in videos):
        return None
    return sorted(videos, key=lambda j: (-(j.candidate.similarity or 0.0), j.candidate.rank))


def _by_youtube(videos: list[Judged]) -> list[Judged] | None:
    """YouTube's order; only for topics whose candidates all have their search position."""
    if any(j.candidate.search_position is None for j in videos):
        return None
    return sorted(videos, key=lambda j: j.candidate.search_position or 0)


ORDERS: dict[str, Order] = {
    "c": _by_similarity,
    "b": _by_youtube,
    "d": _by_rank,
}
ORDER_NAMES = {
    "a": "(a) Al azar (esperado)",
    "b": "(b) Orden de YouTube",
    "c": "(c) Solo similitud con el tema",
    "d": "(d) Puntaje vigente (similitud + idioma + duración)",
}


def _scores(ordered: Sequence[Judged], pool: Sequence[Judged]) -> tuple[float, float]:
    p3 = precision_at_k([j.relevant for j in ordered], K)
    ndcg = ndcg_at_k([j.graded for j in ordered], K, ideal_relevances=[j.graded for j in pool])
    return p3, ndcg


def random_scores(videos: Sequence[Judged], seed: str) -> tuple[float, float]:
    """Expected P@3 and nDCG@3 of a random order (mean of seeded permutations)."""
    rng = random.Random(seed)  # noqa: S311 (reproducible sampling, not crypto)
    p3s: list[float] = []
    ndcgs: list[float] = []
    for _ in range(RANDOM_PERMUTATIONS):
        shuffled = list(videos)
        rng.shuffle(shuffled)
        p3, ndcg = _scores(shuffled, videos)
        p3s.append(p3)
        ndcgs.append(ndcg)
    return statistics.fmean(p3s), statistics.fmean(ndcgs)


def read_judgments(rows: Iterable[Mapping[str, str]]) -> dict[tuple[str, str], dict[int, bool]]:
    """``(topic, video) -> {judge slot: relevant}``; blank or unknown answers are skipped."""
    votes: dict[tuple[str, str], dict[int, bool]] = defaultdict(dict)
    for row in rows:
        relevant = parse_relevance(row.get("is_relevant", ""))
        slot = _int(row.get("judge_slot"))
        if relevant is None or slot is None:
            continue
        votes[(row["topic_key"].strip(), row["youtube_video_id"].strip())][slot] = relevant
    return votes


def _key_candidates(rows: Iterable[Mapping[str, str]]) -> list[Candidate]:
    return [
        Candidate(
            topic_key=row["topic_key"].strip(),
            topic_name="",
            youtube_video_id=row["youtube_video_id"].strip(),
            title="",
            language=(row.get("language") or "?").strip() or "?",
            rank=_int(row["rank"]) or 0,
            search_position=_int(row.get("search_position")),
            similarity=_float(row.get("similarity")),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class E6Result:
    judges: int
    kappa: float | None
    kappa_pairs: int
    topics: int
    videos: int
    scores: dict[str, tuple[float, float, int]]  # order -> (P@3, nDCG@3, topics)
    by_language: dict[str, tuple[int, int]]  # language -> (relevant in top 3, videos in top 3)


def analyse(
    key: Sequence[Candidate], votes: Mapping[tuple[str, str], Mapping[int, bool]], seed: int
) -> E6Result:
    slots = sorted({slot for judged in votes.values() for slot in judged})
    first, second = (slots[0], slots[1]) if len(slots) >= 2 else (None, None)
    pairs = [
        (v[first], v[second])
        for v in votes.values()
        if first is not None and second is not None and first in v and second in v
    ]
    kappa = cohen_kappa([a for a, _ in pairs], [b for _, b in pairs]) if pairs else None
    topics: dict[str, list[Judged]] = defaultdict(list)
    for candidate in key:
        judged = votes.get((candidate.topic_key, candidate.youtube_video_id))
        if judged:
            topics[candidate.topic_key].append(Judged(candidate, tuple(judged.values())))
    usable = {t: v for t, v in topics.items() if len(v) >= MIN_CANDIDATES}
    per_order: dict[str, list[tuple[float, float]]] = defaultdict(list)
    language: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for topic, videos in usable.items():
        per_order["a"].append(random_scores(videos, f"{seed}-{topic}"))
        for name, order in ORDERS.items():
            ordered = order(videos)
            if ordered is not None:
                per_order[name].append(_scores(ordered, videos))
        for top in _by_rank(videos)[:K]:
            language[top.candidate.language][0] += int(top.relevant)
            language[top.candidate.language][1] += 1
    scores = {
        name: (
            statistics.fmean(p for p, _ in values),
            statistics.fmean(n for _, n in values),
            len(values),
        )
        for name, values in sorted(per_order.items())
        if values
    }
    return E6Result(
        judges=len(slots),
        kappa=kappa,
        kappa_pairs=len(pairs),
        topics=len(usable),
        videos=sum(len(v) for v in usable.values()),
        scores=scores,
        by_language={k: (v[0], v[1]) for k, v in sorted(language.items())},
    )


def _num(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def render(result: E6Result) -> str:
    lines = [
        "# E6 · Videos por tema",
        "",
        f"Temas con al menos {MIN_CANDIDATES} candidatos juzgados: {result.topics} "
        f"({result.videos} videos). Jueces: {result.judges}.",
        "",
        "## Acuerdo entre jueces",
        "",
    ]
    if result.kappa is None:
        lines.append("Sin videos juzgados por dos jueces: el κ no se calcula.")
    else:
        state = "cumple" if result.kappa >= KAPPA_TARGET else "no cumple"
        lines.append(
            f"κ de Cohen = {_num(result.kappa)} sobre {result.kappa_pairs} videos "
            f"(meta ≥ {_num(KAPPA_TARGET)}: {state})."
        )
    lines += [
        "",
        "## Precision@3 y nDCG@3 por ordenación",
        "",
        "| Ordenación | P@3 | nDCG@3 | Temas |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in ("a", "b", "c", "d"):
        if name in result.scores:
            p3, ndcg, n = result.scores[name]
            lines.append(f"| {ORDER_NAMES[name]} | {_num(p3)} | {_num(ndcg)} | {n} |")
        else:
            lines.append(f"| {ORDER_NAMES[name]} | sin datos | sin datos | 0 |")
    lines += ["", f"Meta de P@3 del puntaje vigente: ≥ {_num(P3_TARGET)}.", ""]
    lines += ["## P@3 del puntaje vigente por idioma del video", ""]
    lines += ["| Idioma | Pertinentes en el top 3 | Videos en el top 3 |", "| --- | ---: | ---: |"]
    for lang, (relevant, total) in result.by_language.items():
        lines.append(f"| {lang} | {relevant} | {total} |")
    lines += ["", "## Regla de decisión (segundo corte, tabla 9)", ""]
    lines += [f"- {line}" for line in decisions(result)]
    return "\n".join(lines) + "\n"


def decisions(result: E6Result) -> list[str]:
    current = result.scores.get("d")
    if current is None:
        return ["Sin datos suficientes para aplicar la regla."]
    out: list[str] = []
    p3 = current[0]
    out.append(
        f"P@3 del puntaje vigente = {_num(p3)}: "
        + ("cumple la meta." if p3 >= P3_TARGET else "no cumple la meta de 0,7.")
    )
    random_p3 = result.scores.get("a", (0.0, 0.0, 0))[0]
    if p3 <= random_p3:
        out.append("El puntaje vigente no supera al azar: el recomendador no aporta.")
    else:
        out.append(f"El puntaje vigente supera al azar ({_num(p3)} frente a {_num(random_p3)}).")
    similarity = result.scores.get("c")
    if similarity is not None and abs(similarity[0] - p3) < 1e-9:
        out.append("Solo la similitud iguala al puntaje vigente: se puede simplificar el puntaje.")
    youtube = result.scores.get("b")
    if youtube is None:
        out.append(
            "Sin el orden de YouTube: los candidatos son anteriores a E6 (sin `search_position`). "
            "Hay que buscar los videos de nuevo (B-064) antes de exportar."
        )
    if p3 < P3_TARGET:
        out.append(
            "La personalización por aprendiz (H3) no se construye hasta que el ranking por tema "
            "llegue a 0,7."
        )
    return out


def report(key_csv: Path, judge_csvs: Sequence[Path], *, seed: int) -> str:
    with key_csv.open(encoding="utf-8", newline="") as handle:
        key = _key_candidates(csv.DictReader(handle))
    rows: list[dict[str, str]] = []
    for path in judge_csvs:
        with path.open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return render(analyse(key, read_judgments(rows), seed))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.video_experiment", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    exp = commands.add_parser("export", help="hojas ciegas para los jueces y la clave")
    exp.add_argument("--candidates", type=Path, required=True)
    exp.add_argument("--out", type=Path, required=True)
    exp.add_argument("--judges", type=int, default=2)
    exp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    rep = commands.add_parser("report", help="κ, P@3 y nDCG@3 de las cuatro ordenaciones")
    rep.add_argument("--key", type=Path, required=True)
    rep.add_argument("--judges", type=Path, nargs="+", required=True)
    rep.add_argument("--seed", type=int, default=DEFAULT_SEED)
    rep.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "export":
        print(export(args.candidates, args.out, judges=args.judges, seed=args.seed))  # noqa: T201
        return 0
    text = report(args.key, args.judges, seed=args.seed)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
