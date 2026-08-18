"""Regression tests for objective deduplication, scoring, and final diversity."""

import random

from app.schemas.ai import AIQuizQuestion
from app.services.quiz_pipeline import _dedupe_scored
from app.services.quiz_scoring import QUALITY_WEIGHTS, ScoredCandidate, select_diverse


def _question(identifier: str, prompt: str, *, page: int = 1) -> AIQuizQuestion:
    return AIQuizQuestion(
        id=identifier,
        type="short-answer",
        prompt=prompt,
        correct_answer="A source-grounded answer",
        explanation="The source directly supports this answer.",
        difficulty="medium",
        source_pages=[page],
    )


def _candidate(
    identifier: str,
    prompt: str,
    *,
    score: float,
    objective: str,
    concept: str = "recursion",
    # Deduplication is keyed on the knowledge-target *identity*, so tests pass
    # target ids exactly as the pipeline does.
    target: str = "recursion--understanding",
    skill: str = "understanding",
    category: str = "core_concept",
    page: int = 1,
) -> ScoredCandidate:
    return ScoredCandidate(
        question=_question(identifier, prompt, page=page),
        score=score,
        concept=concept,
        skill=skill,
        pattern=skill,
        objective_key=objective,
        blueprint_id=f"bp-{identifier}",
        category=category,
        knowledge_target=target,
    )


def test_required_quality_weights_are_exact_and_sum_to_one() -> None:
    assert QUALITY_WEIGHTS == {
        "educational_importance": 0.25,
        "source_grounding": 0.20,
        "conceptual_understanding": 0.15,
        "clarity": 0.10,
        "distractor_quality": 0.10,
        "cognitive_value": 0.10,
        "novelty": 0.05,
        "difficulty_match": 0.05,
    }
    assert sum(QUALITY_WEIGHTS.values()) == 1.0


def test_same_objective_paraphrases_collapse_to_highest_quality() -> None:
    candidates = [
        _candidate(
            "weak",
            "What does a recursion base case do?",
            score=0.72,
            objective="recursion::base case stops calls::understanding",
        ),
        _candidate(
            "strong",
            "How does the base case stop recursive calls?",
            score=0.94,
            objective="recursion::base case stops calls::understanding",
        ),
    ]

    kept = _dedupe_scored(candidates)
    assert [candidate.question.id for candidate in kept] == ["strong"]


def test_same_concept_requires_a_different_knowledge_target_to_recur() -> None:
    candidates = [
        _candidate(
            "base",
            "How does the base case stop recursive calls?",
            score=0.94,
            objective="recursion::base case stops calls::understanding",
        ),
        _candidate(
            "reduce",
            "How does the recursive case reduce the problem?",
            score=0.92,
            objective="recursion::recursive-case::understanding",
            concept="recursive-case",
            target="recursive-case--understanding",
        ),
        _candidate(
            "apply",
            "Suppose the base case is missing; predict what happens.",
            score=0.91,
            objective="recursion::base case stops calls::application",
            target="recursion--application",
            skill="application",
        ),
    ]

    kept = _dedupe_scored(candidates)
    # A concept may legitimately recur for a *different* knowledge target
    # (understanding vs. application), so all three survive deduplication.
    assert {candidate.question.id for candidate in kept} == {"base", "reduce", "apply"}

    # Selection, however, prefers breadth: with room for two questions it takes
    # the two different concepts rather than two views of the same one.
    selected = select_diverse(kept, 2, rng=random.Random(4))
    assert {question.id for question in selected} == {"base", "reduce"}


def test_identical_target_is_deduplicated_regardless_of_wording() -> None:
    candidates = [
        _candidate(
            "worded-a",
            "What is the function of the mitochondrion?",
            score=0.90,
            objective="mitochondria::mitochondria--understanding::understanding",
            concept="mitochondria",
            target="mitochondria--understanding",
        ),
        _candidate(
            "worded-b",
            "Which role does the mitochondrion perform in the cell?",
            score=0.86,
            objective="mitochondria::mitochondria--understanding::understanding",
            concept="mitochondria",
            target="mitochondria--understanding",
        ),
        _candidate(
            "worded-c",
            "Why are mitochondria important to a cell?",
            score=0.84,
            objective="mitochondria::mitochondria--understanding::understanding",
            concept="mitochondria",
            target="mitochondria--understanding",
        ),
    ]

    kept = _dedupe_scored(candidates)
    assert [candidate.question.id for candidate in kept] == ["worded-a"]


def test_selection_prefers_cognitive_diversity_from_an_already_valid_pool() -> None:
    candidates = [
        _candidate(
            str(index),
            f"Valid source-grounded {skill} question {index}",
            score=0.90,
            objective=f"concept-{index}::target-{index}::{skill}",
            concept=f"concept-{index}",
            target=f"target-{index}",
            skill=skill,
            category=category,
            page=index + 1,
        )
        for index, (skill, category) in enumerate(
            [
                ("understanding", "core_concept"),
                ("application", "formula_rule"),
                ("cause_effect", "cause_effect"),
                ("comparison", "comparison"),
                ("process_order", "process_mechanism"),
                ("understanding", "important_definition"),
            ]
        )
    ]
    skill_for_id = {candidate.question.id: candidate.skill for candidate in candidates}

    selected = select_diverse(candidates, 4, rng=random.Random(5))
    assert len(selected) == 4
    assert len({skill_for_id[question.id] for question in selected}) >= 3


def test_selection_seed_is_repeatable_and_only_varies_accepted_candidates() -> None:
    candidates = [
        _candidate(
            str(index),
            f"Accepted question {index} about concept {index}",
            score=0.88,
            objective=f"concept-{index}::target-{index}::understanding",
            concept=f"concept-{index}",
            target=f"target-{index}",
            page=index + 1,
        )
        for index in range(8)
    ]

    choose = lambda seed: [
        question.id for question in select_diverse(candidates, 4, rng=random.Random(seed))
    ]
    assert choose(101) == choose(101)
    assert choose(101) != choose(202)
    assert set(choose(101)).issubset({candidate.question.id for candidate in candidates})
    assert set(choose(202)).issubset({candidate.question.id for candidate in candidates})
