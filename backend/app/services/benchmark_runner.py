"""Batched, resumable execution of the STEP 9 MSEMAX A/B benchmark.

Design constraints that shaped this module
------------------------------------------
* ~485 provider calls cannot fit in one Vercel invocation, so the work is split
  into 40 batches of one ``(document, seed)`` pair each. Measured worst case for
  a single pair is 16 provider calls.
* Serverless filesystems are ephemeral, so progress lives in Postgres
  (``app.models.benchmark``), which the project already uses.
* The methodology must not change: same corpus, seeds, count, blueprints,
  validators and ``inspect_quiz`` scanner as ``backend/scripts/msemax_ab.py``.
  Both arms run inside one batch against the identical document and seed, so
  the control and the experiment cannot drift apart.

What this module deliberately does NOT do
-----------------------------------------
* It never reads, logs, stores or returns provider credentials. AIService reads
  them from the environment at call time; nothing here can observe them.
* It never fabricates a measurement. A batch that cannot reach a provider is
  recorded as failed with its error category, and the final report refuses to
  aggregate until every batch has genuinely completed.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.benchmark import (
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PENDING,
    BATCH_RUNNING,
    BenchmarkBatch,
    BenchmarkPhrasing,
    BenchmarkRun,
)
from app.services.ai_documents import AIDocumentSource, _extract_pdf
from app.services.quiz_blueprints import target_tier
from app.services.quiz_msemax import (
    MsemaxConfigurationError,
    MsemaxRejection,
    MsemaxStats,
    generate_candidate,
)
from app.services.quiz_pipeline import generate_quiz

logger = logging.getLogger(__name__)

# Repository root: backend/app/services/ -> up three.
ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = ROOT / "public" / "demo-files"
CORPUS_DIR = ROOT / "backend" / "tests" / "fixtures" / "domain_corpus"

#: STEP 9 methodology. These are the published defaults and must not be changed
#: to make a run cheaper or faster -- doing so would silently produce a
#: different benchmark under the same name.
DEFAULT_SEEDS: tuple[int, ...] = (1, 3, 5, 7, 11)
DEFAULT_COUNT = 8
ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]

#: Wall-clock budget for provider work inside ONE request, in seconds.
#: vercel.json uses the legacy ``builds`` property, which cannot carry a
#: ``functions.maxDuration`` override, so the platform default applies (10s on
#: Hobby, 15s on Pro). A single provider call may take up to
#: AI_TIMEOUT_SECONDS (25s by default) on its own, so a request stops starting
#: NEW calls once this budget is spent and reports partial progress instead.
#: The remaining blueprints are phrased by the next request.
PHRASING_BUDGET_SECONDS = float(os.getenv("BENCHMARK_PHRASING_BUDGET", "6"))

#: Hard cap on provider calls per request, independent of the clock. Keeps a
#: burst of fast responses from still overrunning the invocation.
MAX_CALLS_PER_REQUEST = int(os.getenv("BENCHMARK_MAX_CALLS_PER_REQUEST", "3"))

#: Retries for a *transient* provider failure (429 quota, timeout, connection,
#: 5xx) on a single blueprint. Free-tier Gemini keys rate-limit aggressively,
#: and without this a burst of 429s is recorded as if MSEMAX had produced bad
#: questions. Bounded so a rate-limited run degrades into slow progress rather
#: than an unbounded stall.
PHRASING_RETRY_ATTEMPTS = int(os.getenv("BENCHMARK_RETRY_ATTEMPTS", "3"))

#: Base seconds for exponential backoff: sleep = base * 2**(attempt-1), capped.
#: A provider-supplied Retry-After always wins over this schedule.
PHRASING_RETRY_BASE_SECONDS = float(os.getenv("BENCHMARK_RETRY_BASE_SECONDS", "1.0"))

#: Never sleep longer than this in one wait. The invocation has a hard ceiling,
#: so a very long cooldown is better served by ending the request and letting
#: the next one resume than by blocking until the platform kills us.
PHRASING_RETRY_MAX_SLEEP_SECONDS = float(
    os.getenv("BENCHMARK_RETRY_MAX_SLEEP", "8.0")
)


def retry_delay_seconds(
    attempt: int,
    retry_after: float | None = None,
    *,
    base: float = PHRASING_RETRY_BASE_SECONDS,
    cap: float = PHRASING_RETRY_MAX_SLEEP_SECONDS,
) -> float:
    """Backoff before retry number ``attempt`` (1-based).

    Honours a server-supplied ``Retry-After`` when present, otherwise uses
    exponential backoff. Always clamped to ``cap`` so one wait cannot overrun
    the serverless invocation.
    """
    if retry_after is not None and retry_after >= 0:
        return min(retry_after, cap)
    return min(base * (2 ** max(0, attempt - 1)), cap)


#: How many separate requests may defer a unit for transient provider reasons
#: before the failure is recorded instead. Without a ceiling, a persistently
#: rate-limited key would defer forever and the run could never complete.
#: Recorded failures stay classified as provider errors, so they still never
#: count as MSEMAX quality rejections.
MAX_TRANSIENT_DEFERRALS = int(os.getenv("BENCHMARK_MAX_DEFERRALS", "6"))

#: Marker prefix for a phrasing that failed for an infrastructure reason
#: rather than a quality one. Rows carrying it are NOT counted as MSEMAX
#: rejections and are retried by a later request instead of being final.
TRANSIENT_PREFIX = "transient:"


def is_transient_reason(reason: str | None) -> bool:
    """True when a stored rejection reason represents a provider/quota failure.

    These must never be read as "MSEMAX wrote a bad question": the model was
    never given the chance to answer.
    """
    return bool(reason) and reason.startswith(TRANSIENT_PREFIX)


def classify_generation_failure(exc: BaseException) -> tuple[bool, float | None]:
    """(is_transient, retry_after) for an exception raised while phrasing.

    Unwraps ``AIUnavailableError``, which aggregates one failure per provider:
    the attempt is transient only when *every* provider failed transiently,
    since a deterministic defect (bad schema, retired model) will simply repeat.
    """
    from app.services.ai_providers import ProviderError
    from app.services.ai_service import AIUnavailableError
    from app.services.ai_providers import ErrorCategory

    if isinstance(exc, AIUnavailableError):
        failures = exc.failures
        if not failures:
            return False, None
        transient_categories = {
            ErrorCategory.QUOTA_RATE_LIMIT.value,
            ErrorCategory.TIMEOUT.value,
            ErrorCategory.CONNECTION.value,
            ErrorCategory.PROVIDER_UNAVAILABLE.value,
        }
        all_transient = all(f.category in transient_categories for f in failures)
        waits = [f.retry_after for f in failures if getattr(f, "retry_after", None)]
        return all_transient, (max(waits) if waits else None)
    if isinstance(exc, ProviderError):
        return exc.is_transient, exc.retry_after
    if isinstance(exc, TimeoutError):
        return True, None
    return False, None


def phrase_with_retry(
    blueprint: Any,
    *,
    backend: Any,
    attempts: int = PHRASING_RETRY_ATTEMPTS,
    sleep: Any = time.sleep,
) -> tuple[dict | None, Any, bool]:
    """Phrase one blueprint, retrying transient provider failures.

    Returns ``(candidate, rejection, transient)``. When ``transient`` is True
    every attempt failed for an infrastructure reason (429/timeout/5xx) and the
    result must NOT be treated as a quality rejection -- the model never got to
    answer. Quality rejections return immediately and are never retried, since
    the deterministic pipeline would produce the identical verdict again.
    """
    last_rejection: Any = None
    for attempt in range(1, max(1, attempts) + 1):
        candidate, rejection = generate_candidate(blueprint, backend=backend)
        if candidate is not None:
            return candidate, None, False
        last_rejection = rejection

        reason = getattr(rejection, "reason", "") or ""
        if not reason.startswith("provider error"):
            # A genuine MSEMAX quality rejection: deterministic, do not retry.
            return None, rejection, False

        transient, retry_after = _transient_from_reason(reason)
        if not transient or attempt >= max(1, attempts):
            return None, rejection, transient

        delay = retry_delay_seconds(attempt, retry_after)
        logger.info(
            "benchmark phrasing retry %s/%s for blueprint %s after %.1fs (%s)",
            attempt,
            attempts,
            getattr(blueprint, "id", "?"),
            delay,
            reason[:120],
        )
        sleep(delay)
    return None, last_rejection, True


def _transient_from_reason(reason: str) -> tuple[bool, float | None]:
    """Decide transience from a rendered 'provider error [...]' reason string.

    ``generate_candidate`` already converts the exception into a sanitized,
    category-bearing string, so transience is derived from those categories
    rather than from re-raising.
    """
    from app.services.ai_providers import ErrorCategory

    transient_names = {
        ErrorCategory.QUOTA_RATE_LIMIT.value,
        ErrorCategory.TIMEOUT.value,
        ErrorCategory.CONNECTION.value,
        ErrorCategory.PROVIDER_UNAVAILABLE.value,
    }
    found = {name for name in transient_names if name in reason}
    if not found:
        return False, None
    # Transient only when NO deterministic category also appears: a mixed
    # result (e.g. gemini model_not_found + groq quota) will not self-heal.
    deterministic = {
        ErrorCategory.AUTHENTICATION.value,
        ErrorCategory.INVALID_REQUEST.value,
        ErrorCategory.MODEL_NOT_FOUND.value,
        ErrorCategory.RESPONSE_SCHEMA.value,
        ErrorCategory.CONTENT_BLOCKED.value,
        ErrorCategory.CONFIGURATION.value,
    }
    if any(name in reason for name in deterministic):
        return False, None
    return True, None


class BenchmarkError(RuntimeError):
    """A benchmark could not be created or advanced."""


class _NoQuizProvider:
    """Blocks provider *quiz authoring* so both arms share one planner.

    The question STEP 9 answers is "does MSEMAX phrase blueprints better than
    the deterministic writer?". Letting the provider also author whole quizzes
    would confound that with a different planning path, so quiz-level
    completion is refused in both arms. MSEMAX is reached through its own seam,
    which is the only difference between the two arms.
    """

    def complete_structured(self, **kwargs: Any) -> Any:
        from app.services.ai_service import AIServiceError

        raise AIServiceError("quiz authoring disabled for A/B comparison")


class _MsemaxOnlyService:
    """Routes MSEMAX phrasing calls to the real provider, nothing else.

    Quiz authoring still fails (keeping the planner identical across arms)
    while MSEMAX's per-blueprint calls reach the genuine AIService. This is what
    makes arm B a real provider measurement rather than a simulation.
    """

    def __init__(self, service: Any) -> None:
        self._service = service

    def complete_structured(self, **kwargs: Any) -> Any:
        from app.services.quiz_msemax import MsemaxQuestion

        if kwargs.get("response_model") is MsemaxQuestion:
            return self._service.complete_structured(**kwargs)
        from app.services.ai_service import AIServiceError

        raise AIServiceError("quiz authoring disabled for A/B comparison")


def corpus_documents() -> list[Path]:
    """The 8-domain corpus, in a stable order."""
    return sorted(DEMO_DIR.glob("*.pdf")) + sorted(CORPUS_DIR.glob("*.txt"))


def load_source(doc: Path) -> AIDocumentSource:
    """Identical loading for both arms (mirrors ``msemax_ab.load_source``)."""
    if doc.suffix.lower() == ".pdf":
        return _extract_pdf(
            doc.read_bytes(),
            file_id=doc.stem,
            title=doc.stem,
            max_characters=200_000,
            allowed_pages=None,
        )
    paragraphs = [
        block.strip()
        for block in doc.read_text(encoding="utf-8").split("\n\n")
        if block.strip()
    ]
    pages = [paragraphs[i : i + 2] for i in range(0, len(paragraphs), 2)]
    text = "\n\n".join(
        f"[Page {n}]\n" + "\n\n".join(block) for n, block in enumerate(pages, start=1)
    )
    return AIDocumentSource(
        file_id=doc.stem,
        title=doc.stem.replace("-", " ").title(),
        text=text,
        page_count=len(pages),
    )


def _scanner():
    """The production ``inspect_quiz``.

    Loaded from the same script the offline harness uses so there is exactly one
    definition of "defect"; a second copy could drift and make the two arms
    incomparable.
    """
    import importlib.util

    path = ROOT / "backend" / "scripts" / "adversarial_scan.py"
    spec = importlib.util.spec_from_file_location("_adv_scan", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise BenchmarkError("adversarial_scan.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect_quiz


def _tier_counts(result: Any) -> tuple[int, int]:
    by_id = {blueprint.id: blueprint for blueprint in result.blueprints}
    tier1 = tier2 = 0
    for trace in result.provenance:
        blueprint = by_id.get(getattr(trace, "blueprint_id", ""))
        if blueprint is None:
            continue
        tier = target_tier(blueprint)
        if tier == 1:
            tier1 += 1
        elif tier == 2:
            tier2 += 1
    return tier1, tier2


def _measure(result: Any, scanner: Any, elapsed: float) -> dict[str, Any]:
    """Reduce one generated quiz to the STEP 9 metric set."""
    findings = scanner(result)
    defect_kinds: dict[str, int] = {}
    defects = warnings = 0
    for severity, _where, message in findings:
        key = message.split(":")[0]
        if severity == "DEFECT":
            defects += 1
            defect_kinds[key] = defect_kinds.get(key, 0) + 1
        else:
            warnings += 1

    rejections: dict[str, int] = {}
    for note in result.rejections:
        rejections[note.stage] = rejections.get(note.stage, 0) + 1

    tier1, _tier2 = _tier_counts(result)
    concepts = (
        len(result.understanding.important_concepts())
        if result.understanding is not None
        else 0
    )
    return {
        "questions": len(result.questions),
        "concepts": concepts,
        "tier1": tier1,
        "defects": defects,
        "warnings": warnings,
        # A "written candidate" either became a question or carries a rejection
        # note; comparing the two detects a candidate vanishing unrecorded.
        "candidates": len(result.questions) + len(result.rejections),
        "rejections": rejections,
        "defect_kinds": defect_kinds,
        "latency": round(elapsed, 3),
    }


def create_run(
    db: Session,
    *,
    settings: Any,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    count: int = DEFAULT_COUNT,
) -> BenchmarkRun:
    """Create a run and its full batch matrix up front.

    Materialising every batch immediately makes progress explicit and lets the
    unique constraint guarantee that no ``(document, seed)`` pair is ever
    measured twice, regardless of retries or concurrent callers.
    """
    documents = corpus_documents()
    if not documents:
        raise BenchmarkError("benchmark corpus is empty")

    run = BenchmarkRun(
        seeds=" ".join(str(seed) for seed in seeds),
        count=count,
        documents=[doc.name for doc in documents],
        provider_primary=settings.ai_provider,
        provider_fallback=settings.ai_fallback_provider,
        gemini_model=settings.gemini_model,
        groq_model=settings.groq_model,
        total_batches=len(documents) * len(seeds),
        status="running",
    )
    db.add(run)
    db.flush()

    for doc in documents:
        for seed in seeds:
            db.add(
                BenchmarkBatch(
                    run_id=run.id, document=doc.name, seed=seed, status=BATCH_PENDING
                )
            )
    db.commit()
    db.refresh(run)
    return run


def _claim_next_batch(db: Session, run: BenchmarkRun) -> BenchmarkBatch | None:
    """Take the next unfinished batch, locking it against concurrent callers.

    ``SELECT ... FOR UPDATE SKIP LOCKED`` means two overlapping requests pick up
    different batches instead of racing on the same one. SQLite (used by tests)
    ignores the locking clause, which is harmless there because the tests are
    single-threaded.
    """
    query = (
        db.query(BenchmarkBatch)
        .filter(
            BenchmarkBatch.run_id == run.id,
            BenchmarkBatch.status.in_([BATCH_PENDING, BATCH_FAILED]),
        )
        .order_by(BenchmarkBatch.document, BenchmarkBatch.seed)
    )
    try:
        batch = query.with_for_update(skip_locked=True).first()
    except Exception:  # dialect without row locking (SQLite in tests)
        batch = query.first()
    if batch is None:
        return None
    batch.status = BATCH_RUNNING
    batch.attempts += 1
    db.commit()
    db.refresh(batch)
    return batch


def _blueprints_for(source: Any, run: BenchmarkRun, seed: int) -> list[Any]:
    """The deterministic blueprints MSEMAX would phrase for this unit.

    Produced by running the deterministic pipeline with MSEMAX off, so the
    planner -- and therefore the blueprint set -- is identical in both arms and
    across every request that touches this unit.
    """
    result = generate_quiz(
        _NoQuizProvider(),
        source,
        count=run.count,
        question_types=ALL_TYPES,
        difficulty="mixed",
        kind="practice",
        language="en",
        seed=seed,
        previous_questions=[],
        system_prompt="Benchmark run.",
        msemax_enabled=False,
    )
    return [bp for bp in result.blueprints if bp.id.startswith("det-bp-")]


def _cached_phrasings(db: Session, batch_id: str) -> dict[str, BenchmarkPhrasing]:
    rows = (
        db.query(BenchmarkPhrasing).filter(BenchmarkPhrasing.batch_id == batch_id).all()
    )
    return {row.blueprint_id: row for row in rows}


def phrase_step(
    db: Session,
    run: BenchmarkRun,
    batch: BenchmarkBatch,
    *,
    service: Any,
    budget_seconds: float = PHRASING_BUDGET_SECONDS,
    max_calls: int = MAX_CALLS_PER_REQUEST,
    sleep: Any = time.sleep,
) -> bool:
    """Phrase a few of this unit's blueprints; return True when the unit is done.

    Bounded by BOTH a wall-clock budget and a call cap so one request can never
    overrun the serverless limit. Each phrasing is committed immediately, so an
    invocation killed mid-flight loses at most the call in progress -- the rest
    is already durable and the next request resumes from there.
    """
    document = next(
        (doc for doc in corpus_documents() if doc.name == batch.document), None
    )
    if document is None:
        raise BenchmarkError(f"corpus document missing: {batch.document}")

    source = load_source(document)
    blueprints = _blueprints_for(source, run, batch.seed)
    if batch.blueprint_count != len(blueprints):
        batch.blueprint_count = len(blueprints)
        db.commit()

    done = _cached_phrasings(db, batch.id)
    pending = [bp for bp in blueprints if bp.id not in done]
    if not pending:
        return True

    # Fail fast and loudly if the deployment is not configured for MSEMAX,
    # rather than silently recording deterministic output as a model result.
    from app.services.quiz_msemax import resolve_backend
    from app.core.config import get_settings

    backend = resolve_backend(get_settings(), service)

    started = time.perf_counter()
    calls = 0
    transient_deferrals = 0
    for blueprint in pending:
        if calls >= max_calls or (time.perf_counter() - started) >= budget_seconds:
            break
        call_started = time.perf_counter()
        candidate, rejection, transient = phrase_with_retry(
            blueprint, backend=backend, sleep=sleep
        )
        elapsed = time.perf_counter() - call_started
        calls += 1

        if transient and batch.attempts < MAX_TRANSIENT_DEFERRALS:
            # Quota/timeout/outage: the model never got to answer, so this is
            # NOT a quality result. Storing it would freeze the hole in place,
            # because UniqueConstraint(batch_id, blueprint_id) makes the row
            # final. Leave the blueprint unphrased so a later request retries
            # it, and stop early rather than burning the budget on more 429s.
            logger.warning(
                "benchmark phrasing deferred for blueprint %s (attempt %s/%s) (%s)",
                blueprint.id,
                batch.attempts,
                MAX_TRANSIENT_DEFERRALS,
                (getattr(rejection, "reason", "") or "")[:160],
            )
            transient_deferrals += 1
            break

        if transient:
            # The provider has stayed unhealthy across many separate requests.
            # Deferring forever would leave the run permanently incomplete, so
            # record the failure and let the unit finish. It is still tagged
            # transient, which keeps it OUT of the quality metrics and flips
            # measurement_reliable to false rather than pretending MSEMAX lost.
            logger.warning(
                "benchmark phrasing giving up for blueprint %s after %s attempts (%s)",
                blueprint.id,
                batch.attempts,
                (getattr(rejection, "reason", "") or "")[:160],
            )

        db.add(
            BenchmarkPhrasing(
                batch_id=batch.id,
                blueprint_id=blueprint.id,
                candidate=candidate,
                rejection_reason=rejection.reason if rejection else None,
                concept_id=blueprint.concept_id,
                cognitive_skill=blueprint.cognitive_skill,
                latency=round(elapsed, 3),
            )
        )
        # Commit per call: durability is what makes the unit resumable.
        db.commit()

    batch.phrased_count = len(_cached_phrasings(db, batch.id))
    db.commit()
    return batch.phrased_count >= len(blueprints)


def measure_batch(
    db: Session, run: BenchmarkRun, batch: BenchmarkBatch
) -> BenchmarkBatch:
    """Score both arms for a fully phrased unit, making no provider call.

    Arm A is the deterministic control. Arm B replays the cached MSEMAX prose
    through the identical pipeline, so both arms share the same documents,
    seeds, blueprints, validators and scanner -- only the wording differs.
    """
    document = next(
        (doc for doc in corpus_documents() if doc.name == batch.document), None
    )
    if document is None:
        raise BenchmarkError(f"corpus document missing: {batch.document}")

    scanner = _scanner()
    source = load_source(document)
    common = {
        "count": run.count,
        "question_types": ALL_TYPES,
        "difficulty": "mixed",
        "kind": "practice",
        "language": "en",
        "seed": batch.seed,
        "previous_questions": [],
        "system_prompt": "Benchmark run.",
    }

    started = time.perf_counter()
    baseline = generate_quiz(_NoQuizProvider(), source, **common, msemax_enabled=False)
    baseline_metrics = _measure(baseline, scanner, time.perf_counter() - started)

    rows = _cached_phrasings(db, batch.id)
    phrasings = {
        blueprint_id: row.candidate
        for blueprint_id, row in rows.items()
        if row.candidate
    }
    rejections = [
        MsemaxRejection(
            blueprint_id=blueprint_id,
            concept_id=row.concept_id,
            cognitive_skill=row.cognitive_skill,
            reason=row.rejection_reason or "",
        )
        for blueprint_id, row in rows.items()
        if not row.candidate
    ]
    stats = MsemaxStats()
    stats.requested = len(rows)
    stats.generated = len(phrasings)
    for rejection in rejections:
        if rejection.reason.startswith("provider error"):
            # Infrastructure failure, not a judgement on the generated text.
            # Counted separately so it can be excluded from quality metrics.
            stats.provider_errors += 1
        stats.note_rejection(rejection.reason)

    started = time.perf_counter()
    experimental = generate_quiz(
        _NoQuizProvider(),
        source,
        **common,
        msemax_enabled=True,
        msemax_phrasings=phrasings,
        msemax_replayed_rejections=rejections,
        msemax_replayed_stats=stats,
    )
    msemax_metrics = _measure(experimental, scanner, time.perf_counter() - started)

    for prefix, metrics in (("baseline", baseline_metrics), ("msemax", msemax_metrics)):
        setattr(batch, f"{prefix}_questions", metrics["questions"])
        setattr(batch, f"{prefix}_concepts", metrics["concepts"])
        setattr(batch, f"{prefix}_tier1", metrics["tier1"])
        setattr(batch, f"{prefix}_defects", metrics["defects"])
        setattr(batch, f"{prefix}_warnings", metrics["warnings"])
        setattr(batch, f"{prefix}_candidates", metrics["candidates"])
        setattr(batch, f"{prefix}_rejections", metrics["rejections"])
        setattr(batch, f"{prefix}_defect_kinds", metrics["defect_kinds"])

    batch.baseline_latency = baseline_metrics["latency"]
    # Report the real cost of MSEMAX: the provider time actually spent phrasing.
    batch.msemax_latency = round(sum(row.latency for row in rows.values()), 3)
    batch.generations_requested = stats.requested
    batch.generations_accepted = stats.generated
    batch.provider_errors = stats.provider_errors
    batch.rejection_reasons = dict(stats.reasons)
    batch.status = BATCH_COMPLETED
    batch.error = None
    batch.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(batch)
    return batch


def run_batch(
    db: Session,
    run: BenchmarkRun,
    *,
    service: Any,
    batch: BenchmarkBatch | None = None,
    sleep: Any = time.sleep,
) -> BenchmarkBatch | None:
    """Advance the benchmark by one bounded step.

    A unit may need several calls to this function: the first few phrase its
    blueprints a handful at a time, and the last one measures both arms from
    the cache. Returns the unit it touched, or ``None`` when nothing is left.
    """
    batch = batch or _claim_next_batch(db, run)
    if batch is None:
        return None

    try:
        finished = phrase_step(db, run, batch, service=service, sleep=sleep)
        if not finished:
            # More phrasing needed: release the unit so the next request picks
            # it up, with progress already durable.
            batch.status = BATCH_PENDING
            db.commit()
            db.refresh(batch)
            return batch
        return measure_batch(db, run, batch)
    except MsemaxConfigurationError as exc:
        batch.status = BATCH_FAILED
        batch.error = f"configuration: {exc}"
        db.commit()
        raise
    except Exception as exc:  # provider outage, timeout, quota, bad response
        batch.status = BATCH_FAILED
        batch.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        logger.warning(
            "benchmark batch %s failed (%s seed %s): %s",
            batch.id,
            batch.document,
            batch.seed,
            type(exc).__name__,
        )
        return batch


def run_progress(db: Session, run: BenchmarkRun) -> dict[str, Any]:
    rows = (
        db.query(BenchmarkBatch.status, func.count(BenchmarkBatch.id))
        .filter(BenchmarkBatch.run_id == run.id)
        .group_by(BenchmarkBatch.status)
        .all()
    )
    by_status = {status: total for status, total in rows}
    completed = by_status.get(BATCH_COMPLETED, 0)
    return {
        "run_id": run.id,
        "status": run.status,
        "total_batches": run.total_batches,
        "completed": completed,
        "pending": by_status.get(BATCH_PENDING, 0),
        "running": by_status.get(BATCH_RUNNING, 0),
        "failed": by_status.get(BATCH_FAILED, 0),
        "remaining": run.total_batches - completed,
    }


def build_report(db: Session, run: BenchmarkRun) -> dict[str, Any]:
    """Aggregate completed batches into the STEP 9 report.

    Refuses to present an A/B comparison until every batch has completed: a
    partial aggregate would understate coverage for whichever arm happened to
    be measured less, which is exactly the kind of misleading number this
    benchmark exists to avoid.
    """
    batches = (
        db.query(BenchmarkBatch)
        .filter(BenchmarkBatch.run_id == run.id)
        .order_by(BenchmarkBatch.document, BenchmarkBatch.seed)
        .all()
    )
    completed = [batch for batch in batches if batch.status == BATCH_COMPLETED]
    progress = run_progress(db, run)

    report: dict[str, Any] = {
        "configuration": {
            "run_id": run.id,
            "seeds": [int(value) for value in run.seeds.split()],
            "count": run.count,
            "documents": run.documents,
            "question_types": ALL_TYPES,
            "provider_primary": run.provider_primary,
            "provider_fallback": run.provider_fallback,
            "gemini_model": run.gemini_model,
            "groq_model": run.groq_model,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        },
        "progress": progress,
    }

    if progress["remaining"] > 0:
        report["status"] = "in_progress"
        report["note"] = (
            f"{progress['completed']}/{run.total_batches} batches completed. "
            "No A/B comparison is reported until every batch has finished."
        )
        return report

    def _sum(attr: str) -> int:
        return sum(getattr(batch, attr) for batch in completed)

    def _merge(attr: str) -> dict[str, int]:
        merged: dict[str, int] = {}
        for batch in completed:
            for key, value in (getattr(batch, attr) or {}).items():
                merged[key] = merged.get(key, 0) + value
        return merged

    def _arm(prefix: str) -> dict[str, Any]:
        questions = _sum(f"{prefix}_questions")
        candidates = _sum(f"{prefix}_candidates")
        rejections = _merge(f"{prefix}_rejections")
        return {
            "questions": questions,
            "concepts": _sum(f"{prefix}_concepts"),
            "tier1": _sum(f"{prefix}_tier1"),
            "scanner_defects": _sum(f"{prefix}_defects"),
            "scanner_warnings": _sum(f"{prefix}_warnings"),
            "candidates_written": candidates,
            "candidate_survival": (
                round(questions / candidates, 4) if candidates else 0.0
            ),
            # A written candidate that neither survived nor was rejected.
            "silent_candidate_loss": max(
                0, candidates - questions - sum(rejections.values())
            ),
            "rejections_by_stage": rejections,
            "defect_kinds": _merge(f"{prefix}_defect_kinds"),
            "latency_seconds": round(
                sum(getattr(batch, f"{prefix}_latency") for batch in completed), 3
            ),
        }

    baseline = _arm("baseline")
    msemax = _arm("msemax")
    requested = _sum("generations_requested")
    accepted = _sum("generations_accepted")

    provider_errors = _sum("provider_errors")
    all_reasons = _merge("rejection_reasons")
    # Split infrastructure failures away from genuine quality rejections. A
    # 429 says nothing about whether MSEMAX writes good questions, so mixing
    # the two produced a valid_rate that measured quota, not quality.
    provider_reasons = {
        reason: count
        for reason, count in all_reasons.items()
        if reason.startswith("provider error")
    }
    quality_reasons = {
        reason: count
        for reason, count in all_reasons.items()
        if not reason.startswith("provider error")
    }
    # Attempts where the model actually returned something to judge.
    evaluated = max(0, requested - provider_errors)

    report["status"] = "completed"
    report["baseline"] = baseline
    report["msemax"] = {
        **msemax,
        "generations_requested": requested,
        "generations_accepted": accepted,
        #: Attempts that reached the model and produced a judgeable result.
        "generations_evaluated": evaluated,
        #: Quality metric: acceptance among attempts the model answered.
        #: This is the number to read when judging MSEMAX.
        "valid_rate": round(accepted / evaluated, 4) if evaluated else None,
        #: Raw acceptance including infrastructure failures. Operational only.
        "valid_rate_including_provider_errors": (
            round(accepted / requested, 4) if requested else None
        ),
        "provider_errors": provider_errors,
        "provider_error_rate": (
            round(provider_errors / requested, 4) if requested else None
        ),
        #: Genuine MSEMAX quality rejections only.
        "rejection_reasons": quality_reasons,
        #: Infrastructure failures, kept separate for diagnosis.
        "provider_error_reasons": provider_reasons,
        #: All reasons, unsplit, for backwards compatibility.
        "rejection_reasons_all": all_reasons,
        #: True when provider failures were common enough that the quality
        #: comparison should not be trusted without a rerun.
        "measurement_reliable": (
            requested > 0 and (provider_errors / requested) <= 0.05
        ),
    }
    report["comparison"] = {
        "questions_delta": msemax["questions"] - baseline["questions"],
        "tier1_delta": msemax["tier1"] - baseline["tier1"],
        "scanner_defects_delta": (
            msemax["scanner_defects"] - baseline["scanner_defects"]
        ),
        "scanner_warnings_delta": (
            msemax["scanner_warnings"] - baseline["scanner_warnings"]
        ),
        "verdict_rule": (
            "MSEMAX is an improvement only if defects do not increase AND "
            "coverage (questions, tier 1) does not decrease."
        ),
        #: Guard against reading a quota-crippled run as a quality result.
        "measurement_reliable": (
            requested > 0 and (provider_errors / requested) <= 0.05
        ),
        "measurement_warning": (
            None
            if requested > 0 and (provider_errors / requested) <= 0.05
            else (
                f"{provider_errors}/{requested} phrasing attempts failed at the "
                "provider (quota/timeout/outage). MSEMAX questions were never "
                "generated for those blueprints, so the comparison understates "
                "MSEMAX coverage. Rerun once the provider is healthy."
            )
        ),
    }
    return report
