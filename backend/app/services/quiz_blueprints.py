"""Teacher-style question blueprints built from the verified content map.

A blueprint defines *what* knowledge is tested and *how* it is tested before an
LLM writes prose.  This prevents random type assignment and gives the backend a
stable semantic objective for duplicate detection: concept + knowledge target
+ cognitive skill.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.services.quiz_content_map import (
    ContentItem,
    EXAMPLE_CATEGORY,
    QUESTION_WORTHY_CATEGORIES,
    category_label,
)
from app.services.quiz_scoring import normalize_question_text

_SUPPORTED_TYPES: dict[str, tuple[str, ...]] = {
    "core_concept": ("mcq", "true-false", "short-answer", "fill-blank"),
    "important_definition": ("mcq", "fill-blank", "true-false", "short-answer"),
    "process_mechanism": ("mcq", "true-false", "short-answer", "fill-blank"),
    "cause_effect": ("mcq", "true-false", "short-answer"),
    "comparison": ("mcq", "true-false", "short-answer"),
    "formula_rule": ("mcq", "fill-blank", "short-answer", "true-false"),
    "important_example": ("mcq", "short-answer", "true-false"),
}

_CATEGORY_SKILLS: dict[str, tuple[str, ...]] = {
    "core_concept": ("understanding", "application", "analysis", "factual_recall"),
    "important_definition": ("understanding", "factual_recall", "misconception"),
    "process_mechanism": ("process_order", "application", "analysis", "understanding"),
    "cause_effect": ("cause_effect", "application", "analysis", "understanding"),
    "comparison": ("comparison", "analysis", "understanding", "misconception"),
    "formula_rule": ("application", "understanding", "factual_recall", "misconception"),
    "important_example": ("application", "understanding", "analysis"),
}

# Some type/skill pairings are intrinsically malformed (for example an
# application fill-blank).  They are omitted rather than leaving the LLM to
# reinterpret a randomly assigned type.
_TYPE_SKILLS: dict[str, frozenset[str]] = {
    "mcq": frozenset(
        {
            "understanding",
            "application",
            "analysis",
            "factual_recall",
            "process_order",
            "cause_effect",
            "comparison",
            "misconception",
        }
    ),
    "true-false": frozenset(
        {"understanding", "analysis", "process_order", "cause_effect", "comparison", "misconception"}
    ),
    "fill-blank": frozenset({"factual_recall", "understanding"}),
    "short-answer": frozenset(
        {"understanding", "application", "analysis", "process_order", "cause_effect", "comparison"}
    ),
}


@dataclass(frozen=True)
class QuestionBlueprint:
    id: str
    content_id: str
    concept: str
    category: str
    importance: float
    knowledge_target: str
    cognitive_skill: str
    question_type: str
    difficulty: str
    evidence: str
    pages: tuple[int, ...]

    @property
    def objective_key(self) -> str:
        return semantic_objective_key(self.concept, self.knowledge_target, self.cognitive_skill)


def semantic_objective_key(concept: str, knowledge_target: str, cognitive_skill: str) -> str:
    """Stable identity for the knowledge being tested, independent of wording/type."""
    return "::".join(
        (
            normalize_question_text(concept),
            normalize_question_text(knowledge_target),
            normalize_question_text(cognitive_skill),
        )
    )


def _difficulty_for(skill: str, requested: str) -> str:
    if requested in {"easy", "medium", "hard"}:
        return requested
    if skill == "factual_recall":
        return "easy"
    if skill in {"understanding", "misconception", "process_order"}:
        return "medium"
    return "hard"


def _proposal_types(item: ContentItem, allowed_types: list[str], skill: str) -> list[str]:
    supported = set(_SUPPORTED_TYPES.get(item.category, ()))
    return [
        question_type
        for question_type in allowed_types
        if question_type in supported and skill in _TYPE_SKILLS.get(question_type, frozenset())
    ]


def _proposal_items(items: list[ContentItem]) -> tuple[list[ContentItem], list[ContentItem]]:
    primary = [
        item
        for item in items
        if item.category in QUESTION_WORTHY_CATEGORIES and item.importance >= 0.62
    ]
    examples = [item for item in items if item.category == EXAMPLE_CATEGORY and item.importance >= 0.50]
    return primary, examples


def build_question_blueprints(
    items: list[ContentItem],
    *,
    count: int,
    question_types: list[str],
    difficulty: str,
    seed: int,
) -> list[QuestionBlueprint]:
    """Plan a larger-than-needed, content-matched and cognitively varied set."""
    allowed_types = list(dict.fromkeys(question_types))
    desired = min(24, max(count + 4, count * 2))
    primary, examples = _proposal_items(items)
    if not primary:
        return []

    # Each tuple is item, target, skill, type. Multiple candidate wordings may
    # later reference one blueprint, but only one blueprint exists per semantic
    # objective. Final selection separately prevents the same concept/target
    # from appearing twice merely because its cognitive verb differs.
    proposals: list[tuple[ContentItem, str, str, str]] = []
    for item in [*primary, *examples]:
        for target in item.knowledge_targets:
            for skill in _CATEGORY_SKILLS.get(item.category, ("understanding",)):
                for question_type in _proposal_types(item, allowed_types, skill):
                    proposals.append((item, target, skill, question_type))

    rng = random.Random(seed ^ 0x5EEDB10E)
    rng.shuffle(proposals)
    selected: list[tuple[ContentItem, str, str, str]] = []
    objectives: set[str] = set()
    concept_counts: dict[str, int] = {}
    skill_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    page_counts: dict[int, int] = {}
    # Examples remain a small supplement even when the source contains many.
    max_examples = max(1, desired // 6)
    example_count = 0

    while proposals and len(selected) < desired:
        best_index = -1
        best_value = float("-inf")
        for index, (item, target, skill, question_type) in enumerate(proposals):
            objective = semantic_objective_key(item.concept, target, skill)
            if objective in objectives:
                continue
            if item.category == EXAMPLE_CATEGORY and example_count >= max_examples:
                continue

            # Importance dominates.  Diversity bonuses then distribute skills,
            # concepts, categories, types, and source pages without admitting a
            # low-importance item merely to fill a quota.
            value = item.importance * 1.8
            value += 0.50 / (1 + skill_counts.get(skill, 0))
            value += 0.32 / (1 + concept_counts.get(item.concept.casefold(), 0))
            value += 0.20 / (1 + category_counts.get(item.category, 0))
            value += 0.18 / (1 + type_counts.get(question_type, 0))
            value += sum(0.07 / (1 + page_counts.get(page, 0)) for page in item.pages[:2])
            value += rng.random() * 0.015
            if value > best_value:
                best_value = value
                best_index = index

        if best_index < 0:
            break
        item, target, skill, question_type = proposals.pop(best_index)
        objective = semantic_objective_key(item.concept, target, skill)
        if objective in objectives:
            continue
        selected.append((item, target, skill, question_type))
        objectives.add(objective)
        concept_key = item.concept.casefold()
        concept_counts[concept_key] = concept_counts.get(concept_key, 0) + 1
        skill_counts[skill] = skill_counts.get(skill, 0) + 1
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
        type_counts[question_type] = type_counts.get(question_type, 0) + 1
        for page in item.pages:
            page_counts[page] = page_counts.get(page, 0) + 1
        if item.category == EXAMPLE_CATEGORY:
            example_count += 1

    return [
        QuestionBlueprint(
            id=f"bp-{index + 1}",
            content_id=item.id,
            concept=item.concept,
            category=item.category,
            importance=item.importance,
            knowledge_target=target,
            cognitive_skill=skill,
            question_type=question_type,
            difficulty=_difficulty_for(skill, difficulty),
            evidence=item.evidence,
            pages=item.pages,
        )
        for index, (item, target, skill, question_type) in enumerate(selected)
    ]


def blueprint_block(blueprints: list[QuestionBlueprint]) -> str:
    lines: list[str] = []
    for blueprint in blueprints:
        lines.append(
            f"- [{blueprint.id}] concept={blueprint.concept!r}; "
            f"category={category_label(blueprint.category)}; target={blueprint.knowledge_target!r}; "
            f"skill={blueprint.cognitive_skill}; type={blueprint.question_type}; "
            f"difficulty={blueprint.difficulty}; pages={list(blueprint.pages)}; "
            f"VERBATIM EVIDENCE={blueprint.evidence!r}"
        )
    return "\n".join(lines) or "(no blueprints)"
