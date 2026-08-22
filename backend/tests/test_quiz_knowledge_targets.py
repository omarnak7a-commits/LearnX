"""KNOWLEDGE TARGETS: questions come from targets, and only supported ones."""

from __future__ import annotations

from app.services.quiz_boilerplate import clean_source_units
from app.services.quiz_concepts import split_source_units
from app.services.quiz_knowledge_targets import (
    SKILL_QUESTION_TYPES,
    build_knowledge_targets,
    derive_targets_for_concept,
    targets_block,
)
from app.services.quiz_understanding import deterministic_understanding


def _understanding(text: str, title: str = "Doc"):
    return deterministic_understanding(
        clean_source_units(split_source_units(text)), title=title
    )


PROCESS_SOURCE = """[Page 1]
Mitosis is defined as the process of nuclear division that produces two genetically identical
daughter cells from a single parent cell, and is used for growth and tissue repair.
Mitosis proceeds through the phases prophase, metaphase, anaphase, and telophase.
Meiosis is defined as a specialized type of cell division that produces four genetically
distinct daughter cells, unlike mitosis which produces two identical cells.
"""


def test_targets_are_derived_per_concept_and_carry_grounded_evidence() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    targets = build_knowledge_targets(understanding)

    assert targets
    for target in targets:
        assert target.concept_id
        assert target.target_id
        assert target.statement
        assert target.evidence
        assert target.pages
        assert target.cognitive_skill in SKILL_QUESTION_TYPES


def test_every_concept_yields_at_least_an_understanding_target() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    for concept in understanding.important_concepts():
        skills = {
            target.cognitive_skill
            for target in derive_targets_for_concept(concept, understanding)
        }
        assert "understanding" in skills


def test_a_process_with_stated_stages_gains_a_sequence_target() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    mitosis = next(
        concept for concept in understanding.concepts if concept.concept_id == "mitosis"
    )
    skills = {
        target.cognitive_skill for target in derive_targets_for_concept(mitosis, understanding)
    }
    assert "process_order" in skills


def test_unsupported_target_types_are_never_invented() -> None:
    """A document with no comparison and no outcome yields neither target."""
    plain = """[Page 1]
An integer is defined as a whole number without a fractional component.
A rational number is defined as a number expressible as the ratio of two integers.
"""
    understanding = _understanding(plain, "Numbers")
    targets = build_knowledge_targets(understanding)
    skills = {target.cognitive_skill for target in targets}

    assert skills  # something is testable
    assert "comparison" not in skills  # nothing is contrasted
    assert "classification" not in skills  # no taxonomy is enumerated


def test_application_targets_require_a_stated_outcome_to_transfer() -> None:
    with_outcome = """[Page 1]
Lysosomes are organelles containing digestive enzymes that break down waste materials,
so that the cell can recycle damaged components and remain healthy.
"""
    without_outcome = """[Page 1]
A quaternion is defined as a number system that extends the complex numbers.
A scalar is defined as a quantity described by magnitude alone.
"""
    assert any(
        target.cognitive_skill == "application"
        for target in build_knowledge_targets(_understanding(with_outcome))
    )
    assert not any(
        target.cognitive_skill == "application"
        for target in build_knowledge_targets(_understanding(without_outcome))
    )


def test_target_identity_is_stable_and_deduplicable() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    targets = build_knowledge_targets(understanding)
    ids = [target.target_id for target in targets]
    assert len(ids) == len(set(ids))
    # The objective key ignores wording entirely.
    for target in targets:
        assert target.objective_key() == f"{target.concept_id}::{target.cognitive_skill}"


def test_targets_are_deterministic_and_importance_ordered() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    first = build_knowledge_targets(understanding)
    second = build_knowledge_targets(understanding)
    assert [t.target_id for t in first] == [t.target_id for t in second]
    importances = [t.importance for t in first]
    assert importances == sorted(importances, reverse=True)


def test_targets_block_renders_for_prompting() -> None:
    understanding = _understanding(PROCESS_SOURCE, "Cell division")
    block = targets_block(build_knowledge_targets(understanding))
    assert "skill=" in block
    assert "evidence=" in block
