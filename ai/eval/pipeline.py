"""``eval.run_pipeline``: runs the content pipeline on a syllabus and saves the package.

Steps (the same code the worker runs): structure the syllabus -> enqueue and run the jobs of
``course.generate_content`` (index, explanation with faithfulness, quiz bank, final bank, videos)
-> badge text -> for each simulated learner: personal example, answers to a quiz attempt,
grading (rule and judge) and a remedial explanation for the topic where they failed.

Output directory: ``syllabus.json``, ``explanations/``, ``quiz_banks/``, ``final_bank.json``,
``videos/``, ``badge.json``, ``learners/<profile>/``, ``llm_log.jsonl`` and ``metrics.json``.
With the fakes (default) no key or network is needed; the real providers need ``AI_EVAL_LIVE=1``
(``eval/runtime.py``) and are never used in CI.
"""

from __future__ import annotations

import dataclasses
import json
import math
import statistics
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from app.adapters.budget import BudgetLimits, CallLogBudgetGuard
from app.adapters.memory import (
    InMemoryCallLogRepository,
    InMemoryCatalogReader,
    InMemoryGenerationCache,
    InMemoryJobRepository,
)
from app.adapters.memory_knowledge import InMemoryKnowledgeStore
from app.adapters.metadata_transcripts import MetadataTranscriptProvider
from app.adapters.prompt_files import FilePromptStore
from app.application.content.context import Handler, TaskContext, TaskResult
from app.application.content.course_generation import GenerateContentInput
from app.application.content.privacy import pseudonymize_profile
from app.application.content.registry import ContentDeps, build_content_handlers
from app.application.embeddings.sources import DirectorySourceReader
from app.application.grading.rule import grade_multiple_choice
from app.application.llm_runner import CallContext, EmbeddingRunner, LlmRunner, ModelConfig
from app.application.pricing import PriceTable
from app.core.config import AI_ROOT, REPO_ROOT
from app.domain.contracts.assessment import (
    AssessmentItem,
    AssessmentItemBank,
    SimulatedAnswersLLM,
    answer_from_llm,
)
from app.domain.contracts.content import TopicExplanation
from app.domain.contracts.grading import AnswerGrading
from app.domain.contracts.syllabus import Syllabus, SyllabusLLM, syllabus_from_llm
from app.domain.contracts.validation import check_simulated_answers, check_syllabus
from app.domain.contracts.video import VideoResource
from app.domain.errors import TaskError
from app.ports.call_logs import LlmCallLog
from app.ports.catalog import OutcomeRecord, TopicRecord
from app.ports.jobs import Job, JobError, JobRefs
from eval.consistency import Package, verify_consistency
from eval.runtime import EvalRuntime

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEFAULT_SYLLABUS = FIXTURES / "syllabus.md"
DEFAULT_SOURCES = FIXTURES / "sources"
DEFAULT_PROFILES = [
    "Analista de datos en logística; uso Excel y SQL y quiero aprender modelos predictivos.",
    "Estudiante de administración sin experiencia en programación; me interesa la analítica.",
]
COURSE_ID = 1
LEARNING_PATH_ID = 1
LEASE_SECONDS = 900
ATTEMPT_MC = 4
ATTEMPT_SA = 1
DONT_KNOW_RULE = "Esta es una práctica del quiz: no uses «No lo sé» (dont_know = false)."


@dataclass(frozen=True)
class PipelineOptions:
    syllabus_text: str
    out_dir: Path
    simulated_profiles: list[str] = field(default_factory=lambda: list(DEFAULT_PROFILES))
    sources_dir: Path = DEFAULT_SOURCES
    syllabus_document_id: int = 1
    quiz_items_per_topic: int = 23
    final_versions: int = 2


@dataclass(frozen=True)
class PipelineReport:
    output_dir: Path
    metrics: dict[str, Any]
    issues: list[str]

    def as_result(self) -> dict[str, Any]:
        """The ``result`` of the job type ``eval.run_pipeline``."""
        return {"output_dir": str(self.output_dir), "metrics": self.metrics}


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(q * len(ordered)) - 1)
    return float(ordered[rank])


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, UUID, Decimal)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def log_metrics(rows: list[LlmCallLog]) -> dict[str, Any]:
    """Invalid JSON, latency and cost, as AD2 reads them from ``llm_call_logs``."""
    calls = [r for r in rows if not r.from_cache and r.status != "budget_exceeded"]
    latencies = [r.latency_ms for r in calls]
    by_task: dict[str, list[int]] = {}
    for r in calls:
        by_task.setdefault(r.task, []).append(r.latency_ms)
    invalid = sum(r.status == "invalid_output" for r in calls)
    json_invalid = sum(r.json_valid is False for r in calls)
    cost = sum((r.cost_usd or Decimal(0) for r in rows), Decimal(0))
    return {
        "llm_calls": len(calls),
        "cache_hits": sum(r.from_cache for r in rows),
        "errors": sum(r.status == "error" for r in rows),
        "invalid_output": invalid,
        "invalid_json": json_invalid,
        "invalid_json_rate": round(json_invalid / len(calls), 4) if calls else 0.0,
        "invalid_output_rate": round(invalid / len(calls), 4) if calls else 0.0,
        "latency_ms_p50": percentile(latencies, 0.5),
        "latency_ms_p95": percentile(latencies, 0.95),
        "latency_ms_p95_by_task": {t: percentile(v, 0.95) for t, v in sorted(by_task.items())},
        "input_tokens": sum(r.input_tokens for r in rows),
        "output_tokens": sum(r.output_tokens for r in rows),
        "cost_usd": str(cost),
        "calls_by_prompt": dict(Counter(r.prompt_id for r in calls if r.prompt_id)),
    }


class EvalWorld:
    """State of one run: dependencies, handlers and the package being built."""

    def __init__(self, options: PipelineOptions, runtime: EvalRuntime) -> None:
        self.options = options
        self.runtime = runtime
        self.logs = InMemoryCallLogRepository()
        self.jobs = InMemoryJobRepository()
        self.catalog = InMemoryCatalogReader()
        prompts = FilePromptStore(REPO_ROOT / "prompts")
        if problems := prompts.verify():
            raise RuntimeError(f"prompt store problems: {problems}")
        prices = PriceTable.load(AI_ROOT / "config" / "prices.yaml")
        budget = CallLogBudgetGuard(BudgetLimits(), self.logs, "UTC")
        models = ModelConfig(
            provider_is_real=runtime.live,
            default_model=runtime.default_model,
            small_model=runtime.small_model,
        )
        self.runner = LlmRunner(
            provider=runtime.provider,
            prompts=prompts,
            models=models,
            prices=prices,
            cache=InMemoryGenerationCache(),
            call_logs=self.logs,
            budget=budget,
            clock=self.now,
            provider_backoff_seconds=0.0 if not runtime.live else 2.0,
        )
        self.embeddings = EmbeddingRunner(
            provider=runtime.embedder,
            prices=prices,
            provider_is_real=runtime.live,
            call_logs=self.logs,
            budget=budget,
            clock=self.now,
        )
        self.deps = ContentDeps(
            runner=self.runner,
            embeddings=self.embeddings,
            catalog=self.catalog,
            knowledge=InMemoryKnowledgeStore(),
            sources=DirectorySourceReader(options.sources_dir, default_course=True),
            jobs=self.jobs,
            transcripts=MetadataTranscriptProvider(),
            clock=self.now,
            video_search=runtime.video_search,
        )
        self.handlers: dict[str, Handler] = build_content_handlers(self.deps)
        self.package = Package(
            topics=[],
            quiz_items_per_topic=options.quiz_items_per_topic,
            final_versions=options.final_versions,
        )

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)

    # ---------- syllabus ----------

    async def structure_syllabus(self) -> Syllabus:
        ctx = CallContext(task="syllabus.structure")
        llm, meta = await self.runner.run(
            "syllabus_structuring",
            {"syllabus": self.options.syllabus_text},
            SyllabusLLM,
            ctx,
            check=check_syllabus,
        )
        syllabus = syllabus_from_llm(llm, meta)
        topics = [
            TopicRecord(
                id=str(n),
                course_id=COURSE_ID,
                name=t.name,
                description=t.description,
                subtopics=t.subtopics,
                position=n,
                outcomes=[
                    OutcomeRecord(id=o.id, statement=o.statement, bloom_level=o.bloom_level)
                    for o in t.learning_outcomes
                ],
            )
            for n, t in enumerate(syllabus.topics, start=1)
        ]
        self.catalog.topic_list = topics
        self.package.topics = topics
        return syllabus

    # ---------- worker loop ----------

    async def call(self, job_type: str, payload: dict[str, Any], refs: JobRefs) -> TaskResult:
        return await self.handlers[job_type](
            payload, TaskContext(idempotency_key=f"eval:{job_type}", refs=refs, requested_by="eval")
        )

    async def drain_jobs(self) -> dict[UUID, TaskResult]:
        """Run every queued job like the worker does; failures are recorded, not raised."""
        results: dict[UUID, TaskResult] = {}
        while (job := await self.jobs.claim_next(self.now(), LEASE_SECONDS)) is not None:
            ctx = TaskContext(
                job_id=job.id,
                idempotency_key=job.idempotency_key,
                refs=job.refs,
                requested_by=job.requested_by,
            )
            try:
                result = await self.handlers[job.job_type](job.input, ctx)
            except TaskError as exc:
                await self.jobs.fail(
                    job.id, JobError(exc.code, exc.message, exc.retryable), self.now()
                )
                self.package.failed_jobs.append(f"{job.job_type} {job.input}: {exc.code}")
            else:
                await self.jobs.succeed(job.id, result.result, result.contract, self.now())
                results[job.id] = result
                self._collect(job, result)
        return results

    def _collect(self, job: Job, result: TaskResult) -> None:
        topic_id = str(job.input.get("topic_id", ""))
        match job.job_type:
            case "content.explain_topic":
                self.package.explanations[topic_id] = TopicExplanation.model_validate(result.result)
            case "items.generate_quiz_bank":
                self.package.quiz_banks[topic_id] = AssessmentItemBank.model_validate(result.result)
            case "items.generate_final_bank":
                self.package.final_bank = AssessmentItemBank.model_validate(result.result)
            case "video.collect_candidates":
                self.package.videos[topic_id] = VideoResource.model_validate(result.result)

    # ---------- learners ----------

    async def simulate_learner(self, name: str, profile: str, out: Path) -> dict[str, Any]:
        topic = self.package.topics[0]
        bank = self.package.quiz_banks[topic.id]
        usable = [i for i in bank.items if i.id not in set(bank.discarded_item_ids)]
        attempt = [i for i in usable if i.item_type == "multiple_choice"][:ATTEMPT_MC]
        attempt += [i for i in usable if i.item_type == "short_answer"][:ATTEMPT_SA]
        refs = JobRefs(course_id=COURSE_ID, topic_id=int(topic.id), enrollment_id=len(name))
        scope_ctx = TaskContext(refs=refs, requested_by="eval")
        safe_profile = pseudonymize_profile(profile)

        example = await self.call(
            "content.personal_example", {"topic_id": topic.id, "profile_text": profile}, refs
        )
        answers = await self._simulated_answers(safe_profile, attempt, scope_ctx)
        gradings = await self._grade(attempt, answers, scope_ctx)
        self.package.gradings += gradings
        failed = [
            {"stem": item.stem, "learner_answer": answers.get(item.id, "")}
            for item, g in zip(attempt, gradings, strict=True)
            if not g.is_correct
        ]
        remedial = None
        if failed:
            level = round(100 * sum(g.is_correct for g in gradings) / len(gradings), 1)
            remedial = await self.call(
                "content.remedial",
                {
                    "topic_id": topic.id,
                    "level": level,
                    "profile_text": profile,
                    "failed_items": failed,
                },
                refs,
            )
        _write_json(out / "personal_example.json", example.result)
        _write_json(out / "gradings.json", [g.model_dump(mode="json") for g in gradings])
        if remedial is not None:
            _write_json(out / "remedial.json", remedial.result)
        return {
            "profile": name,
            "attempt_items": len(attempt),
            "correct": sum(g.is_correct for g in gradings),
            "remedial": remedial is not None,
        }

    async def _simulated_answers(
        self, profile: str, attempt: list[AssessmentItem], ctx: TaskContext
    ) -> dict[str, str]:
        payload = [
            {"id": i.id, "item_type": i.item_type, "stem": i.stem, "options": i.options}
            for i in attempt
        ]
        types = {i.id: i.item_type for i in attempt}
        llm, _ = await self.runner.run(
            "simulated_learner",
            {
                "profile": profile,
                "context": "",
                "items": json.dumps(payload, ensure_ascii=False),
                "dont_know_rule": DONT_KNOW_RULE,
            },
            SimulatedAnswersLLM,
            ctx.call("eval.simulate_learner"),
            check=lambda out: check_simulated_answers(out, types, allow_dont_know=False),
            use_cache=False,
        )
        learner_answers = [answer_from_llm(a) for a in llm.answers]
        return {
            a.item_id: str(a.selected_option)
            if a.selected_option is not None
            else a.text_answer or ""
            for a in learner_answers
        }

    async def _grade(
        self, attempt: list[AssessmentItem], answers: Mapping[str, str], ctx: TaskContext
    ) -> list[AnswerGrading]:
        gradings: list[AnswerGrading] = []
        for item in attempt:
            given = answers.get(item.id, "")
            if item.item_type == "multiple_choice":
                selected = int(given) if given.isdigit() else None
                gradings.append(grade_multiple_choice(item.id, item.correct_option or 0, selected))
                continue
            result = await self.call(
                "grading.short_answer",
                {
                    "item_id": item.id,
                    "stem": item.stem,
                    "model_answer": item.model_answer,
                    "rubric": [c.model_dump() for c in item.rubric],
                    "answer_text": given,
                    "min_criteria_ratio": 2 / 3,
                },
                ctx.refs,
            )
            gradings.append(AnswerGrading.model_validate(result.result))
        return gradings


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.casefold()).strip("_")[:40] or "x"


async def run_pipeline(
    options: PipelineOptions,
    runtime: EvalRuntime,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineReport:
    """Run the pipeline and write the package to ``options.out_dir``."""
    say = on_progress or (lambda _msg: None)
    run = EvalWorld(options, runtime)
    out = options.out_dir
    out.mkdir(parents=True, exist_ok=True)

    say("syllabus")
    syllabus = await run.structure_syllabus()
    _write_json(out / "syllabus.json", syllabus.model_dump(mode="json"))

    say("course.generate_content")
    started = await run.call(
        "course.generate_content",
        GenerateContentInput(
            course_id=COURSE_ID,
            learning_path_id=LEARNING_PATH_ID,
            quiz_items_per_topic=options.quiz_items_per_topic,
            final_versions=options.final_versions,
        ).model_dump(),
        JobRefs(course_id=COURSE_ID),
    )
    results = await run.drain_jobs()
    _write_json(out / "jobs.json", started.result)

    for topic in run.package.topics:
        if explanation := run.package.explanations.get(topic.id):
            _write_json(
                out / "explanations" / f"{topic.id}.json", explanation.model_dump(mode="json")
            )
        if bank := run.package.quiz_banks.get(topic.id):
            _write_json(out / "quiz_banks" / f"{topic.id}.json", bank.model_dump(mode="json"))
        if video := run.package.videos.get(topic.id):
            _write_json(out / "videos" / f"{topic.id}.json", video.model_dump(mode="json"))
    if run.package.final_bank is not None:
        _write_json(out / "final_bank.json", run.package.final_bank.model_dump(mode="json"))

    say("badge")
    badge = await run.call(
        "badge.compose_text",
        {
            "course_name": syllabus.course_name,
            "objective_statement": syllabus.default_objective,
            "topic_names": [t.name for t in run.package.topics],
            "final_pass_threshold": 80,
        },
        JobRefs(course_id=COURSE_ID),
    )
    _write_json(out / "badge.json", badge.result)

    learners: list[dict[str, Any]] = []
    if run.package.quiz_banks.get(run.package.topics[0].id) is not None:
        for number, profile in enumerate(options.simulated_profiles, start=1):
            say(f"learner {number}")
            name = f"{number:02d}_{_slug(profile)}"
            learners.append(await run.simulate_learner(name, profile, out / "learners" / name))

    rows = run.logs.rows
    (out / "llm_log.jsonl").write_text(
        "\n".join(
            json.dumps(dataclasses.asdict(r), ensure_ascii=False, default=_json_default)
            for r in rows
        )
        + "\n",
        encoding="utf-8",
    )
    issues = verify_consistency(run.package)
    explanations = list(run.package.explanations.values())
    faithfulness = [e.faithfulness for e in explanations if e.faithfulness is not None]
    metrics: dict[str, Any] = {
        "live": runtime.live,
        "models": {"default": runtime.default_model, "small": runtime.small_model},
        "embedding_model": runtime.embedder.model,
        "topics": len(run.package.topics),
        "jobs": dict(
            Counter(
                j.status
                for j in (
                    await run.jobs.list(
                        status=None, job_type=None, course_id=None, limit=1000, offset=0
                    )
                ).items
            )
        ),
        "jobs_succeeded": len(results),
        "faithfulness_mean": round(statistics.fmean(faithfulness), 3) if faithfulness else None,
        "quiz_items": {t: len(b.items) for t, b in run.package.quiz_banks.items()},
        "quiz_discarded": {t: len(b.discarded_item_ids) for t, b in run.package.quiz_banks.items()},
        "final_items": len(run.package.final_bank.items) if run.package.final_bank else 0,
        "videos_selected": sum(
            v.selected_video_id is not None for v in run.package.videos.values()
        ),
        "learners": learners,
        "llm": log_metrics(rows),
        "consistency_issues": issues,
    }
    _write_json(out / "metrics.json", metrics)
    return PipelineReport(output_dir=out, metrics=metrics, issues=issues)
