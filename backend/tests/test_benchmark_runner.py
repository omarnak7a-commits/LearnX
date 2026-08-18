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
        batch = run_batch(db, run, service=service)
        if batch is None:
            return last
        last = batch
        if batch.status in (BATCH_COMPLETED, BATCH_FAILED):
            return batch
    raise AssertionError("unit did not finish")


def _drive_to_completion(db, run, service=None):
    service = service or _DownProvider()
    for _ in range(5000):
        if run_batch(db, run, service=service) is None:
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
    assert report["msemax"]["valid_rate"] == 0.0
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
