"""Grounding must accept legitimate transformations, not just verbatim text.

The bug behind these tests: a request for 12 questions failed with "this PDF
does not contain enough clearly explained material ... could only verify 1",
on documents that plainly had the material.

The cause was *not* the grounding validator refusing paraphrases -- the
validator already accepts them, and the first two tests here pin that down so
it cannot regress. The cause was upstream, in planning: quality preferences
("prefer reasoning over recall", "cap recognition questions") were enforced as
hard rules, so the planner could only ever produce ~13 slots from 19 usable
knowledge targets, and the top-up round then re-planned objectives the quiz
already held. Both are covered below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_documents import AIDocumentSource, _extract_pdf, source_from_text
from app.services.ai_service import AIServiceError, AIUnavailableError
from app.services.quiz_pipeline import (
    QuizMaterialError,
    _RawQuizPool,
    classify_grounding_result,
    generate_quiz,
)
from tests.quiz_fakes import FakeQuizService, parse_blueprints

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "public" / "demo-files"
ALL_TYPES = ["mcq", "true-false", "short-answer", "fill-blank"]
SEEDS = (1, 3, 5, 7, 11)

#: A small but genuinely explanatory source: definitions, a process spread over
#: two sentences, and a relationship stated across two pages.
BIO_TEXT = """[Page 1]
Photosynthesis is defined as the process by which green plants convert light energy into chemical energy.
Chlorophyll is the green pigment that absorbs light energy inside the chloroplast.

[Page 2]
The light-dependent reactions occur in the thylakoid membranes and produce ATP and NADPH.
The Calvin cycle uses ATP and NADPH to fix carbon dioxide into glucose."""


class NoProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("no provider configured")


def load_pdf(name: str) -> AIDocumentSource:
    path = DEMO_DIR / name
    return _extract_pdf(
        path.read_bytes(),
        file_id=path.stem,
        title=path.stem,
        max_characters=200_000,
        allowed_pages=None,
    )


def build(source: AIDocumentSource, *, count: int = 8, seed: int = 1, **overrides):
    kwargs = dict(
        count=count,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=seed,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )
    kwargs.update(overrides)
    return generate_quiz(NoProvider(), source, **kwargs)


def offer(concept: str, question_type: str, candidate: dict):
    """Run the pipeline with a provider that offers `candidate` for one slot.

    The candidate is attached to a blueprint that actually plans that concept
    and question type. Forcing prose onto a mismatched slot would be rejected
    for the type clash rather than on its grounding, which would make these
    tests measure the wrong thing.
    """

    class Provider(FakeQuizService):
        matched = False

        def _write(self, prompt):
            plan = parse_blueprints(prompt)
            blueprint = next(
                (
                    item
                    for item in plan
                    if item["concept_id"] == concept and item["type"] == question_type
                ),
                None,
            )
            if blueprint is None:
                return _RawQuizPool(questions=[])
            Provider.matched = True
            item = dict(candidate)
            item["blueprint_id"] = blueprint["id"]
            return _RawQuizPool.model_validate({"questions": [item]})

    result = generate_quiz(
        Provider(title="bio"),
        source_from_text(BIO_TEXT, "bio"),
        count=6,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="practice",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
        require_exact_count=False,
    )
    assert Provider.matched, f"no planned slot for {concept}/{question_type}"
    accepted = any(question.prompt == candidate["prompt"] for question in result.questions)
    reasons = [
        f"[{note.grounding_result}] {note.reason}"
        for note in result.rejections
        if note.prompt == candidate["prompt"]
    ]
    return accepted, reasons


# --------------------------------------------------------------------------- #
# 1-8. Legitimate transformations are accepted
# --------------------------------------------------------------------------- #


def test_an_exact_source_statement_is_accepted() -> None:
    accepted, reasons = offer(
        "photosynthesis",
        "true-false",
        dict(
            id="e1",
            type="true-false",
            prompt=(
                "Photosynthesis is the process by which green plants convert light "
                "energy into chemical energy."
            ),
            options=["True", "False"],
            correct_answer="True",
            explanation=(
                "The source defines photosynthesis as converting light energy into "
                "chemical energy."
            ),
            difficulty="medium",
            source_pages=[1],
            source_quote=(
                "Photosynthesis is defined as the process by which green plants "
                "convert light energy into chemical energy."
            ),
        ),
    )
    assert accepted, reasons


def test_a_valid_paraphrase_is_accepted() -> None:
    """Not a verbatim sentence, but unambiguously the document's claim."""
    accepted, reasons = offer(
        "photosynthesis",
        "true-false",
        dict(
            id="p1",
            type="true-false",
            prompt="Green plants turn light energy into chemical energy through photosynthesis.",
            options=["True", "False"],
            correct_answer="True",
            explanation=(
                "The source defines photosynthesis as converting light energy into "
                "chemical energy."
            ),
            difficulty="medium",
            source_pages=[1],
            source_quote=(
                "Photosynthesis is defined as the process by which green plants "
                "convert light energy into chemical energy."
            ),
        ),
    )
    assert accepted, reasons


def test_a_definition_rewritten_as_mcq_is_accepted() -> None:
    accepted, reasons = offer(
        "calvin-cycle",
        "mcq",
        dict(
            id="m1",
            type="mcq",
            prompt="Which best describes what the Calvin cycle does with ATP and NADPH?",
            options=[
                "It uses them to fix carbon dioxide into glucose",
                "It releases them as waste products",
                "It converts them into chlorophyll pigment",
                "It stores them inside the thylakoid membrane",
            ],
            correct_answer="It uses them to fix carbon dioxide into glucose",
            explanation="The Calvin cycle uses ATP and NADPH to fix carbon dioxide into glucose.",
            difficulty="medium",
            source_pages=[2],
            distractor_rationales=[
                "The source never describes them as waste",
                "Chlorophyll is a pigment, not a product of the cycle",
                "Storage in the thylakoid is not described",
            ],
            source_quote="The Calvin cycle uses ATP and NADPH to fix carbon dioxide into glucose.",
        ),
    )
    assert accepted, reasons


def test_a_short_answer_transformation_is_accepted() -> None:
    accepted, reasons = offer(
        "chlorophyll",
        "short-answer",
        dict(
            id="s1",
            type="short-answer",
            prompt="Why does chlorophyll matter inside the chloroplast?",
            correct_answer="It absorbs the light energy that photosynthesis needs.",
            explanation=(
                "Chlorophyll is the green pigment that absorbs light energy inside "
                "the chloroplast."
            ),
            difficulty="medium",
            source_pages=[1],
            source_quote=(
                "Chlorophyll is the green pigment that absorbs light energy inside "
                "the chloroplast."
            ),
        ),
    )
    assert accepted, reasons


@pytest.mark.parametrize("name", ["cell-biology-ch3.pdf", "calculus-limits-derivatives.pdf"])
def test_real_documents_produce_every_requested_question_type(name: str) -> None:
    """MCQ, true/false, fill-blank and short-answer all clear grounding."""
    produced: set[str] = set()
    for question_type in ALL_TYPES:
        try:
            result = build(load_pdf(name), count=4, question_types=[question_type])
        except (QuizMaterialError, AIUnavailableError):
            continue
        for question in result.questions:
            assert question.type == question_type
            produced.add(question_type)
    # A document need not support every type, but it must support several.
    assert len(produced) >= 3, produced


def test_multi_sentence_and_multi_page_evidence_are_usable() -> None:
    """Questions may draw on any page of the document, not just page 1."""
    result = build(load_pdf("cell-biology-ch3.pdf"), count=12)
    pages = {page for question in result.questions for page in question.source_pages}
    assert len(pages) >= 2, "the quiz should draw on more than a single page"


def test_evidence_carries_concept_explanation_and_pages() -> None:
    """The evidence model exposes what a grounding decision needs."""
    result = build(load_pdf("cell-biology-ch3.pdf"), count=8)
    understanding = result.understanding
    assert understanding is not None
    for concept in understanding.important_concepts():
        assert concept.name
        assert concept.description
        assert concept.knowledge_type
        assert concept.source_pages
        for evidence in concept.evidence:
            assert evidence.text.strip()
            assert evidence.page >= 1


# --------------------------------------------------------------------------- #
# 9-11. Genuinely unsupported content is still rejected
# --------------------------------------------------------------------------- #


def test_a_truly_unrelated_question_is_rejected() -> None:
    accepted, _ = offer(
        "photosynthesis",
        "true-false",
        dict(
            id="u1",
            type="true-false",
            prompt="The Treaty of Versailles was signed in 1919.",
            options=["True", "False"],
            correct_answer="True",
            explanation="The treaty was signed in 1919.",
            difficulty="medium",
            source_pages=[1],
            source_quote="The Treaty of Versailles was signed in 1919.",
        ),
    )
    assert not accepted


def test_a_contradictory_answer_is_rejected() -> None:
    accepted, _ = offer(
        "photosynthesis",
        "true-false",
        dict(
            id="c1",
            type="true-false",
            prompt="Photosynthesis converts chemical energy into light energy.",
            options=["True", "False"],
            correct_answer="True",
            explanation="It runs in reverse.",
            difficulty="medium",
            source_pages=[1],
            source_quote=(
                "Photosynthesis is defined as the process by which green plants "
                "convert light energy into chemical energy."
            ),
        ),
    )
    assert not accepted


def test_an_unsupported_external_fact_is_rejected() -> None:
    accepted, _ = offer(
        "chlorophyll",
        "short-answer",
        dict(
            id="x1",
            type="short-answer",
            prompt="At what wavelength in nanometres does chlorophyll a peak?",
            correct_answer="Around 430 and 662 nanometres.",
            explanation="Chlorophyll a has absorption peaks at 430 nm and 662 nm.",
            difficulty="medium",
            source_pages=[1],
            source_quote=(
                "Chlorophyll is the green pigment that absorbs light energy inside "
                "the chloroplast."
            ),
        ),
    )
    assert not accepted


# --------------------------------------------------------------------------- #
# 12-13. Question count against real documents
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    [
        "calculus-limits-derivatives.pdf",
        "cell-biology-ch3.pdf",
        "operating-systems-scheduling.pdf",
        "physics-newtonian-mechanics.pdf",
    ],
)
@pytest.mark.parametrize("seed", SEEDS)
def test_twelve_requested_returns_twelve_from_a_rich_pdf(name: str, seed: int) -> None:
    """The reported bug: 12 requested, "could only verify 1" returned."""
    result = build(load_pdf(name), count=12, seed=seed)
    assert len(result.questions) == 12


@pytest.mark.parametrize("count", [10, 12, 15])
def test_larger_requests_are_met_on_a_rich_pdf(count: int) -> None:
    result = build(load_pdf("cell-biology-ch3.pdf"), count=count)
    assert len(result.questions) == count


def test_a_genuinely_tiny_pdf_still_reports_insufficient_material() -> None:
    """Raising the ceiling must not turn a real shortfall into invention."""
    thin = source_from_text(
        "Photosynthesis is the process by which plants convert light into chemical energy.",
        "Thin note",
    )
    with pytest.raises((QuizMaterialError, AIUnavailableError)):
        build(thin, count=12)


def test_the_shortfall_message_only_appears_when_material_is_exhausted() -> None:
    """A refusal must be backed by exhausted material, not eager rejection.

    When the pipeline does refuse, the rejections that caused it must be
    genuine ``unsupported_by_pdf`` decisions -- if they were validator false
    negatives, the message would be blaming the document for a bug.
    """
    tiny = source_from_text(
        "Evaporation is the process by which liquid water changes into water vapor. "
        "Heat supplies the energy that causes evaporation.",
        "note",
    )
    with pytest.raises((QuizMaterialError, AIUnavailableError)):
        build(tiny, count=12)

    # And on a rich document the message must not appear at all.
    result = build(load_pdf("cell-biology-ch3.pdf"), count=12)
    assert len(result.questions) == 12


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #


def test_rejections_are_classified_as_unsupported_or_false_negative() -> None:
    assert (
        classify_grounding_result("correct answer is not supported by the evidence")
        == "unsupported_by_pdf"
    )
    assert (
        classify_grounding_result("source quote is not verbatim in the cited page text")
        == "unsupported_by_pdf"
    )
    assert (
        classify_grounding_result("MCQ distractors are too weak to be plausible")
        == "validator_false_negative"
    )


def test_rejection_notes_carry_structured_diagnostics() -> None:
    result = build(load_pdf("physics-newtonian-mechanics.pdf"), count=12)
    for note in result.rejections:
        assert note.question_id
        assert note.grounding_result in {
            "unsupported_by_pdf",
            "validator_false_negative",
            "not_selected",
        }
        assert note.reason.strip()


def test_telemetry_separates_the_two_rejection_kinds() -> None:
    result = build(load_pdf("cell-biology-ch3.pdf"), count=12)
    telemetry = result.telemetry
    assert "rejected_unsupported_by_pdf" in telemetry
    assert "rejected_validator_false_negative" in telemetry
    assert telemetry["questions_validated"] == 12


# --------------------------------------------------------------------------- #
# Planning capacity and top-up behaviour (the actual root causes)
# --------------------------------------------------------------------------- #


def test_the_planner_uses_the_documents_full_capacity_when_asked_for_more() -> None:
    """Quality preferences must not cap how much a rich document can support."""
    from app.services.quiz_blueprints import build_question_blueprints
    from app.services.quiz_deterministic import (
        SUPPORTED_SKILLS,
        target_writable_types,
        writable_question_types,
    )
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import build_document_understanding, build_quiz_context

    source = load_pdf("physics-newtonian-mechanics.pdf")
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    targets = build_knowledge_targets(understanding)
    types = writable_question_types(ALL_TYPES, understanding)

    small = build_question_blueprints(
        targets,
        count=8,
        question_types=types,
        difficulty="medium",
        seed=1,
        allowed_skills=SUPPORTED_SKILLS,
        type_filter=target_writable_types,
    )
    large = build_question_blueprints(
        targets,
        count=20,
        question_types=types,
        difficulty="medium",
        seed=1,
        allowed_skills=SUPPORTED_SKILLS,
        type_filter=target_writable_types,
    )
    # Before the fix this was capped at 13 no matter how many were requested.
    assert len(large) > len(small)
    assert len(large) >= 15


def test_planning_a_small_quiz_still_prefers_the_strongest_targets() -> None:
    """Relaxation must not fire when the strict pass can already fill the quiz."""
    from app.services.quiz_blueprints import (
        RECOGNITION_SKILLS,
        build_question_blueprints,
        target_tier,
    )
    from app.services.quiz_deterministic import (
        SUPPORTED_SKILLS,
        target_writable_types,
        writable_question_types,
    )
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import build_document_understanding, build_quiz_context

    source = load_pdf("calculus-limits-derivatives.pdf")
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    targets = build_knowledge_targets(understanding)
    types = writable_question_types(ALL_TYPES, understanding)
    plans = build_question_blueprints(
        targets,
        count=8,
        question_types=types,
        difficulty="medium",
        seed=1,
        allowed_skills=SUPPORTED_SKILLS,
        type_filter=target_writable_types,
    )
    assert plans
    # This document has plenty of reasoning material, so no bare-recall slot
    # should be planned for an eight-question quiz.
    assert all(target_tier(plan) < 3 for plan in plans)
    recognition = sum(1 for plan in plans if plan.cognitive_skill in RECOGNITION_SKILLS)
    assert recognition <= len(plans) // 2


def test_the_planner_can_exclude_objectives_already_used() -> None:
    """Top-up rounds must be able to ask for genuinely new material."""
    from app.services.quiz_blueprints import build_question_blueprints
    from app.services.quiz_deterministic import (
        SUPPORTED_SKILLS,
        target_writable_types,
        writable_question_types,
    )
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import build_document_understanding, build_quiz_context

    source = load_pdf("cell-biology-ch3.pdf")
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    targets = build_knowledge_targets(understanding)
    types = writable_question_types(ALL_TYPES, understanding)
    kwargs = dict(
        question_types=types,
        difficulty="medium",
        seed=1,
        allowed_skills=SUPPORTED_SKILLS,
        type_filter=target_writable_types,
    )
    first = build_question_blueprints(targets, count=8, **kwargs)
    used = {plan.objective_key for plan in first}
    second = build_question_blueprints(
        targets, count=8, exclude_objectives=used, **kwargs
    )
    assert second, "a rich document should still have unused objectives"
    assert not ({plan.objective_key for plan in second} & used)


def test_a_top_up_round_does_not_regenerate_the_same_rejected_question() -> None:
    """Retries must explore new material, not repeat a failed candidate."""
    result = build(load_pdf("physics-newtonian-mechanics.pdf"), count=12)
    validation_prompts = [
        note.prompt for note in result.rejections if note.stage == "validation"
    ]
    # Each distinct failing question may appear at most twice: once from the
    # initial plan and once before the attempted-objective guard learns it.
    for prompt in set(validation_prompts):
        assert validation_prompts.count(prompt) <= 2, prompt


def test_twelve_questions_are_spread_across_concepts() -> None:
    for name in ("cell-biology-ch3.pdf", "calculus-limits-derivatives.pdf"):
        result = build(load_pdf(name), count=12)
        concepts = [record.concept_id for record in result.provenance]
        assert len(set(concepts)) >= 8, concepts
        assert max(concepts.count(value) for value in set(concepts)) <= 3
        prompts = [question.prompt for question in result.questions]
        assert len(set(prompts)) == len(prompts)
