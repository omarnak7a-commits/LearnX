"""Regression tests for semantic source mapping and backend classification gates."""

from app.services.quiz_blueprints import build_question_blueprints
from app.services.quiz_content_map import (
    _RawContentMap,
    normalize_content_map,
)
from app.services.quiz_concepts import split_source_units


SOURCE = """--- Page 1 ---
Recursion solves a problem by calling the same procedure on a smaller input.
A base case stops the recursive calls, while a recursive case reduces the problem.
This worked example appears in a blue box on the right side of the page.
Copyright 2026 Example Learning Press. All rights reserved.
"""


def _raw_map() -> _RawContentMap:
    return _RawContentMap.model_validate(
        {
            "items": [
                {
                    "concept": "Base case",
                    "category": "core_concept",
                    "importance": "low",
                    "source_quote": "A base case stops the recursive calls, while a recursive case reduces the problem.",
                    "source_pages": [1],
                    "knowledge_targets": ["base case stops recursive calls"],
                },
                {
                    # Deliberately mislabeled/highly rated by the provider.  The
                    # backend must independently veto layout trivia.
                    "concept": "Blue box",
                    "category": "core_concept",
                    "importance": "high",
                    "source_quote": "This worked example appears in a blue box on the right side of the page.",
                    "source_pages": [1],
                    "knowledge_targets": ["blue box position"],
                },
                {
                    "concept": "Copyright notice",
                    "category": "metadata_boilerplate",
                    "importance": "high",
                    "source_quote": "Copyright 2026 Example Learning Press. All rights reserved.",
                    "source_pages": [1],
                    "knowledge_targets": ["copyright year 2026"],
                },
            ]
        }
    )


def test_category_first_importance_overrides_provider_ranking() -> None:
    items = normalize_content_map(_raw_map(), split_source_units(SOURCE))
    by_concept = {item.concept: item for item in items}

    assert by_concept["Base case"].importance > by_concept["Blue box"].importance
    assert by_concept["Base case"].importance >= 0.72
    assert by_concept["Blue box"].category == "minor_detail"
    assert by_concept["Blue box"].importance <= 0.22


def test_metadata_is_retained_only_as_an_explicit_exclusion() -> None:
    items = normalize_content_map(_raw_map(), split_source_units(SOURCE))
    copyright_item = next(item for item in items if item.concept == "Copyright notice")

    assert copyright_item.category == "metadata_boilerplate"
    assert copyright_item.importance == 0.0

    blueprints = build_question_blueprints(
        items,
        count=8,
        question_types=["mcq", "true-false", "fill-blank", "short-answer"],
        difficulty="medium",
        seed=9,
    )
    assert blueprints
    assert {blueprint.content_id for blueprint in blueprints} == {"content-1"}
    assert all(blueprint.category != "metadata_boilerplate" for blueprint in blueprints)


def test_provider_cannot_hide_boilerplate_under_a_content_label() -> None:
    raw = _RawContentMap.model_validate(
        {
            "items": [
                {
                    "concept": "Publisher",
                    "category": "core_concept",
                    "importance": "high",
                    "source_quote": "Copyright 2026 Example Learning Press. All rights reserved.",
                    "source_pages": [1],
                    "knowledge_targets": ["publisher name"],
                }
            ]
        }
    )
    assert normalize_content_map(raw, split_source_units(SOURCE)) == []


def test_knowledge_targets_must_be_substantially_grounded() -> None:
    raw = _RawContentMap.model_validate(
        {
            "items": [
                {
                    "concept": "Base case",
                    "category": "core_concept",
                    "importance": "high",
                    "source_quote": "A base case stops the recursive calls, while a recursive case reduces the problem.",
                    "source_pages": [1],
                    "knowledge_targets": [
                        "base case stops recursive calls",
                        "base case allows exactly 17 retries in production",
                    ],
                }
            ]
        }
    )
    item = normalize_content_map(raw, split_source_units(SOURCE))[0]

    assert "base case stops recursive calls" in item.knowledge_targets
    assert all("17" not in target for target in item.knowledge_targets)
    assert all("production" not in target for target in item.knowledge_targets)


def test_evidence_must_be_verbatim_and_on_an_allowed_page() -> None:
    raw = _RawContentMap.model_validate(
        {
            "items": [
                {
                    "concept": "Invented rule",
                    "category": "formula_rule",
                    "importance": "high",
                    "source_quote": "Every recursive algorithm runs in exactly three steps.",
                    "source_pages": [2],
                    "knowledge_targets": ["three recursive steps"],
                }
            ]
        }
    )
    assert normalize_content_map(raw, split_source_units(SOURCE)) == []
