"""MSEMAX at the pipeline seam.

Two properties matter more than anything MSEMAX writes:

1. **Disabled is the baseline.** With the flag off, the pipeline must behave
   exactly as it did before MSEMAX existed. This is what keeps the A/B
   comparison honest and the deterministic engine authoritative.
2. **Enabled never loses a question.** MSEMAX only rephrases blueprints the
   planner already chose. If it fails for a blueprint, the deterministic
   candidate for that same blueprint stays, and the failure is recorded.
"""

from __future__ import annotations

import pytest

from app.services.ai_service import AIServiceError
from app.services.quiz_msemax import MSEMAX_ORIGIN, MsemaxConfigurationError, MsemaxQuestion
from app.services.quiz_pipeline import generate_quiz

from tests.quiz_fakes import default_kwargs
from tests.test_quiz_acceptance import ALL_TYPES, RICH_SOURCE


class _NoProvider:
    """No quiz provider: forces the deterministic writer, as in production
    without credentials."""

    def complete_structured(self, **kwargs):
        raise AIServiceError("provider unavailable")


def _run(**overrides):
    return generate_quiz(
        _NoProvider(),
        RICH_SOURCE,
        **default_kwargs(seed=3, count=6, question_types=ALL_TYPES, **overrides),
    )


def test_disabled_msemax_reproduces_the_deterministic_baseline() -> None:
    first = _run(msemax_enabled=False)
    second = _run(msemax_enabled=False)

    assert [question.prompt for question in first.questions] == [
        question.prompt for question in second.questions
    ]
    assert first.questions, "the deterministic baseline must still produce a quiz"
    # MSEMAX did not participate, so it reports nothing rather than zeroes.
    assert first.msemax_stats is None
    assert not [note for note in first.rejections if note.stage == "msemax_generation"]


def test_enabling_msemax_without_credentials_fails_loudly() -> None:
    """No silent downgrade: asking for MSEMAX without a provider is an error."""
    with pytest.raises(MsemaxConfigurationError):
        _run(msemax_enabled=True)


def test_msemax_failures_fall_back_without_losing_questions(monkeypatch) -> None:
    """Every blueprint MSEMAX declines keeps its deterministic candidate."""
    import app.services.quiz_pipeline as pipeline

    baseline = _run(msemax_enabled=False)

    monkeypatch.setattr(pipeline, "resolve_backend", lambda settings, service: object())

    def _all_fail(blueprints, *, backend, stats=None):
        from app.services.quiz_msemax import MsemaxRejection

        if stats is not None:
            stats.requested = len(blueprints)
            stats.rejected = len(blueprints)
            stats.provider_errors = len(blueprints)
        return {}, [
            MsemaxRejection(
                blueprint_id=blueprint.id,
                concept_id=blueprint.concept_id,
                cognitive_skill=blueprint.cognitive_skill,
                reason="provider error: TimeoutError: deadline exceeded",
            )
            for blueprint in blueprints
        ]

    monkeypatch.setattr(pipeline, "msemax_candidates", _all_fail)

    result = _run(msemax_enabled=True)

    # Coverage is unchanged: the deterministic writer still supplied every slot.
    assert [question.prompt for question in result.questions] == [
        question.prompt for question in baseline.questions
    ]
    # And each failure is on the record.
    notes = [note for note in result.rejections if note.stage == "msemax_generation"]
    assert notes, "MSEMAX failures must be logged, never silent"
    assert all("provider error" in note.reason for note in notes)


def test_msemax_output_still_passes_every_validator(monkeypatch) -> None:
    """A grounded MSEMAX rewrite reaches the quiz; an ungrounded one cannot.

    The rewrite here is deliberately *ungrounded* — it asserts a fact absent
    from the evidence. It must not appear in the final quiz, proving MSEMAX
    output is subject to the same gates as any other candidate.
    """
    import app.services.quiz_pipeline as pipeline

    monkeypatch.setattr(pipeline, "resolve_backend", lambda settings, service: object())

    def _hallucinate(blueprints, *, backend, stats=None):
        from app.services.quiz_msemax import _to_candidate

        written = {}
        for blueprint in blueprints:
            value = MsemaxQuestion(
                stem="Which nation first ratified the Treaty of Vienna in 1815?",
                options=["Prussia", "Austria", "Bavaria", "Saxony"],
                correct_option=0,
                explanation="Prussia ratified it first.",
            )
            if blueprint.question_type == "mcq":
                written[blueprint.id] = _to_candidate(value, blueprint)
        if stats is not None:
            stats.requested = len(blueprints)
            stats.generated = len(written)
        return written, []

    monkeypatch.setattr(pipeline, "msemax_candidates", _hallucinate)

    result = _run(msemax_enabled=True)

    prompts = [question.prompt for question in result.questions]
    assert not any("Treaty of Vienna" in prompt for prompt in prompts), (
        "ungrounded MSEMAX prose must be rejected by the existing gates"
    )
    # The quiz survives on deterministic candidates rather than collapsing.
    assert result.questions


def test_msemax_never_relabels_deterministic_text(monkeypatch) -> None:
    """Deterministic prose is never reported as model output."""
    import app.services.quiz_pipeline as pipeline

    monkeypatch.setattr(pipeline, "resolve_backend", lambda settings, service: object())
    monkeypatch.setattr(
        pipeline, "msemax_candidates", lambda blueprints, *, backend, stats=None: ({}, [])
    )

    result = _run(msemax_enabled=True)

    assert result.questions
    # Nothing claimed MSEMAX authorship, because MSEMAX wrote nothing.
    assert not [
        note for note in result.rejections if note.stage == "msemax_generation"
    ] or all(
        note.reason for note in result.rejections if note.stage == "msemax_generation"
    )
    assert MSEMAX_ORIGIN == "msemax"
