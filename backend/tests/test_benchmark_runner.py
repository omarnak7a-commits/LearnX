"""Batched STEP 9 benchmark: persistence, resumability and failure handling.

These tests use a real SQLite database rather than mocks, because the properties
under test *are* persistence properties: that a completed batch is never
re-measured, that partial progress survives an invocation boundary, and that a
provider failure leaves the run recoverable instead of corrupt.

Nothing here fabricates provider output. Where a provider is required, the
double raises the same exceptions a real outage produces; no test asserts that
invented model prose is good.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.benchmark import (
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PENDING,
    BenchmarkBatch,
    BenchmarkPhrasing,
    BenchmarkRun,
)
from app.services.ai_service import AIServiceError
from app.services.benchmark_runner import (
    build_report,
    corpus_documents,
    create_run,
    run_batch,
    run_progress,
)


class _Settings:
    ai_provider = "gemini"
    ai_fallback_provider = "groq"
    gemini_model = "gemini-2.5-flash"
    groq_model = "llama-3.3-70b-versatile"


@pytest.fixture(autouse=True)
def _provider_configured(monkeypatch):
    """Make the MSEMAX credential gate pass, as it does on Vercel.

    In production the provider keys come from the Vercel environment. Here a
    placeholder is enough to get past ``resolve_backend``; the request itself is
    then answered by a double that raises, so no real call is ever attempted and
    no real credential is needed. The value is never sent anywhere.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    # Only the benchmark tables: other models use Postgres-specific column
    # types (ARRAY) that SQLite cannot compile, and they are irrelevant here.
    Base.metadata.create_all(
        bind=engine,
        tables=[
            BenchmarkBatch.__table__,
            BenchmarkRun.__table__,
            BenchmarkPhrasing.__table__,
        ],
    )
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


class _DownProvider:
    """A provider that is unreachable, as in a real outage."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc or AIServiceError("provider unavailable")
        self.calls = 0

    def complete_structured(self, **kwargs):
        self.calls += 1
        raise self.exc




def _drive_one_unit(db, run, service=None):
    """Advance until one (document, seed) unit reaches a terminal state.

    Phrasing is now bounded per request, so a unit takes several run_batch()
    calls: this mirrors what the remote client does in production.
    """
    service = service or _DownProvider()
    last = None
    for _ in range(200):
        # sleep is stubbed out: backoff timing is covered by its own unit test,
        # and real sleeps would add minutes to the suite for no extra coverage.
        batch = run_batch(db, run, service=service, sleep=lambda _s: None)
        if batch is None:
            return last
        last = batch
        if batch.status in (BATCH_COMPLETED, BATCH_FAILED):
            return batch
    raise AssertionError("unit did not finish")


def _drive_to_completion(db, run, service=None):
    service = service or _DownProvider()
    for _ in range(5000):
        if run_batch(db, run, service=service, sleep=lambda _s: None) is None:
            return
    raise AssertionError("run did not finish")


# --------------------------------------------------------------------------- #
# A. Run creation and the batch matrix
# --------------------------------------------------------------------------- #


def test_run_materialises_one_batch_per_document_and_seed(db) -> None:
    run = create_run(db, settings=_Settings(), seeds=(1, 3), count=8)

    expected = len(corpus_documents()) * 2
    assert run.total_batches == expected
    assert db.query(BenchmarkBatch).filter_by(run_id=run.id).count() == expected
    assert run_progress(db, run)["pending"] == expected
    # Methodology is recorded with the run, so a report can be read in context.
    assert run.seeds == "1 3"
    assert run.count == 8
    # Provider NAMES only: no credential may reach the database.
    assert run.provider_primary == "gemini"
    assert "key" not in str(run.__dict__).lower()


def test_a_document_seed_pair_cannot_be_duplicated(db) -> None:
    """The resumability guarantee is enforced by the database, not by code."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    document = run.documents[0]

    db.add(BenchmarkBatch(run_id=run.id, document=document, seed=1))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


# --------------------------------------------------------------------------- #
# B. Executing batches
# --------------------------------------------------------------------------- #


def test_batch_records_both_arms_and_advances_progress(db) -> None:
    """One batch measures control and experiment against the same input."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)

    batch = _drive_one_unit(db, run)

    assert batch is not None
    assert batch.status == BATCH_COMPLETED
    # The deterministic arm never contacts a provider, so it must still produce
    # a quiz even though the provider is down.
    assert batch.baseline_questions > 0
    # And MSEMAX degrades to the deterministic candidates rather than losing
    # coverage: this is the fallback contract, measured.
    assert batch.msemax_questions == batch.baseline_questions
    assert batch.provider_errors > 0
    assert batch.generations_accepted == 0
    assert run_progress(db, run)["completed"] == 1


def test_completed_batches_are_never_re_measured(db) -> None:
    """Repeated calls advance the run instead of redoing finished work."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    total = run.total_batches

    seen: list[tuple[str, int]] = []
    for _ in range(total):
        batch = _drive_one_unit(db, run)
        assert batch is not None
        seen.append((batch.document, batch.seed))

    assert len(seen) == len(set(seen)), "a (document, seed) pair was measured twice"
    assert run_progress(db, run)["remaining"] == 0
    # Once the matrix is exhausted there is simply no work left.
    assert run_batch(db, run, service=_DownProvider()) is None


def test_progress_survives_an_invocation_boundary(db) -> None:
    """State lives in the database, not in process memory or on disk."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    _drive_one_unit(db, run)
    run_id = run.id

    # Simulate a new serverless invocation: fresh session, same database.
    db.expunge_all()
    reloaded = db.query(type(run)).filter_by(id=run_id).first()
    assert reloaded is not None
    assert run_progress(db, reloaded)["completed"] == 1


# --------------------------------------------------------------------------- #
# C. Failure handling
# --------------------------------------------------------------------------- #


def test_a_failed_batch_is_recorded_and_retryable(db) -> None:
    """A crash mid-batch must not corrupt the run or lose the slot."""
    import app.services.benchmark_runner as runner

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)

    def _explode(*args, **kwargs):
        raise TimeoutError("deadline exceeded")

    original = runner.generate_quiz
    runner.generate_quiz = _explode
    try:
        failed = run_batch(db, run, service=_DownProvider())
    finally:
        # Restore directly rather than via monkeypatch.undo(), which would also
        # revert the autouse fixture that satisfies the credential gate.
        runner.generate_quiz = original

    assert failed is not None
    assert failed.status == BATCH_FAILED
    assert "TimeoutError" in (failed.error or "")
    assert failed.attempts >= 1
    # The batch is still eligible, so the run is recoverable.
    assert run_progress(db, run)["failed"] == 1

    retried = _drive_one_unit(db, run)
    assert retried is not None
    assert retried.id == failed.id
    assert retried.status == BATCH_COMPLETED
    assert retried.attempts >= 2


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("deadline exceeded"),
        AIServiceError("rate limit exceeded"),
        ValueError("malformed structured output"),
        RuntimeError("quota exhausted"),
    ],
)
def test_provider_failures_do_not_reduce_coverage(db, failure) -> None:
    """Every provider failure mode falls back to the deterministic question."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)

    batch = _drive_one_unit(db, run, service=_DownProvider(failure))

    assert batch is not None
    assert batch.status == BATCH_COMPLETED
    assert batch.msemax_questions == batch.baseline_questions
    assert batch.msemax_defects == batch.baseline_defects


# --------------------------------------------------------------------------- #
# D. Honest reporting
# --------------------------------------------------------------------------- #


def test_no_ab_comparison_before_every_batch_completes(db) -> None:
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    _drive_one_unit(db, run)

    report = build_report(db, run)

    assert report["status"] == "in_progress"
    assert "comparison" not in report
    assert "baseline" not in report
    assert report["progress"]["remaining"] > 0


def test_report_aggregates_only_completed_batches(db) -> None:
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    _drive_to_completion(db, run)

    report = build_report(db, run)

    assert report["status"] == "completed"
    assert report["baseline"]["questions"] > 0
    # With the provider down the two arms must be identical, and no candidate
    # may disappear unaccounted for.
    assert report["msemax"]["questions"] == report["baseline"]["questions"]
    assert report["comparison"]["scanner_defects_delta"] == 0
    assert report["baseline"]["silent_candidate_loss"] == 0
    assert report["msemax"]["silent_candidate_loss"] == 0
    # Every attempt died at the provider, so nothing was ever judged. valid_rate
    # must be None ("not measured"), NOT 0.0, which would read as "MSEMAX wrote
    # unusable questions" -- the exact confusion that made STEP 9 inconclusive.
    assert report["msemax"]["generations_evaluated"] == 0
    assert report["msemax"]["valid_rate"] is None
    assert report["msemax"]["provider_errors"] > 0
    assert report["msemax"]["measurement_reliable"] is False
    # Quality rejections stay empty: no question was ever produced to reject.
    assert report["msemax"]["rejection_reasons"] == {}
    # Configuration is reported for provenance -- names only, never secrets.
    assert report["configuration"]["provider_primary"] == "gemini"
    assert "api_key" not in str(report).lower()


# --------------------------------------------------------------------------- #
# E. Micro-batching: fitting inside a Vercel invocation
# --------------------------------------------------------------------------- #


def test_one_request_is_bounded_by_the_call_cap(db) -> None:
    """A single request must never attempt a whole unit's provider calls.

    vercel.json uses the legacy ``builds`` property, so maxDuration cannot be
    raised and the platform default (10-15s) applies. One provider call can
    take up to AI_TIMEOUT_SECONDS on its own, so a request phrases only a few
    blueprints and defers the rest.
    """
    from app.services.benchmark_runner import MAX_CALLS_PER_REQUEST

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    batch = run_batch(db, run, service=_DownProvider())
    assert batch is not None

    phrased = db.query(BenchmarkPhrasing).filter_by(batch_id=batch.id).count()
    assert 0 < phrased <= MAX_CALLS_PER_REQUEST, (
        "a request phrased more blueprints than its per-invocation cap allows"
    )
    # The unit is not finished yet, so it is handed back for the next request.
    assert batch.status == BATCH_PENDING
    assert batch.blueprint_count > MAX_CALLS_PER_REQUEST


def test_phrasings_accumulate_across_requests_without_repeating_work(db) -> None:
    """Resume at blueprint granularity: no blueprint is phrased twice."""
    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    provider = _DownProvider()

    batch = _drive_one_unit(db, run, service=provider)
    assert batch is not None
    assert batch.status == BATCH_COMPLETED

    rows = db.query(BenchmarkPhrasing).filter_by(batch_id=batch.id).all()
    ids = [row.blueprint_id for row in rows]
    assert len(ids) == len(set(ids)), "a blueprint was phrased more than once"
    assert len(ids) == batch.blueprint_count
    # Exactly one provider attempt per blueprint, no wasted quota.
    assert provider.calls == batch.blueprint_count


def test_measurement_makes_no_provider_calls(db) -> None:
    """The final scoring pass replays cached prose only."""
    from app.services.benchmark_runner import measure_batch, phrase_step  # noqa: F401

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    batch = _claim_for_test(db, run)

    provider = _DownProvider()
    while not phrase_step(db, run, batch, service=provider):
        pass
    calls_after_phrasing = provider.calls

    measure_batch(db, run, batch)

    assert provider.calls == calls_after_phrasing, (
        "measurement must not contact the provider"
    )
    assert batch.status == BATCH_COMPLETED


def _claim_for_test(db, run):
    from app.services.benchmark_runner import _claim_next_batch

    batch = _claim_next_batch(db, run)
    assert batch is not None
    return batch


# --------------------------------------------------------------------------- #
# Quota resilience: 429 must not be mistaken for poor MSEMAX quality
# --------------------------------------------------------------------------- #


def _quota_error():
    """The exact shape a rate-limited Gemini+Groq pair produces."""
    from app.services.ai_service import AIUnavailableError, ProviderFailure

    return AIUnavailableError(
        "The AI service is temporarily unavailable. Please try again shortly.",
        failures=[
            ProviderFailure("gemini", "quota_rate_limit", 429, "RESOURCE_EXHAUSTED",
                            "gemini-3.7-flash"),
            ProviderFailure("groq", "quota_rate_limit", 429, "rate_limit_exceeded",
                            "openai/gpt-oss-120b"),
        ],
    )


def _rejection(blueprint_id: str, reason: str):
    from app.services.quiz_msemax import MsemaxRejection

    return MsemaxRejection(blueprint_id, "concept", "cause_effect", reason)


def _provider_reason(exc) -> str:
    from app.services.quiz_msemax import describe_provider_failure

    return f"provider error [{describe_provider_failure(exc)}]"


class _Blueprint:
    id = "det-bp-1"
    concept_id = "concept"
    cognitive_skill = "cause_effect"


def _candidate(blueprint_id: str = "det-bp-1") -> dict:
    return {
        "id": f"msemax-{blueprint_id}",
        "blueprint_id": blueprint_id,
        "type": "mcq",
        "difficulty": "medium",
        "source_pages": [1],
        "source_quote": "q",
        "prompt": "Why does X cause Y?",
        "explanation": "e",
        "origin": "msemax",
        "options": ["a", "b", "c", "d"],
        "correct_answer": "a",
    }


def test_backoff_is_exponential_and_capped() -> None:
    from app.services.benchmark_runner import retry_delay_seconds

    assert retry_delay_seconds(1, base=1.0, cap=8.0) == 1.0
    assert retry_delay_seconds(2, base=1.0, cap=8.0) == 2.0
    assert retry_delay_seconds(3, base=1.0, cap=8.0) == 4.0
    # Never exceeds the cap, so one wait cannot overrun the invocation.
    assert retry_delay_seconds(9, base=1.0, cap=8.0) == 8.0
    # A server-supplied Retry-After wins, but is still clamped.
    assert retry_delay_seconds(1, 4.0, base=1.0, cap=8.0) == 4.0
    assert retry_delay_seconds(1, 999.0, base=1.0, cap=8.0) == 8.0


def test_429_is_retried_then_succeeds(monkeypatch) -> None:
    """A transient 429 must not cost the blueprint its question."""
    import app.services.benchmark_runner as runner

    attempts = {"n": 0}

    def flaky(blueprint, backend=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return None, _rejection(blueprint.id, _provider_reason(_quota_error()))
        return _candidate(blueprint.id), None

    monkeypatch.setattr(runner, "generate_candidate", flaky)
    slept: list[float] = []
    candidate, rejection, transient = runner.phrase_with_retry(
        _Blueprint(), backend=object(), sleep=slept.append
    )

    assert attempts["n"] == 3
    assert candidate is not None
    assert rejection is None
    assert transient is False
    assert slept == [1.0, 2.0]  # exponential, and it really did wait


def test_exhausted_retries_are_flagged_transient_not_rejected(monkeypatch) -> None:
    import app.services.benchmark_runner as runner

    attempts = {"n": 0}

    def always_429(blueprint, backend=None):
        attempts["n"] += 1
        return None, _rejection(blueprint.id, _provider_reason(_quota_error()))

    monkeypatch.setattr(runner, "generate_candidate", always_429)
    candidate, rejection, transient = runner.phrase_with_retry(
        _Blueprint(), backend=object(), attempts=3, sleep=lambda _s: None
    )

    assert attempts["n"] == 3
    assert candidate is None
    # The crucial bit: infrastructure failure, NOT a quality verdict.
    assert transient is True


def test_quality_rejection_is_never_retried(monkeypatch) -> None:
    """Retrying a deterministic verdict would only waste quota."""
    import app.services.benchmark_runner as runner

    attempts = {"n": 0}

    def bad_output(blueprint, backend=None):
        attempts["n"] += 1
        return None, _rejection(blueprint.id, "malformed output: bad schema")

    monkeypatch.setattr(runner, "generate_candidate", bad_output)
    candidate, rejection, transient = runner.phrase_with_retry(
        _Blueprint(), backend=object(), sleep=lambda _s: None
    )

    assert attempts["n"] == 1
    assert candidate is None
    assert transient is False
    assert rejection.reason.startswith("malformed output")


def test_deterministic_provider_failure_is_not_retried(monkeypatch) -> None:
    """A retired model or bad key repeats identically; retrying is pointless."""
    import app.services.benchmark_runner as runner
    from app.services.ai_service import AIUnavailableError, ProviderFailure

    attempts = {"n": 0}
    fatal = AIUnavailableError(
        "unavailable",
        failures=[ProviderFailure("gemini", "model_not_found", 404, "NOT_FOUND")],
    )

    def not_found(blueprint, backend=None):
        attempts["n"] += 1
        return None, _rejection(blueprint.id, _provider_reason(fatal))

    monkeypatch.setattr(runner, "generate_candidate", not_found)
    _, _, transient = runner.phrase_with_retry(
        _Blueprint(), backend=object(), sleep=lambda _s: None
    )
    assert attempts["n"] == 1
    assert transient is False


def test_quota_failure_is_not_persisted_and_unit_stays_resumable(db, monkeypatch) -> None:
    """The core resumability guarantee.

    A 429 must leave no row behind: the unique constraint would otherwise
    freeze the hole permanently and the unit would complete with missing
    MSEMAX questions that look like MSEMAX failures.
    """
    import app.services.benchmark_runner as runner
    from app.services.benchmark_runner import create_run, phrase_step

    class _Svc:
        def complete_structured(self, **kwargs):
            raise RuntimeError("never reached")

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    batch = runner._claim_next_batch(db, run)

    monkeypatch.setattr(
        runner,
        "generate_candidate",
        lambda bp, backend=None: (
            None,
            _rejection(bp.id, _provider_reason(_quota_error())),
        ),
    )
    finished = phrase_step(
        db, run, batch, service=_Svc(), budget_seconds=60, max_calls=5
    )

    rows = (
        db.query(BenchmarkPhrasing)
        .filter(BenchmarkPhrasing.batch_id == batch.id)
        .all()
    )
    assert finished is False
    assert rows == []          # nothing frozen
    assert batch.phrased_count == 0

    # Provider recovers: the same blueprints are phrased, exactly once each.
    monkeypatch.setattr(
        runner,
        "generate_candidate",
        lambda bp, backend=None: (_candidate(bp.id), None),
    )
    for _ in range(60):
        if phrase_step(db, run, batch, service=_Svc(), budget_seconds=60, max_calls=5):
            break

    rows = (
        db.query(BenchmarkPhrasing)
        .filter(BenchmarkPhrasing.batch_id == batch.id)
        .all()
    )
    assert len(rows) == batch.blueprint_count
    assert len({row.blueprint_id for row in rows}) == len(rows)  # no duplicates
    assert all(row.candidate for row in rows)


def test_report_separates_provider_errors_from_quality_rejections(db) -> None:
    """valid_rate must measure quality, not quota."""
    from datetime import datetime

    from app.services.benchmark_runner import build_report, create_run

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    batches = db.query(BenchmarkBatch).filter(BenchmarkBatch.run_id == run.id).all()
    for batch in batches:
        batch.status = BATCH_COMPLETED
        batch.completed_at = datetime.utcnow()
        for prefix in ("baseline", "msemax"):
            setattr(batch, f"{prefix}_questions", 8)
            setattr(batch, f"{prefix}_concepts", 6)
            setattr(batch, f"{prefix}_tier1", 5)
            setattr(batch, f"{prefix}_defects", 0)
            setattr(batch, f"{prefix}_warnings", 0)
            setattr(batch, f"{prefix}_candidates", 10)
            setattr(batch, f"{prefix}_rejections", {"diversity_selection": 2})
            setattr(batch, f"{prefix}_defect_kinds", {})
            setattr(batch, f"{prefix}_latency", 1.0)
        batch.generations_requested = 10
        batch.generations_accepted = 3
        batch.provider_errors = 6
        batch.rejection_reasons = {
            "provider error: quota_rate_limit": 6,
            "malformed output": 1,
        }
    db.commit()

    msemax = build_report(db, run)["msemax"]
    n = len(batches)

    assert msemax["generations_requested"] == 10 * n
    assert msemax["provider_errors"] == 6 * n
    # Denominator excludes attempts the model never answered.
    assert msemax["generations_evaluated"] == 4 * n
    assert msemax["valid_rate"] == round((3 * n) / (4 * n), 4)
    # The old, polluted figure is retained but clearly labelled.
    assert msemax["valid_rate_including_provider_errors"] == round((3 * n) / (10 * n), 4)
    # Quality reasons must not contain infrastructure noise.
    assert msemax["rejection_reasons"] == {"malformed output": 1 * n}
    assert msemax["provider_error_reasons"] == {
        "provider error: quota_rate_limit": 6 * n
    }
    # A 60% provider-error run is not a trustworthy quality measurement.
    assert msemax["measurement_reliable"] is False


def test_clean_run_is_marked_reliable(db) -> None:
    from datetime import datetime

    from app.services.benchmark_runner import build_report, create_run

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    for batch in db.query(BenchmarkBatch).filter(BenchmarkBatch.run_id == run.id).all():
        batch.status = BATCH_COMPLETED
        batch.completed_at = datetime.utcnow()
        for prefix in ("baseline", "msemax"):
            setattr(batch, f"{prefix}_questions", 8)
            setattr(batch, f"{prefix}_concepts", 6)
            setattr(batch, f"{prefix}_tier1", 5)
            setattr(batch, f"{prefix}_defects", 0)
            setattr(batch, f"{prefix}_warnings", 0)
            setattr(batch, f"{prefix}_candidates", 10)
            setattr(batch, f"{prefix}_rejections", {})
            setattr(batch, f"{prefix}_defect_kinds", {})
            setattr(batch, f"{prefix}_latency", 1.0)
        batch.generations_requested = 10
        batch.generations_accepted = 9
        batch.provider_errors = 0
        batch.rejection_reasons = {"grounding": 1}
    db.commit()

    report = build_report(db, run)
    assert report["msemax"]["measurement_reliable"] is True
    assert report["msemax"]["valid_rate"] == 0.9
    assert report["msemax"]["provider_error_reasons"] == {}
    assert report["comparison"]["measurement_warning"] is None


def test_persistent_quota_failure_still_completes_the_run(db, monkeypatch) -> None:
    """A permanently rate-limited provider must not stall the run forever.

    Deferring a transient failure is right for a short 429 burst, but if the
    provider never recovers the unit would defer indefinitely and the benchmark
    could never finish. After MAX_TRANSIENT_DEFERRALS the failure is recorded
    so the run terminates -- while still being classified as a provider error,
    never as an MSEMAX quality rejection.
    """
    from app.services import benchmark_runner as runner

    monkeypatch.setattr(runner, "MAX_TRANSIENT_DEFERRALS", 2)

    def always_rate_limited(blueprint, *, backend):
        return None, runner.MsemaxRejection(
            blueprint_id=blueprint.id,
            concept_id=blueprint.concept_id,
            cognitive_skill=blueprint.cognitive_skill,
            reason="provider error [gemini: quota_rate_limit status=429]",
        )

    monkeypatch.setattr(runner, "generate_candidate", always_rate_limited)

    run = create_run(db, settings=_Settings(), seeds=(1,), count=8)
    batch = _drive_one_unit(db, run)

    # The unit reaches a terminal state instead of deferring forever.
    assert batch is not None
    assert batch.status == BATCH_COMPLETED
    # Coverage is preserved: the deterministic arm still produced questions.
    assert batch.baseline_questions > 0
    assert batch.msemax_questions == batch.baseline_questions
    # And the failures are booked as provider errors, not quality rejections.
    assert batch.provider_errors > 0
    assert all(
        reason.startswith("provider error")
        for reason in (batch.rejection_reasons or {})
    )
