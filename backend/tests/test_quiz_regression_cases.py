"""Explicit regression cases from the adversarial review (§15).

Each test pins a defect that was observed in real generated output. They are
written against the *behaviour* (a wrong question must not be produced), not
against a blacklist of wordings, so a future refactor that reintroduces the
underlying cause fails here rather than shipping.
"""

from __future__ import annotations

import re

from app.services.quiz_deterministic import (
    _DANGLING_TAIL,
    _claim,
    _effect_clause,
    _shorten,
)
from app.services.quiz_understanding import (
    _clean_clause,
    _other_subject_intervenes,
    _mention_end,
    extract_facets,
)
from app.services.quiz_grounding import SourceSentence


def _sentence(text: str, page: int = 1) -> SourceSentence:
    return SourceSentence(text=text, page=page, order=0, section="")


# --------------------------------------------------------------------------- #
# Semantic ownership
# --------------------------------------------------------------------------- #


def test_summary_sentence_does_not_credit_another_subjects_claim() -> None:
    """"a limit describes X, continuity requires Y" must not give Y to limit.

    The facet pattern for a condition fires on "requires", which is the *new*
    subject's verb, so a guard window ending at the match start stopped one
    word short and attributed continuity's claim to the limit.
    """
    text = (
        "In summary, a limit describes the value a function approaches near a "
        "point, continuity requires that a function have no gaps or jumps, and "
        "the derivative measures the instantaneous rate of change of a function."
    )
    facets = extract_facets("limit", [_sentence(text)])
    for facet in facets:
        assert "gaps or jumps" not in facet.clause, (
            f"continuity's requirement was credited to 'limit': {facet.clause!r}"
        )


def test_contrast_clause_is_not_absorbed_into_a_purpose_answer() -> None:
    """Rough ER's purpose must not trail into the smooth ER's."""
    evidence = (
        "The rough endoplasmic reticulum is studded with ribosomes and is "
        "responsible for protein synthesis, while the smooth endoplasmic "
        "reticulum lacks ribosomes and is responsible for lipid synthesis."
    )
    assert "smooth" not in _effect_clause(evidence)
    assert "smooth" not in _clean_clause(
        "protein synthesis, while the smooth endoplasmic reticulum lacks ribosomes"
    )


def test_claim_stops_at_a_switch_of_subject() -> None:
    evidence = (
        "The rough endoplasmic reticulum is studded with ribosomes and is "
        "responsible for protein synthesis, while the smooth endoplasmic "
        "reticulum lacks ribosomes."
    )
    claim = _claim(evidence, "rough endoplasmic reticulum")
    assert claim
    assert "smooth" not in claim


# --------------------------------------------------------------------------- #
# Answer completeness
# --------------------------------------------------------------------------- #


def test_a_pronoun_object_may_end_a_clause() -> None:
    """"...without ever reaching it" is complete, not truncated.

    Treating a trailing "it" as a dangling function word discarded whole
    definitions, which silently removed the concept from the exam.
    """
    text = (
        "the value that a function f(x) approaches as the input x approaches "
        "some particular value, without necessarily ever reaching it"
    )
    assert not _DANGLING_TAIL.search(text)
    assert _shorten(text, 30) == text


def test_a_stranded_function_word_still_fails() -> None:
    for fragment in (
        "the total time taken from process submission to",
        "is equal to the mass of the object multiplied",
        "the process by which the operating system decides",
    ):
        assert not _shorten(fragment, 30), f"accepted a fragment: {fragment!r}"


def test_shorten_never_returns_a_mid_phrase_cut() -> None:
    """A budget cut must land on a real boundary or return nothing."""
    text = (
        "use the chain rule to relate the rates of change of two or more "
        "related quantities with respect to time"
    )
    result = _shorten(text, 12)
    assert result == "" or not re.search(
        r"\b(?:with|to|of|for|and|or|two|more)\s*$", result
    )
