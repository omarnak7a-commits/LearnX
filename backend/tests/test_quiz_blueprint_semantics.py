"""Blueprint planning: knowledge targets in, a teacher-shaped plan out."""

from __future__ import annotations

from app.services.quiz_blueprints import (
    build_question_blueprints,
    semantic_objective_key,
)
from app.services.quiz_knowledge_targets import KnowledgeTarget

ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]


def _target(
    concept_id: str,
    *,
    skill: str,
    importance: float = 0.9,
    knowledge_type: str = "definition",
    page: int = 1,
    topic: str = "",
) -> KnowledgeTarget:
    return KnowledgeTarget(
        target_id=f"{concept_id}--{skill}",
        concept_id=concept_id,
        concept_name=concept_id.replace("-", " ").title(),
        statement=f"{skill} target for {concept_id}",
        cognitive_skill=skill,
        knowledge_type=knowledge_type,
        importance=importance,
        evidence=f"The {concept_id} performs a clearly described role in the system.",
        pages=(page,),
        topic=topic or concept_id,
    )


TARGETS = [
    _target("cell-membrane", skill="understanding"),
    _target("cell-membrane", skill="application", knowledge_type="process"),
    _target("mitosis", skill="process_order", knowledge_type="process", page=2),
    _target("temperature", skill="cause_effect", knowledge_type="cause_effect", page=3),
    _target("plant-cells", skill="comparison", knowledge_type="comparison", page=4),
    _target("density", skill="factual_recall", knowledge_type="principle", page=5),
]


def test_plans_cognitively_diverse_objectives_before_wording() -> None:
    blueprints = build_question_blueprints(
        TARGETS, count=6, question_types=ALL_TYPES, difficulty="medium", seed=42
    )

    assert len(blueprints) >= 5
    assert len({blueprint.cognitive_skill for blueprint in blueprints}) >= 3
    assert len({blueprint.concept_id for blueprint in blueprints}) >= 4
    # Each planned slot is a distinct semantic objective.
    assert len({blueprint.objective_key for blueprint in blueprints}) == len(blueprints)


def test_breadth_first_covers_a_new_concept_before_repeating_one() -> None:
    blueprints = build_question_blueprints(
        TARGETS, count=5, question_types=ALL_TYPES, difficulty="mixed", seed=3
    )
    first_five = [blueprint.concept_id for blueprint in blueprints[:5]]
    assert len(set(first_five)) == 5


def test_question_types_are_matched_to_supported_skills() -> None:
    cause = _target("light-intensity", skill="cause_effect", knowledge_type="cause_effect")
    comparison = _target("dna-and-rna", skill="comparison", knowledge_type="comparison")

    # Neither cause/effect nor comparison can be expressed as a fill-blank.
    assert (
        build_question_blueprints(
            [cause, comparison],
            count=4,
            question_types=["fill-blank"],
            difficulty="medium",
            seed=1,
        )
        == []
    )

    planned = build_question_blueprints(
        [cause, comparison], count=4, question_types=ALL_TYPES, difficulty="medium", seed=1
    )
    assert planned
    assert all(blueprint.question_type != "fill-blank" for blueprint in planned)


def test_same_concept_can_recur_only_for_a_different_target() -> None:
    targets = [
        _target("recursion", skill="understanding"),
        _target("recursion", skill="application", knowledge_type="process"),
    ]
    blueprints = build_question_blueprints(
        targets, count=2, question_types=ALL_TYPES, difficulty="mixed", seed=9
    )
    assert len(blueprints) == 2
    assert {blueprint.concept_id for blueprint in blueprints} == {"recursion"}
    assert len({blueprint.knowledge_target_id for blueprint in blueprints}) == 2


def test_allowed_skills_restricts_planning_to_writable_slots() -> None:
    blueprints = build_question_blueprints(
        TARGETS,
        count=6,
        question_types=ALL_TYPES,
        difficulty="mixed",
        seed=5,
        allowed_skills=frozenset({"understanding", "comparison"}),
    )
    assert blueprints
    assert {blueprint.cognitive_skill for blueprint in blueprints} <= {
        "understanding",
        "comparison",
    }


def test_seeded_variation_only_reorders_valid_plans() -> None:
    def plan(seed: int) -> list[str]:
        return [
            blueprint.objective_key
            for blueprint in build_question_blueprints(
                TARGETS, count=4, question_types=ALL_TYPES, difficulty="mixed", seed=seed
            )
        ]

    assert plan(11) == plan(11)
    valid = {
        semantic_objective_key(target.concept_id, target.target_id, target.cognitive_skill)
        for target in TARGETS
    }
    assert set(plan(11)) <= valid
    assert set(plan(202)) <= valid


def test_no_targets_means_no_plan() -> None:
    assert build_question_blueprints(
        [], count=6, question_types=ALL_TYPES, difficulty="mixed", seed=1
    ) == []
