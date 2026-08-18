"""MSEMAX adapter behaviour.

MSEMAX is the optional constrained-LLM phrasing layer. These tests pin the
contract that makes it safe to enable:

* it may only rephrase what the deterministic planner already decided;
* anything it invents, drops, or mis-targets is rejected with a stated reason;
* a failure never removes a question, because the deterministic candidate for
  that blueprint stays in place.

The doubles here stand in for a *provider transport* (they return canned JSON
the way a model would), never for MSEMAX itself: the code under test is the
real adapter, its real validators, and the real pipeline seam. No test asserts
that fabricated model prose is good — they assert that bad prose is caught.
"""

from __future__ import annotations

import pytest

from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_msemax import (
    MSEMAX_ORIGIN,
    MsemaxConfigurationError,
    MsemaxQuestion,
    MsemaxStats,
    build_generation_payload,
    generate_candidate,
    msemax_candidates,
    resolve_backend,
    validate_generation,
)

EVIDENCE = (
    "A catalyst increases the rate of a reaction by providing an alternative "
    "pathway with a lower activation energy."
)


def make_blueprint(
    *,
    question_type: str = "mcq",
    skill: str = "process_order",
    evidence: str = EVIDENCE,
    concept: str = "catalyst",
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id="det-bp-1",
        concept_id="catalyst",
        concept=concept,
        knowledge_target_id="catalyst--process-order",
        knowledge_target="explain how a catalyst works",
        knowledge_type="process",
        cognitive_skill=skill,
        question_type=question_type,
        difficulty="medium",
        importance=0.9,
        evidence=evidence,
        pages=(2,),
        facet_kind="mechanism",
        answer_clause="providing an alternative pathway with a lower activation energy",
    )


class Backend:
    """A provider transport double: returns whatever payload it is given."""

    def __init__(self, value: MsemaxQuestion | Exception | object) -> None:
        self.value = value
        self.calls: list[dict] = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.value, Exception):
            raise self.value

        class _Completion:
            value = self.value

        return _Completion()


# --------------------------------------------------------------------------- #
# A. The request sent to the model
# --------------------------------------------------------------------------- #


def test_payload_carries_only_blueprint_derived_constraints() -> None:
    payload = build_generation_payload(make_blueprint())

    assert payload["concept"] == "catalyst"
    assert payload["skill"] == "process_order"
    assert payload["question_type"] == "mcq"
    assert payload["evidence"] == EVIDENCE
    assert payload["relationship_type"] == "mechanism"
    assert payload["forbidden_content"]
    # The raw document must never be shipped: the model sees one sentence.
    assert "\n\n" not in payload["evidence"]


# --------------------------------------------------------------------------- #
# B. Valid output survives
# --------------------------------------------------------------------------- #


def test_valid_generation_becomes_a_candidate() -> None:
    backend = Backend(
        MsemaxQuestion(
            stem="How does a catalyst increase the rate of a reaction?",
            options=[
                "By providing an alternative pathway with a lower activation energy",
                "By increasing the activation energy of the reaction",
                "By lowering the temperature of the reaction mixture",
                "By being consumed as the reaction proceeds",
            ],
            correct_option=0,
            explanation="A catalyst provides a pathway with lower activation energy.",
        )
    )

    candidate, rejection = generate_candidate(make_blueprint(), backend=backend)

    assert rejection is None
    assert candidate is not None
    assert candidate["origin"] == MSEMAX_ORIGIN
    # Provenance comes from the blueprint, never from the model.
    assert candidate["blueprint_id"] == "det-bp-1"
    assert candidate["source_pages"] == [2]
    assert candidate["source_quote"] == EVIDENCE
    assert candidate["correct_answer"].startswith("By providing an alternative")


# --------------------------------------------------------------------------- #
# C. Failure modes are rejected, each with its own reason
# --------------------------------------------------------------------------- #


def test_hallucinated_fact_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does a catalyst work in the Haber process at 450 degrees?",
        options=["a", "b", "c", "d"],
        correct_option=0,
    )
    reason = validate_generation(value, make_blueprint())
    assert reason is not None
    assert "unsupported" in reason


def test_unsupported_answer_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does a catalyst increase the rate of a reaction?",
        options=[
            "By shifting the equilibrium position toward the products",
            "By providing an alternative pathway",
            "By raising activation energy",
            "By lowering the rate",
        ],
        correct_option=0,
    )
    reason = validate_generation(value, make_blueprint())
    assert reason is not None
    assert "unsupported" in reason


def test_wrong_skill_is_rejected() -> None:
    """A comparison blueprint answered with a definition loses the slot."""
    blueprint = make_blueprint(skill="comparison", question_type="short-answer")
    value = MsemaxQuestion(
        stem="What is a catalyst?",
        answer="a substance that increases the rate of a reaction",
    )
    reason = validate_generation(value, blueprint)
    assert reason is not None
    assert "skill" in reason


def test_wrong_concept_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does pathway energy alternative lower rate reaction increase?",
        answer="an alternative pathway",
    )
    blueprint = make_blueprint(question_type="short-answer", concept="enzyme")
    reason = validate_generation(value, blueprint)
    assert reason is not None
    assert "concept" in reason


def test_duplicate_options_are_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does a catalyst increase the rate of a reaction?",
        options=[
            "By providing an alternative pathway",
            "By providing an alternative pathway",
            "By raising the activation energy",
            "By being consumed",
        ],
        correct_option=0,
    )
    reason = validate_generation(value, make_blueprint())
    assert reason == "duplicate options"


def test_wrong_option_count_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does a catalyst increase the rate of a reaction?",
        options=["By providing an alternative pathway", "By raising it"],
        correct_option=0,
    )
    reason = validate_generation(value, make_blueprint())
    assert reason is not None
    assert "4 options" in reason


def test_answer_length_giveaway_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="How does a catalyst increase the rate of a reaction?",
        options=[
            "By providing an alternative reaction pathway that has a lower "
            "activation energy for the reaction",
            "By rate",
            "By energy",
            "By pathway",
        ],
        correct_option=0,
    )
    reason = validate_generation(value, make_blueprint())
    assert reason == "answer length giveaway"


def test_verbatim_source_copy_is_rejected() -> None:
    value = MsemaxQuestion(stem=EVIDENCE, answer="an alternative pathway")
    reason = validate_generation(
        value, make_blueprint(question_type="short-answer")
    )
    assert reason is not None
    assert "verbatim" in reason


def test_meta_reference_is_rejected() -> None:
    value = MsemaxQuestion(
        stem="According to the document, how does a catalyst work?",
        answer="by providing an alternative pathway",
    )
    reason = validate_generation(
        value, make_blueprint(question_type="short-answer")
    )
    assert reason is not None
    assert "document" in reason


def test_empty_stem_is_a_structured_refusal_not_a_crash() -> None:
    """The model is told to decline rather than invent; declining is handled."""
    backend = Backend(MsemaxQuestion(stem="", options=[], correct_option=0))
    candidate, rejection = generate_candidate(make_blueprint(), backend=backend)

    assert candidate is None
    assert rejection is not None
    assert "empty stem" in rejection.reason


def test_true_false_must_offer_true_and_false() -> None:
    # Grounded wording, so the only fault under test is the option shape.
    value = MsemaxQuestion(
        stem="A catalyst increases the activation energy of a reaction.",
        options=["Yes", "No"],
        answer="False",
    )
    reason = validate_generation(
        value, make_blueprint(question_type="true-false", skill="misconception")
    )
    assert reason is not None
    assert "True and False" in reason


# --------------------------------------------------------------------------- #
# D. Provider-level failures
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("deadline exceeded"),
        RuntimeError("provider returned 503"),
        ValueError("response was not valid JSON"),
    ],
)
def test_provider_failures_become_structured_rejections(failure: Exception) -> None:
    backend = Backend(failure)
    candidate, rejection = generate_candidate(make_blueprint(), backend=backend)

    assert candidate is None
    assert rejection is not None
    assert rejection.reason.startswith("provider error")
    assert rejection.blueprint_id == "det-bp-1"


def test_malformed_output_shape_is_rejected() -> None:
    backend = Backend(object())
    candidate, rejection = generate_candidate(make_blueprint(), backend=backend)

    assert candidate is None
    assert rejection is not None
    assert "malformed output" in rejection.reason


# --------------------------------------------------------------------------- #
# E. Batch behaviour and accounting
# --------------------------------------------------------------------------- #


def test_every_failure_is_accounted_for_no_silent_loss() -> None:
    blueprints = [make_blueprint(), make_blueprint()]
    blueprints[1] = blueprints[1].__class__(**{**blueprints[1].__dict__, "id": "det-bp-2"})
    backend = Backend(RuntimeError("boom"))
    stats = MsemaxStats()

    written, rejections = msemax_candidates(blueprints, backend=backend, stats=stats)

    assert written == {}
    assert len(rejections) == len(blueprints)
    assert stats.requested == 2
    assert stats.generated == 0
    assert stats.rejected == 2
    assert stats.provider_errors == 2


# --------------------------------------------------------------------------- #
# F. Configuration: no credentials means an explicit error, never a fake
# --------------------------------------------------------------------------- #


class _Settings:
    def __init__(self, gemini: str = "", groq: str = "") -> None:
        self.gemini_api_key = gemini
        self.groq_api_key = groq


def test_enabling_msemax_without_credentials_raises_configuration_error() -> None:
    with pytest.raises(MsemaxConfigurationError) as excinfo:
        resolve_backend(_Settings(), service=object())

    assert "MSEMAX_ENABLED" in str(excinfo.value)


def test_backend_requires_a_structured_completion_service() -> None:
    with pytest.raises(MsemaxConfigurationError):
        resolve_backend(_Settings(gemini="key"), service=object())


def test_backend_resolves_when_configured() -> None:
    service = Backend(MsemaxQuestion(stem="x y z"))
    assert resolve_backend(_Settings(groq="key"), service=service) is service


# --------------------------------------------------------------------------- #
# G. The feature flag itself
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("off", False),
        # An empty or malformed value must degrade to "off", never crash the
        # process: MSEMAX_ENABLED="" is how shell scripts and CI commonly unset
        # a variable, and a boolean-typed field rejected it at import time.
        ("", False),
        ("garbage", False),
    ],
)
def test_msemax_flag_parsing_never_crashes(monkeypatch, raw: str, expected: bool) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("MSEMAX_ENABLED", raw)
    assert Settings().msemax_enabled is expected


def test_msemax_defaults_to_disabled(monkeypatch) -> None:
    """The deterministic engine stays the default, reproducible baseline."""
    from app.core.config import Settings

    monkeypatch.delenv("MSEMAX_ENABLED", raising=False)
    assert Settings().msemax_enabled is False


def test_configuration_error_maps_to_a_clear_503() -> None:
    """A misconfigured deployment gets an actionable error, not an opaque 500."""
    from app.api.ai import _as_http_exception

    exc = _as_http_exception(
        MsemaxConfigurationError("MSEMAX_ENABLED is true but no AI provider ...")
    )
    assert exc.status_code == 503
    assert "MSEMAX_ENABLED" in exc.detail
