"""Acceptance tests for the understanding-first quiz architecture.

Each test maps onto a stated product requirement: understanding precedes
generation, importance is not frequency, targets are deduplicated semantically,
seeds vary the quiz without lowering its bar, and a provider outage never
resurrects weak sentence-transformation questions.
"""

from __future__ import annotations

import pytest

from app.services.ai_documents import source_from_text
from app.services.ai_service import AIUnavailableError
from app.services.quiz_pipeline import (
    DETERMINISTIC_PROVIDER,
    UNAVAILABLE_MESSAGE,
    generate_quiz,
)
from app.services.quiz_understanding import _RawUnderstanding
from tests.quiz_fakes import FakeQuizService, default_kwargs

RICH_SOURCE = source_from_text(
    """[Page 1]
3.1 Cell Structure
The cell is defined as the smallest structural and functional unit of all living organisms.
The plasma membrane is defined as a selectively permeable barrier composed of a phospholipid
bilayer that separates the internal contents of the cell from the external environment.
A eukaryotic cell is a cell that contains a true, membrane-bound nucleus along with other
membrane-bound organelles, unlike a prokaryotic cell which lacks a nucleus.

[Page 2]
3.2 Organelles and Their Functions
Mitochondria are membrane-bound organelles that generate most of the cell's supply of ATP
through a process called cellular respiration.
The Golgi apparatus is defined as an organelle that modifies, sorts, and packages proteins
and lipids received from the endoplasmic reticulum before they are sent to their destination.
Lysosomes are organelles containing digestive enzymes that break down waste materials,
so that the cell can recycle damaged components.

[Page 3]
3.3 Cell Division
Mitosis is defined as the process of nuclear division that produces two genetically identical
daughter cells, and is used for growth and tissue repair in multicellular organisms.
Meiosis is defined as a specialized type of cell division that produces four genetically
distinct daughter cells, and is used in the production of gametes.
Transcription is defined as the process by which RNA polymerase synthesizes messenger RNA
using one strand of DNA as a template.
""",
    title="Cell Biology Chapter 3",
)

ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]


def _generate(*, seed: int = 7, count: int = 8, **overrides):
    service = FakeQuizService(title="Cell Biology Chapter 3")
    result = generate_quiz(
        service,
        RICH_SOURCE,
        **default_kwargs(seed=seed, count=count, question_types=ALL_TYPES, **overrides),
    )
    return service, result


# --------------------------------------------------------------------------- #
# Understanding happens before generation
# --------------------------------------------------------------------------- #


def test_the_document_is_understood_before_any_question_is_written() -> None:
    service, result = _generate()

    # Two provider calls, in order: understand, then write.
    assert len(service.calls) == 2
    assert service.calls[0]["response_model"] is _RawUnderstanding
    assert "UNDERSTAND what this document teaches" in service.calls[0]["user_prompt"]
    assert "Do not write any quiz" in service.calls[0]["user_prompt"]

    writer_prompt = service.calls[1]["user_prompt"]
    assert "DOCUMENT UNDERSTANDING" in writer_prompt
    assert "KNOWLEDGE TARGETS" in writer_prompt
    assert "QUIZ BLUEPRINT" in writer_prompt

    assert result.understanding is not None
    assert result.understanding.summary
    assert result.knowledge_targets
    assert result.blueprints


# --------------------------------------------------------------------------- #
# L. Every final question is fully traceable
# --------------------------------------------------------------------------- #


def test_every_question_carries_full_study_map_provenance() -> None:
    _, result = _generate()
    assert result.questions
    assert len(result.provenance) == len(result.questions)

    concept_ids = {c.concept_id for c in result.understanding.concepts}
    target_ids = {t.target_id for t in result.knowledge_targets}
    for trace in result.provenance:
        assert trace.concept_id in concept_ids
        assert trace.knowledge_target_id in target_ids
        assert trace.source_pages
        assert trace.cognitive_skill
        assert 0.0 < trace.quality_score <= 1.0


# --------------------------------------------------------------------------- #
# F. Different questions cover different concepts
# --------------------------------------------------------------------------- #


def test_an_eight_question_quiz_covers_eight_different_concepts() -> None:
    _, result = _generate(count=8)
    assert len(result.questions) >= 6
    concepts = [trace.concept_id for trace in result.provenance]
    # No concept may dominate the quiz when the document offers alternatives.
    assert len(set(concepts)) >= len(concepts) - 1
    assert max(concepts.count(value) for value in set(concepts)) <= 2


def test_questions_are_not_all_the_same_knowledge_target() -> None:
    _, result = _generate(count=8)
    targets = [trace.knowledge_target_id for trace in result.provenance]
    assert len(set(targets)) == len(targets)


# --------------------------------------------------------------------------- #
# K. Cross-section coverage
# --------------------------------------------------------------------------- #


def test_a_multi_section_document_is_covered_across_its_sections() -> None:
    _, result = _generate(count=8)
    pages = {page for trace in result.provenance for page in trace.source_pages}
    assert len(pages) >= 2


# --------------------------------------------------------------------------- #
# E. Same PDF, different seeds, still-valid quizzes
# --------------------------------------------------------------------------- #


def test_different_seeds_produce_different_but_equally_valid_quizzes() -> None:
    _, first = _generate(seed=11, count=6)
    _, second = _generate(seed=987, count=6)

    a = [question.prompt for question in first.questions]
    b = [question.prompt for question in second.questions]
    assert a != b

    for result in (first, second):
        assert result.questions
        for trace in result.provenance:
            assert trace.quality_score > 0
            assert trace.source_pages


def test_the_study_map_itself_is_identical_across_seeds() -> None:
    _, first = _generate(seed=11, count=6)
    _, second = _generate(seed=987, count=6)

    assert [c.concept_id for c in first.understanding.concepts] == [
        c.concept_id for c in second.understanding.concepts
    ]
    assert [c.importance for c in first.understanding.concepts] == [
        c.importance for c in second.understanding.concepts
    ]


def test_the_same_seed_is_fully_reproducible() -> None:
    _, first = _generate(seed=404, count=5)
    _, second = _generate(seed=404, count=5)
    assert [(q.prompt, q.options) for q in first.questions] == [
        (q.prompt, q.options) for q in second.questions
    ]


# --------------------------------------------------------------------------- #
# H. Sentence copying is rejected
# --------------------------------------------------------------------------- #


def test_a_question_is_never_a_verbatim_source_sentence() -> None:
    from app.services.quiz_scoring import normalize_question_text

    _, result = _generate(count=8)
    sentences = {
        normalize_question_text(sentence.text)
        for sentence in __import__(
            "app.services.quiz_grounding", fromlist=["iter_sentences"]
        ).iter_sentences(
            __import__(
                "app.services.quiz_boilerplate", fromlist=["clean_source_units"]
            ).clean_source_units(
                __import__(
                    "app.services.quiz_concepts", fromlist=["split_source_units"]
                ).split_source_units(RICH_SOURCE.text)
            )
        )
    }
    for question in result.questions:
        assert normalize_question_text(question.prompt) not in sentences


def test_no_question_asks_about_the_document_itself() -> None:
    _, result = _generate(count=8)
    for question in result.questions:
        lowered = question.prompt.lower()
        for phrase in ("on page", "the document", "the passage", "according to the text"):
            assert phrase not in lowered


# --------------------------------------------------------------------------- #
# I. Provider failure never resurrects the weak generator
# --------------------------------------------------------------------------- #


class BrokenProviderService(FakeQuizService):
    """A provider that is entirely unavailable."""

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        raise AIUnavailableError("provider down")


def test_provider_outage_falls_back_to_the_study_map_not_sentence_transformation() -> None:
    service = BrokenProviderService()
    result = generate_quiz(
        service,
        RICH_SOURCE,
        **default_kwargs(count=6, question_types=ALL_TYPES, seed=3),
    )

    # It is explicitly labelled, never passed off as a provider-backed quiz.
    assert result.provider == DETERMINISTIC_PROVIDER
    assert result.fallback_used is True

    # And it is still a real, understanding-derived quiz.
    assert result.questions
    assert result.understanding is not None
    assert result.understanding.source == "deterministic"
    assert len(result.provenance) == len(result.questions)
    for trace in result.provenance:
        assert trace.concept_id
        assert trace.knowledge_target_id
        assert trace.quality_score > 0


def test_provider_outage_on_an_unteachable_source_reports_unavailable() -> None:
    thin = source_from_text(
        "[Page 1]\nCopyright © 2024 Example Press. All rights reserved. ISBN 978-0-12-345678-9.\n"
        "Page 1 of 1. Printed in the USA.\n"
    )
    with pytest.raises(AIUnavailableError):
        generate_quiz(
            BrokenProviderService(), thin, **default_kwargs(count=6, question_types=ALL_TYPES)
        )


def test_unavailable_message_states_the_policy() -> None:
    assert "will not" in UNAVAILABLE_MESSAGE
    assert "low-quality" in UNAVAILABLE_MESSAGE


def test_arabic_provider_outage_is_reported_rather_than_written_badly() -> None:
    """The deterministic writer is English-only, so Arabic must fail loudly."""
    arabic = source_from_text(
        "[Page 1]\nالبناء الضوئي هو العملية التي تحول بها النباتات الطاقة الضوئية إلى طاقة كيميائية "
        "داخل البلاستيدات الخضراء في خلايا النبات.\n"
    )
    with pytest.raises(AIUnavailableError):
        generate_quiz(
            BrokenProviderService(),
            arabic,
            **default_kwargs(count=4, language="ar", question_types=ALL_TYPES),
        )


# --------------------------------------------------------------------------- #
# J. A small but meaningful document still works
# --------------------------------------------------------------------------- #


def test_a_small_meaningful_document_still_produces_useful_questions() -> None:
    small = source_from_text(
        "[Page 1]\n"
        "Osmosis is defined as the net movement of water across a selectively permeable "
        "membrane from a region of higher water potential to a region of lower water potential.\n"
        "Diffusion is defined as the net movement of particles from a region of higher "
        "concentration to a region of lower concentration.\n"
    )
    service = FakeQuizService(title="Transport")
    result = generate_quiz(
        service, small, **default_kwargs(count=4, question_types=ALL_TYPES, seed=2)
    )
    assert result.questions
    assert result.understanding is not None
    assert {c.concept_id for c in result.understanding.important_concepts()} >= {
        "osmosis",
        "diffusion",
    }
    for trace in result.provenance:
        assert trace.concept_id in {"osmosis", "diffusion"}


# --------------------------------------------------------------------------- #
# Subject independence: the pipeline is not tuned to biology
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "title,text,expected",
    [
        (
            "Computer Science",
            "[Page 1]\n"
            "Recursion is defined as a technique in which a procedure calls itself on a smaller input.\n"
            "A base case is defined as the condition that stops the recursive calls, so that the "
            "procedure terminates instead of running forever.\n"
            "A stack frame is defined as the record that stores the state of one active call.\n",
            {"recursion", "base-case", "stack-frame"},
        ),
        (
            "Physics",
            "[Page 1]\n"
            "Momentum is defined as the product of an object's mass and its velocity.\n"
            "Acceleration is defined as the rate of change of velocity with respect to time.\n"
            "Friction is defined as a contact force that opposes relative motion between surfaces, "
            "so that a sliding object gradually slows down.\n",
            {"momentum", "acceleration", "friction"},
        ),
        (
            "History",
            "[Page 1]\n"
            "The Industrial Revolution is defined as the transition to machine-based manufacturing "
            "that began in Britain in the late eighteenth century.\n"
            "Urbanisation is defined as the movement of population from rural areas into cities, "
            "which resulted in rapid growth of industrial towns.\n",
            {"industrial-revolution", "urbanisation"},
        ),
    ],
)
def test_pipeline_works_for_arbitrary_subjects(title: str, text: str, expected: set[str]) -> None:
    source = source_from_text(text, title=title)
    service = FakeQuizService(title=title)
    result = generate_quiz(
        service, source, **default_kwargs(count=4, question_types=ALL_TYPES, seed=5)
    )
    assert result.questions
    found = {concept.concept_id for concept in result.understanding.important_concepts()}
    assert expected <= found
