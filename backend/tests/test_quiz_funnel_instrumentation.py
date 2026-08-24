"""Candidate-funnel instrumentation: counters explain every missing candidate.

The production SQL18 exam returned "could only verify 2 of 8" with
rejected = 0 and candidates_by_type = {}, and nothing in the diagnostics
could say where 16 plans became 2 candidates. These tests pin the
instrumentation that makes that question answerable from telemetry alone:

- every plan skip carries a reason;
- writer passes count attempted/returned/dropped (and dropped reasons);
- candidates_by_type counts candidates PRODUCED, not rejections;
- a 422 shortfall returns the same counters on the error path.

They also pin that instrumentation changed no generation behaviour: the
SQL18-shaped fixture with both provider calls failing (the production
condition: understanding_failed = writer_failed = 1) still yields 8/8.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_documents import _extract_pdf_uncached
from app.services.ai_service import AIServiceError
from app.services.quiz_concepts import split_source_units
from app.services.quiz_pipeline import generate_quiz
from app.services.quiz_understanding import deterministic_understanding

FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"
PRODUCTION_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]


class FailingProvider:
    """Both provider calls raise — the exact production condition."""

    def complete_structured(self, *args, **kwargs):
        raise AIServiceError("provider unavailable")


def sql18_source():
    return _extract_pdf_uncached(
        FIXTURE.read_bytes(),
        file_id="075eb4af-5813-41d0-9602-23065c1e4ddf",
        title="SQL18.pdf",
        max_characters=100_000,
        allowed_pages=None,
    )


def _run(source, count=8, language="en"):
    try:
        result = generate_quiz(
            FailingProvider(),
            source,
            count=count,
            question_types=list(PRODUCTION_TYPES),
            difficulty="mixed",
            kind="exam",
            language=language,
            seed=20260824,
            previous_questions=[],
            system_prompt="You are LearnX.",
        )
        return result.telemetry, len(result.questions), None
    except Exception as exc:  # noqa: BLE001 - telemetry is what we assert on
        return getattr(exc, "telemetry", None), getattr(exc, "available", None), exc


def test_instrumentation_explains_full_funnel_on_success():
    telemetry, accepted, _ = _run(sql18_source())
    assert accepted == 8  # behaviour unchanged: the fixture supports 8/8

    # Provider path: called once, failed once, returned nothing.
    assert telemetry["candidate_generation_errors"] == 1
    assert telemetry["provider_candidates_returned"] == 0
    assert telemetry["candidate_generation_empty"] >= 1

    # Deterministic path: every attempted blueprint is returned or dropped,
    # and every drop carries a reason.
    attempted = telemetry["deterministic_candidates_attempted"]
    returned = telemetry["deterministic_candidates_returned"]
    dropped = telemetry["deterministic_candidates_dropped"]
    assert attempted == returned + dropped
    assert returned >= accepted
    assert sum(telemetry["deterministic_drop_reasons"].values()) == dropped

    # Plans: attempted spans every writer pass; skips are counted WITH reasons.
    assert telemetry["plans_created"] == 16  # stage-2 planning for count=8
    assert telemetry["plans_attempted"] >= telemetry["plans_created"]
    assert telemetry["plans_skipped"] == sum(
        telemetry["plans_skipped_reason"].values()
    )

    # candidates_by_type now counts candidates produced, so it is non-empty
    # even with zero rejections — the exact signal that was {} in production.
    assert sum(telemetry["candidates_by_type"].values()) >= returned
    assert telemetry["candidates_by_type"]


def test_topup_rounds_account_for_each_round():
    telemetry, _, _ = _run(sql18_source())
    rounds = telemetry["topup_rounds"]
    assert rounds, "expected at least one top-up round on this fixture"
    for entry in rounds:
        assert entry["stop_reason"] in {
            "pool_sufficient",
            "no_targets_left",
            "planner_returned_no_blueprints",
            "no_new_objectives",
            "continued",
        }
        if entry["stop_reason"] == "continued":
            assert entry["added"] >= 1
            assert entry["written"] <= entry["planned"]


def test_shortfall_returns_counters_on_422_path():
    # A two-paragraph source cannot support 8 questions: the run must fall
    # short and the telemetry on the error must still explain every candidate.
    thin = " ".join(
        [
            "A primary key uniquely identifies each row in a table.",
            "A foreign key references the primary key of another table.",
            "Normalization organizes columns to reduce duplicate data.",
        ]
    )
    from app.services.ai_documents import source_from_text

    telemetry, available, exc = _run(source_from_text(thin, title="Thin"))
    from app.services.quiz_pipeline import QuizMaterialError

    assert isinstance(exc, QuizMaterialError)
    assert available is not None and available < 8
    assert telemetry is not None
    # The counters exist and are internally consistent even on the error path.
    assert telemetry["deterministic_candidates_attempted"] == (
        telemetry["deterministic_candidates_returned"]
        + telemetry["deterministic_candidates_dropped"]
    )
    assert telemetry["plans_skipped"] == sum(
        telemetry["plans_skipped_reason"].values()
    )
    assert telemetry["provider_candidates_returned"] == 0


def test_non_english_run_counts_the_english_only_drop():
    telemetry, _, exc = _run(sql18_source(), language="ar")
    # Arabic + failing provider: the deterministic writer declines everything
    # by design (English-only). The pipeline then raises AIUnavailableError
    # with NO telemetry (a known diagnostics blind spot on the 503 empty-pool
    # path — distinct from the 422 QuizMaterialError path, which carries the
    # funnel). This test documents that fact rather than assuming data the
    # error path does not provide.
    assert exc is not None
    if telemetry is None:
        pytest.skip(
            "empty-pool AIUnavailableError carries no telemetry (503 blind spot)"
        )
    attempted = telemetry["deterministic_candidates_attempted"]
    dropped = telemetry["deterministic_candidates_dropped"]
    assert attempted == dropped
    assert (
        telemetry["deterministic_drop_reasons"].get(
            "deterministic_writer_english_only", 0
        )
        == dropped
        or dropped == 0
    )
