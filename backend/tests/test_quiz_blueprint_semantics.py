"""Regression tests for teacher-style planning and semantic objectives."""

from app.services.quiz_blueprints import (
    build_question_blueprints,
    semantic_objective_key,
)
from app.services.quiz_content_map import ContentItem


def _item(
    item_id: str,
    concept: str,
    category: str,
    evidence: str,
    *,
    importance: float = 0.9,
    targets: tuple[str, ...] | None = None,
    page: int = 1,
) -> ContentItem:
    return ContentItem(
        id=item_id,
        concept=concept,
        category=category,
        importance=importance,
        evidence=evidence,
        pages=(page,),
        knowledge_targets=targets or (evidence,),
    )


ITEMS = [
    _item("c1", "Cell membrane", "core_concept", "The cell membrane controls movement into and out of the cell."),
    _item("c2", "Mitosis", "process_mechanism", "Mitosis separates copied chromosomes into two nuclei.", page=2),
    _item("c3", "Temperature", "cause_effect", "Higher temperature increases reaction rate until enzymes denature.", page=3),
    _item("c4", "Plant and animal cells", "comparison", "Plant cells have cell walls, whereas animal cells do not.", page=4),
    _item("c5", "Density", "formula_rule", "Density equals mass divided by volume.", page=5),
]


def test_plans_cognitively_diverse_objectives_before_wording() -> None:
    blueprints = build_question_blueprints(
        ITEMS,
        count=6,
        question_types=["mcq", "true-false", "fill-blank", "short-answer"],
        difficulty="medium",
        seed=42,
    )

    assert len(blueprints) >= 6
    assert len({blueprint.cognitive_skill for blueprint in blueprints}) >= 3
    assert len({blueprint.content_id for blueprint in blueprints}) >= 3
    assert len({blueprint.objective_key for blueprint in blueprints}) == len(blueprints)


def test_question_types_are_matched_to_supported_content() -> None:
    cause = _item(
        "cause",
        "Light intensity",
        "cause_effect",
        "Increasing light intensity increases photosynthesis until saturation.",
    )
    comparison = _item(
        "compare",
        "DNA and RNA",
        "comparison",
        "DNA contains thymine, whereas RNA contains uracil.",
    )

    assert build_question_blueprints(
        [cause, comparison],
        count=4,
        question_types=["fill-blank"],
        difficulty="medium",
        seed=1,
    ) == []

    planned = build_question_blueprints(
        [cause, comparison],
        count=4,
        question_types=["mcq", "true-false", "short-answer", "fill-blank"],
        difficulty="medium",
        seed=1,
    )
    assert planned
    assert all(blueprint.question_type != "fill-blank" for blueprint in planned)


def test_same_concept_can_recur_for_legitimately_different_targets() -> None:
    recursion = _item(
        "recursion",
        "Recursion",
        "core_concept",
        "A base case stops recursive calls, while a recursive case reduces the problem.",
        targets=(
            "base case stops recursive calls",
            "recursive case reduces the problem",
        ),
    )
    planned = build_question_blueprints(
        [recursion],
        count=6,
        question_types=["mcq"],
        difficulty="medium",
        seed=3,
    )

    assert {blueprint.knowledge_target for blueprint in planned} == set(recursion.knowledge_targets)
    assert len({blueprint.objective_key for blueprint in planned}) == len(planned)


def test_semantic_objective_ignores_case_and_surface_punctuation() -> None:
    first = semantic_objective_key("Base Case", "Stops recursive calls.", "Understanding")
    second = semantic_objective_key("base case", "stops recursive calls", "understanding")
    different_target = semantic_objective_key("base case", "reduces the problem", "understanding")

    assert first == second
    assert first != different_target


def test_seeded_variation_only_reorders_strong_valid_plans() -> None:
    kwargs = {
        "items": ITEMS,
        "count": 4,
        "question_types": ["mcq"],
        "difficulty": "medium",
    }
    first = build_question_blueprints(seed=11, **kwargs)
    repeated = build_question_blueprints(seed=11, **kwargs)
    varied = build_question_blueprints(seed=12, **kwargs)

    signature = lambda plans: [
        (plan.content_id, plan.knowledge_target, plan.cognitive_skill, plan.question_type)
        for plan in plans
    ]
    assert signature(first) == signature(repeated)
    assert signature(first) != signature(varied)
    for plan in [*first, *varied]:
        assert plan.category not in {"minor_detail", "metadata_boilerplate"}
        assert plan.importance >= 0.62
        assert plan.question_type == "mcq"


def test_low_importance_and_minor_items_cannot_fill_a_diversity_quota() -> None:
    strong = ITEMS[:2]
    weak = _item(
        "weak",
        "Decorative icon",
        "core_concept",
        "A decorative icon appears beside the paragraph.",
        importance=0.40,
    )
    minor = _item(
        "minor",
        "Blue border",
        "minor_detail",
        "The border is blue.",
        importance=1.0,
    )
    plans = build_question_blueprints(
        [*strong, weak, minor],
        count=10,
        question_types=["mcq"],
        difficulty="medium",
        seed=99,
    )

    assert plans
    assert {plan.content_id for plan in plans}.issubset({"c1", "c2"})
