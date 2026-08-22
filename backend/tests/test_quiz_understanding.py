"""DOCUMENT UNDERSTANDING: the study map must be built before any question.

These tests target the architectural requirement directly — that the system
comprehends what a PDF teaches, grounds every concept in real evidence, and
ranks concepts by educational importance rather than by repetition.
"""

from __future__ import annotations

from app.services.quiz_boilerplate import clean_source_units
from app.services.quiz_concepts import split_source_units
from app.services.quiz_grounding import is_heading_like, iter_sentences
from app.services.quiz_understanding import (
    IMPORTANCE_WEIGHTS,
    _RawUnderstanding,
    deterministic_understanding,
    normalize_understanding,
    understanding_block,
)


def units(text: str):
    return clean_source_units(split_source_units(text))


CELL_BIOLOGY = """[Page 1]
3.1 Introduction to Cell Structure
The cell is defined as the smallest structural and functional unit of all living organisms.
Cell theory states that all living things are composed of cells and all cells arise from pre-existing cells.
A eukaryotic cell is a cell that contains a true, membrane-bound nucleus along with other membrane-bound organelles.
In contrast, a prokaryotic cell is a cell that lacks a nucleus and membrane-bound organelles.

[Page 2]
3.2 Organelles
Mitochondria are membrane-bound organelles that generate most of the cell's supply of ATP through cellular respiration.
The Golgi apparatus is defined as an organelle that modifies, sorts, and packages proteins received from the endoplasmic reticulum.
Mitosis is defined as the process of nuclear division that produces two genetically identical daughter cells, and is used for growth and tissue repair.
"""


# --------------------------------------------------------------------------- #
# A. A cell-biology document is understood as cell biology
# --------------------------------------------------------------------------- #


def test_understanding_identifies_the_documents_real_subject_and_concepts() -> None:
    understanding = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")

    assert understanding.subject == "Biology"
    assert understanding.summary
    names = {concept.concept_id for concept in understanding.important_concepts()}
    # The map must contain the chapter's actual teaching targets.
    assert {"cell", "mitochondria", "golgi-apparatus", "mitosis"} <= names
    assert understanding.main_topics
    assert understanding.learning_objectives


def test_every_concept_is_grounded_in_verbatim_source_evidence() -> None:
    understanding = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")
    page_text = {unit.page: unit.text for unit in units(CELL_BIOLOGY)}

    for concept in understanding.concepts:
        assert concept.evidence, f"{concept.concept_id} has no evidence"
        for item in concept.evidence:
            assert item.text in page_text[item.page].replace("\n", " ") or item.text in page_text[item.page]


# --------------------------------------------------------------------------- #
# B. Pure boilerplate teaches nothing
# --------------------------------------------------------------------------- #


def test_pages_of_copyright_and_footers_produce_no_concepts() -> None:
    boilerplate = "\n\n".join(
        f"[Page {page}]\nCopyright © 2024, Example Press. All rights reserved.\n"
        f"ISBN 978-0-12-345678-9\nPage {page} of 5\nwww.example-press.com"
        for page in range(1, 6)
    )
    understanding = deterministic_understanding(units(boilerplate), title="Front matter")

    assert understanding.concepts == ()
    assert understanding.important_concepts() == []
    assert not understanding.is_usable


# --------------------------------------------------------------------------- #
# C. Frequency is not importance
# --------------------------------------------------------------------------- #


def test_a_frequently_repeated_unexplained_term_is_not_the_top_concept() -> None:
    repeated = """[Page 1]
The worksheet mentions the widget in the widget column of the widget table.
See the widget list, the widget index, the widget chart, and the widget summary.
The widget appears again in the widget appendix and the widget register.

[Page 2]
Osmosis is defined as the net movement of water across a selectively permeable membrane
from a region of higher water potential to a region of lower water potential, which allows
cells to regulate their internal water balance.
"""
    understanding = deterministic_understanding(units(repeated), title="Mixed note")
    ranked = understanding.important_concepts()

    assert ranked, "an explained concept should still be found"
    assert ranked[0].concept_id == "osmosis"

    widget = next((c for c in understanding.concepts if "widget" in c.concept_id), None)
    if widget is not None:
        # Repetition alone must never outrank an explained mechanism.
        assert widget.importance < ranked[0].importance
        assert widget.mention_count > ranked[0].mention_count


def test_importance_model_contains_no_frequency_term() -> None:
    """The weighting is the guarantee, so assert it explicitly."""
    assert set(IMPORTANCE_WEIGHTS) == {
        "knowledge_type_value",
        "explanatory_depth",
        "centrality",
        # How many distinct relational claims the document makes about the
        # concept (purpose, mechanism, cause, effect, contrast). Explaining how
        # something works is a teaching signal; repeating its name is not.
        "relational_richness",
        "teaching_emphasis",
        "prerequisite_role",
        "topic_spread",
    }
    assert abs(sum(IMPORTANCE_WEIGHTS.values()) - 1.0) < 1e-9
    assert not any("frequen" in name or "count" in name for name in IMPORTANCE_WEIGHTS)


# --------------------------------------------------------------------------- #
# G. Headings are not concepts and not evidence
# --------------------------------------------------------------------------- #


def test_headings_are_recognized_and_never_become_evidence() -> None:
    assert is_heading_like("3.2 The Nucleus and Genetic Material")
    assert is_heading_like("CHAPTER 4")
    assert is_heading_like("Organelles and Their Functions")
    assert not is_heading_like("The nucleus houses the cell's genetic material.")

    headings_only = """[Page 1]
3.1 Introduction to Cell Structure
3.2 The Nucleus and Genetic Material
3.3 Organelles and Their Functions
3.4 Protein Synthesis in Detail
"""
    understanding = deterministic_understanding(units(headings_only), title="Contents")
    assert understanding.important_concepts() == []


def test_a_heading_is_not_glued_onto_the_sentence_below_it() -> None:
    sentences = iter_sentences(units(CELL_BIOLOGY))
    texts = [sentence.text for sentence in sentences]
    assert any(text.startswith("The cell is defined as") for text in texts)
    assert not any(text.startswith("3.1 Introduction") for text in texts)
    # The heading survives as section context, not as content.
    assert any(sentence.section.startswith("3.1") for sentence in sentences)


# --------------------------------------------------------------------------- #
# K. Multi-section documents get cross-section coverage
# --------------------------------------------------------------------------- #


def test_multiple_sections_all_contribute_concepts() -> None:
    understanding = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")
    pages = {page for concept in understanding.important_concepts() for page in concept.source_pages}
    assert pages == {1, 2}


# --------------------------------------------------------------------------- #
# Provider proposals are verified, never trusted
# --------------------------------------------------------------------------- #


def test_provider_concepts_without_real_evidence_are_discarded() -> None:
    raw = _RawUnderstanding.model_validate(
        {
            "subject": "Biology",
            "summary": "A chapter about cells.",
            "concepts": [
                {
                    "id": "invented",
                    "name": "Quantum ribosome tunnelling",
                    "description": "Not in the document at all.",
                    "knowledge_type": "process",
                    "teaching_emphasis": "high",
                    "evidence_quotes": [
                        "Quantum ribosome tunnelling accelerates translation by a factor of nine."
                    ],
                    "source_pages": [1],
                },
                {
                    "id": "mitochondria",
                    "name": "Mitochondria",
                    "description": "Generate ATP.",
                    "knowledge_type": "process",
                    "teaching_emphasis": "high",
                    "evidence_quotes": [
                        "Mitochondria are membrane-bound organelles that generate most of the "
                        "cell's supply of ATP through cellular respiration."
                    ],
                    "source_pages": [2],
                },
            ],
        }
    )
    understanding = normalize_understanding(raw, units(CELL_BIOLOGY), title="Cell Biology")
    ids = {concept.concept_id for concept in understanding.concepts}
    assert "mitochondria" in ids
    assert "invented" not in ids


def test_provider_cannot_promote_boilerplate_or_layout_to_a_concept() -> None:
    source = """[Page 1]
Photosynthesis is defined as the process by which plants convert light energy into chemical energy.
This worked example appears in a blue box on the right side of the page.
"""
    raw = _RawUnderstanding.model_validate(
        {
            "subject": "Biology",
            "summary": "Photosynthesis.",
            "concepts": [
                {
                    "id": "blue-box",
                    "name": "Blue box",
                    "knowledge_type": "definition",
                    "teaching_emphasis": "high",
                    "evidence_quotes": [
                        "This worked example appears in a blue box on the right side of the page."
                    ],
                    "source_pages": [1],
                },
                {
                    "id": "photosynthesis",
                    "name": "Photosynthesis",
                    "knowledge_type": "definition",
                    "teaching_emphasis": "medium",
                    "evidence_quotes": [
                        "Photosynthesis is defined as the process by which plants convert "
                        "light energy into chemical energy."
                    ],
                    "source_pages": [1],
                },
            ],
        }
    )
    understanding = normalize_understanding(raw, units(source), title="Bio")
    ids = {concept.concept_id for concept in understanding.concepts}
    assert "photosynthesis" in ids
    assert "blue-box" not in ids


def test_a_summary_that_describes_nothing_taught_is_replaced() -> None:
    raw = _RawUnderstanding.model_validate(
        {
            "subject": "Biology",
            "summary": "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod.",
            "concepts": [
                {
                    "id": "mitochondria",
                    "name": "Mitochondria",
                    "knowledge_type": "process",
                    "teaching_emphasis": "high",
                    "evidence_quotes": [
                        "Mitochondria are membrane-bound organelles that generate most of the "
                        "cell's supply of ATP through cellular respiration."
                    ],
                    "source_pages": [2],
                }
            ],
        }
    )
    understanding = normalize_understanding(raw, units(CELL_BIOLOGY), title="Cell Biology")
    assert "Lorem ipsum" not in understanding.summary
    assert "Mitochondria" in understanding.summary


def test_study_map_is_deterministic_for_the_same_source() -> None:
    a = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")
    b = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")
    assert [c.concept_id for c in a.concepts] == [c.concept_id for c in b.concepts]
    assert [c.importance for c in a.concepts] == [c.importance for c in b.concepts]


def test_understanding_block_renders_the_map_for_downstream_prompts() -> None:
    understanding = deterministic_understanding(units(CELL_BIOLOGY), title="Cell Biology")
    block = understanding_block(understanding)
    assert "SUBJECT:" in block
    assert "SUMMARY:" in block
    assert "IMPORTANT CONCEPTS" in block
    assert "importance=" in block
