"""QUIZ BLUEPRINT — the assessment plan, written before any question exists.

A blueprint slot says: *this concept, this knowledge target, this cognitive
skill, this question type, this difficulty, this evidence*.  It is produced
from the semantic study map's knowledge targets, never from sentences.

The blueprint also decides the shape of the quiz.  For an 8-question quiz the
planner aims for a teacher-like spread — core understanding, application,
comparison, mechanism, cause/effect, important knowledge, analysis — but only
using the categories the document actually supports.  A document with no
comparisons simply produces no comparison slots; nothing is invented to fill a
quota.
"""

from __future__ import annotations

import random
from collections.abc import Collection
from typing import Callable
from dataclasses import dataclass

from app.services.quiz_knowledge_targets import KnowledgeTarget
from app.services.quiz_scoring import normalize_question_text

#: Preferred blueprint order for a full-length quiz.  Slots whose skill is
#: unsupported by the document are skipped rather than forced.
#: Reasoning first. A quiz that a teacher would set leads with "why", "how",
#: and "how do these differ", and uses recognition only as a supporting layer.
#: ``understanding`` and ``factual_recall`` are the recognition tier and rank
#: last, so they fill remaining slots rather than dominating the paper.
PREFERRED_SKILL_ORDER: tuple[str, ...] = (
    "cause_effect",
    "comparison",
    "process_order",
    "application",
    "analysis",
    "classification",
    "misconception",
    "understanding",
    "factual_recall",
)

#: Skills that test recognition rather than reasoning.
RECOGNITION_SKILLS: frozenset[str] = frozenset({"understanding", "factual_recall"})

#: Educational tiers. A target's tier is decided by whether it tests a stated
#: *relationship* (tier 1), a substantive grasp of one concept (tier 2), or
#: mere terminology (tier 3). Tier is a property of the knowledge target, so it
#: stays subject-neutral: a chemistry mechanism and a history cause are both
#: tier 1 for the same structural reason.
TIER_REASONING = 1
TIER_UNDERSTANDING = 2
TIER_RECALL = 3

_TIER_1_SKILLS: frozenset[str] = frozenset(
    {"cause_effect", "comparison", "process_order", "analysis", "classification",
     "application", "misconception"}
)


def target_tier(target: KnowledgeTarget) -> int:
    """Which educational tier a knowledge target belongs to.

    A facet-backed target always reaches tier 1: the document states the
    relationship, so the question can ask *why* or *how* rather than *what*.
    An "understanding" target without a facet still demands a real explanation,
    so it is tier 2. Bare terminology is tier 3 and only fills gaps.
    """
    if target.facet_kind or target.cognitive_skill in _TIER_1_SKILLS:
        return TIER_REASONING
    if target.cognitive_skill == "understanding":
        return TIER_UNDERSTANDING
    return TIER_RECALL

#: At most this fraction of a quiz may be recognition questions. A document
#: that genuinely supports nothing else will simply yield a shorter quiz.
MAX_RECOGNITION_SHARE = 0.4

_SKILL_LABEL: dict[str, str] = {
    "understanding": "Core concept understanding",
    "application": "Concept application",
    "comparison": "Important comparison",
    "process_order": "Process / mechanism",
    "cause_effect": "Cause and effect",
    "factual_recall": "Important factual knowledge",
    "analysis": "Integrative / analytical",
    "classification": "Classification",
    "misconception": "Misconception check",
}


@dataclass(frozen=True)
class QuestionBlueprint:
    """One planned question: what it tests and how."""

    id: str
    concept_id: str
    concept: str
    knowledge_target_id: str
    knowledge_target: str
    knowledge_type: str
    cognitive_skill: str
    question_type: str
    difficulty: str
    importance: float
    evidence: str
    pages: tuple[int, ...]
    topic: str = ""
    supporting_ids: tuple[str, ...] = ()
    #: The relational claim being tested and the source's own wording of the
    #: answer, when the target has one. Reasoning questions are written from
    #: these rather than from a template.
    facet_kind: str = ""
    answer_clause: str = ""
    #: Why this concept is worth testing, for diagnostics and auditing.
    importance_reason: str = ""

    @property
    def category(self) -> str:
        """Back-compatible label used by scoring/diversity bookkeeping."""
        return self.knowledge_type

    @property
    def objective_key(self) -> str:
        return semantic_objective_key(self.concept_id, self.knowledge_target_id, self.cognitive_skill)

    @property
    def slot_label(self) -> str:
        return _SKILL_LABEL.get(self.cognitive_skill, self.cognitive_skill)


def semantic_objective_key(concept_id: str, knowledge_target_id: str, cognitive_skill: str) -> str:
    """Stable identity of the knowledge tested, independent of wording/type."""
    return "::".join(
        (
            normalize_question_text(concept_id),
            normalize_question_text(knowledge_target_id),
            normalize_question_text(cognitive_skill),
        )
    )


def _comparison_pair_key(target: KnowledgeTarget) -> tuple[str, ...] | None:
    """Order-independent identity of a contrast target, or None.

    A contrast names both sides — the concept and, in ``answer_clause``, what
    it is contrasted with. Sorting the pair makes both directions collapse to
    one key.
    """
    if target.facet_kind != "contrast":
        return None
    other = normalize_question_text(target.answer_clause)
    concept = normalize_question_text(target.concept_id)
    if not other or not concept:
        return None
    return tuple(sorted((concept, other)))


def _difficulty_for(target: KnowledgeTarget, requested: str) -> str:
    if requested in {"easy", "medium", "hard"}:
        return requested
    return target.difficulty


def _types_for(
    target: KnowledgeTarget,
    allowed_types: list[str],
    type_filter: Callable[[KnowledgeTarget, list[str]], list[str]] | None = None,
) -> list[str]:
    types = [value for value in allowed_types if value in target.question_types]
    if type_filter is not None:
        types = type_filter(target, types)
    return types


def build_question_blueprints(
    targets: list[KnowledgeTarget],
    *,
    count: int,
    question_types: list[str],
    difficulty: str,
    seed: int,
    allowed_skills: frozenset[str] | None = None,
    type_filter: Callable[[KnowledgeTarget, list[str]], list[str]] | None = None,
    exclude_objectives: Collection[str] = (),
    allow_relaxation: bool = True,
) -> list[QuestionBlueprint]:
    """Plan a slightly larger-than-needed, concept-diverse assessment.

    Selection rules, in order of strength:

    1. One slot per semantic objective (concept + target + skill).  The same
       knowledge is never planned twice.
    2. Breadth first: every important concept gets one slot before any concept
       receives a second, so an eight-question quiz covers eight concepts when
       the document contains eight.
    3. Cognitive spread: the planner walks the preferred skill order and only
       reuses a skill once the supported ones are exhausted.
    4. Importance dominates ties; the seed only jitters between otherwise
       equivalent choices, so different seeds pick different valid questions
       from the same deterministic study map.

    ``allowed_skills`` lets a caller restrict planning to the cognitive skills
    a particular writer can actually express (the deterministic writer cannot
    honestly author transfer scenarios, for example).

    ``type_filter`` lets that writer veto question *types* per target. Some
    clauses cannot be phrased as a true/false assertion or carry a meaningful
    blank; without the veto the planner would spend a slot on a question the
    writer then drops, and the quiz would come back short.

    ``exclude_objectives`` names semantic objectives a caller has already
    filled. A top-up round needs this: without it the planner happily re-plans
    the slots the quiz already contains, every candidate is discarded as a
    duplicate, and the quiz stays short even though the document has plenty of
    untouched knowledge targets.

    ``allow_relaxation`` controls whether the quality preferences may be
    dropped to reach ``count``. A caller that is merely widening an
    already-sufficient pool must pass ``False``: with objectives excluded the
    planner runs out of strong targets quickly, and relaxing there would add
    bare-recall slots to a quiz that was never short.
    """
    allowed_types = list(dict.fromkeys(question_types))
    if not allowed_types or not targets:
        return []

    desired = min(24, max(count + 4, count * 2))
    rng = random.Random(seed ^ 0x5EEDB10E)

    # Only targets whose skill can be expressed in a requested question type.
    usable = [
        target
        for target in targets
        if _types_for(target, allowed_types, type_filter)
        and (allowed_skills is None or target.cognitive_skill in allowed_skills)
    ]
    if not usable:
        return []

    selected: list[tuple[KnowledgeTarget, str]] = []
    objectives: set[str] = set(exclude_objectives)
    # Recognition questions are capped so a quiz cannot silently become a list
    # of "what is X?" items. The cap is a *preference for reasoning*, not a
    # prohibition: when a document genuinely supports few reasoning targets,
    # recognition fills the remainder rather than the quiz coming back empty.
    # A short factual handout should still yield a usable quiz.
    reasoning_available = sum(
        1 for target in usable if target.cognitive_skill not in RECOGNITION_SKILLS
    )
    if reasoning_available:
        # Reasoning exists, so recognition stays a garnish. Returning a shorter,
        # stronger quiz is correct: padding to `count` with "explain the role of
        # X" items is exactly the mediocrity this pipeline exists to avoid.
        recognition_budget = max(int(round(count * MAX_RECOGNITION_SHARE)), 1)
        # The share is a cap on *padding*, not a cap on coverage. When the
        # document supports fewer reasoning targets than there are slots, the
        # remaining slots would otherwise go unfilled while important concepts
        # sit unexamined — a 40% cap on an 8-question quiz backed by 4
        # reasoning targets leaves 1 slot unused and 2 concepts unasked. Every
        # concept still deserves one question; the breadth rule below ensures
        # these go to new concepts rather than to second helpings.
        recognition_budget = max(recognition_budget, count - reasoning_available)
    else:
        # A purely definitional document supports nothing else; a recall quiz is
        # the honest output rather than no quiz at all.
        recognition_budget = count
    remaining = list(usable)
    # How many distinct concepts this document can actually cover; breadth is
    # only enforced until each of them has been given a slot.
    concepts_available = len({target.concept_id for target in usable})
    # Concepts that offer something better than bare recall. Used to keep a
    # tier-3 target from being planned when the same concept has a tier-1 or
    # tier-2 target the writer can also express.
    richer_available: dict[str, bool] = {}
    for target in usable:
        if target_tier(target) < TIER_RECALL:
            richer_available[target.concept_id] = True
    # Comparisons planned from each side. "How does waiting time differ from
    # turnaround time?" and its mirror are one knowledge target with two
    # subjects, so their objective keys differ and this loop cannot see the
    # clash. Selection drops the second one later, which wasted a planned slot
    # and left a whole concept unexamined; catching it here lets the slot go to
    # a concept that still has none.
    planned_pairs: set[tuple[str, ...]] = set()
    recognition_selected = 0
    concept_counts: dict[str, int] = {}
    skill_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    page_counts: dict[int, int] = {}

    def plan_pass(
        *,
        enforce_recognition_cap: bool,
        enforce_recall_last_resort: bool,
        stop_at: int | None = None,
    ) -> None:
        """Fill remaining slots under the given quality preferences.

        Re-entrant: it appends to the enclosing ``selected`` list and keeps the
        objective/pair bookkeeping, so a relaxed pass tops up the strict pass's
        result instead of replacing it.
        """
        nonlocal recognition_selected
        limit = desired if stop_at is None else min(stop_at, desired)
        while remaining and len(selected) < limit:
            best_index = -1
            best_value = float("-inf")
            best_type = ""
            for index, target in enumerate(remaining):
                objective = semantic_objective_key(
                    target.concept_id, target.target_id, target.cognitive_skill
                )
                if objective in objectives:
                    continue
                if _comparison_pair_key(target) in planned_pairs:
                    continue
                options = _types_for(target, allowed_types, type_filter)
                if not options:
                    continue
                # A recognition target reads better as multiple choice than as a
                # bare "What is X?": the options make the discrimination explicit
                # and give the student something to reason against, whereas the
                # written form is a vocabulary prompt. This is a general
                # question-type preference for recognition skills, not a rule about
                # any particular concept, and it applies only when the writer has
                # confirmed it can build the MCQ (type_filter already removed types
                # it cannot deliver, including MCQs with too few good distractors).
                # Where no MCQ is available -- typically a very small document --
                # the clean short-answer recognition question stands.
                prefer_mcq = (
                    target.cognitive_skill in RECOGNITION_SKILLS and "mcq" in options
                )
                question_type = min(
                    options,
                    key=lambda value: (
                        value != "mcq" if prefer_mcq else False,
                        type_counts.get(value, 0),
                        allowed_types.index(value),
                    ),
                )

                tier = target_tier(target)
                is_recognition = target.cognitive_skill in RECOGNITION_SKILLS
                # Enforce the recognition cap during planning, so reasoning slots
                # are not crowded out by easy definitional ones.
                if (
                    enforce_recognition_cap
                    and is_recognition
                    and recognition_selected >= recognition_budget
                ):
                    continue
                # Recall is a last resort. While this concept still has a richer
                # target available, never spend its slot on terminology: the
                # document explaining how something works makes "what is it?" the
                # weaker question by definition.
                if (
                    enforce_recall_last_resort
                    and tier == TIER_RECALL
                    and richer_available.get(target.concept_id)
                ):
                    continue

                value = target.importance * 1.6
                # Tier dominates skill ordering: a stated relationship is worth far
                # more than a definition of the same concept, so a concept with a
                # richer target never gets asked "what is X?".
                value += {1: 1.10, 2: 0.35, 3: 0.0}[tier]
                # Concept breadth is the strongest diversity term: a second slot on
                # an already-covered concept is worth much less than a first slot
                # on a new one.
                # Breadth is a near-hard rule, not a tiebreaker. Every important
                # concept earns a slot before any concept earns a second, so an
                # eight-question quiz covers eight concepts when the document has
                # eight. The penalty must exceed every other bonus combined,
                # otherwise a strong concept's second facet-backed target outbids an
                # untouched concept's first and coverage silently collapses.
                already = concept_counts.get(target.concept_id, 0)
                if already and len(concept_counts) < concepts_available:
                    value -= 3.0 * already
                skill_rank = (
                    PREFERRED_SKILL_ORDER.index(target.cognitive_skill)
                    if target.cognitive_skill in PREFERRED_SKILL_ORDER
                    else len(PREFERRED_SKILL_ORDER)
                )
                value += 0.30 * (1.0 - skill_rank / max(1, len(PREFERRED_SKILL_ORDER)))
                # A target backed by a relational claim the document actually makes
                # is worth more than a definitional one: it can carry a real "why"
                # or "how" question rather than a recognition template.
                if target.facet_kind:
                    value += 0.55
                value += 0.45 / (1 + skill_counts.get(target.cognitive_skill, 0))
                value += 0.20 / (1 + type_counts.get(question_type, 0))
                value += 0.18 / (1 + topic_counts.get(normalize_question_text(target.topic), 0))
                value += sum(0.06 / (1 + page_counts.get(page, 0)) for page in target.pages[:2])
                # Seeded jitter must be large enough to reorder genuinely
                # comparable targets, so different seeds give different valid
                # quizzes, but small enough that it cannot promote a weak target
                # over a clearly stronger one.
                value += rng.random() * 0.22
                if value > best_value:
                    best_value, best_index, best_type = value, index, question_type

            if best_index < 0:
                break
            target = remaining.pop(best_index)
            if target.cognitive_skill in RECOGNITION_SKILLS:
                recognition_selected += 1
            objectives.add(
                semantic_objective_key(target.concept_id, target.target_id, target.cognitive_skill)
            )
            pair_key = _comparison_pair_key(target)
            if pair_key:
                planned_pairs.add(pair_key)
            selected.append((target, best_type))
            concept_counts[target.concept_id] = concept_counts.get(target.concept_id, 0) + 1
            skill_counts[target.cognitive_skill] = skill_counts.get(target.cognitive_skill, 0) + 1
            type_counts[best_type] = type_counts.get(best_type, 0) + 1
            topic_key = normalize_question_text(target.topic)
            topic_counts[topic_key] = topic_counts.get(topic_key, 0) + 1
            for page in target.pages:
                page_counts[page] = page_counts.get(page, 0) + 1

    # Strict pass: every quality preference in force. This is what a document
    # with plenty of reasoning material yields, and it is the normal case.
    plan_pass(enforce_recognition_cap=True, enforce_recall_last_resort=True)

    # The two rules above are *preferences about which question is better*, not
    # judgements about whether a question is supported. Enforcing them
    # unconditionally meant a document with 19 usable knowledge targets could
    # plan only 13 slots, so a request for more questions failed with "not
    # enough material" while genuinely grounded targets sat unused. When the
    # strict pass cannot fill the quiz, relax them in order of least
    # educational harm -- the recall-last-resort rule first (it only reorders
    # which target of an already-covered concept is used), then the recognition
    # cap. Both relaxed passes still plan only supported targets; no grounding
    # rule is touched.
    # The strict pass normally overshoots `count` (it plans up to `desired`) so
    # the writer and the gates have spare material to lose. Relaxing must
    # therefore trigger on a genuine shortfall against `count`, and each
    # relaxed pass must stop as soon as the quiz is merely fillable -- planning
    # on to `desired` would append weaker recall slots that then compete with,
    # and displace, the strong ones the strict pass already found.
    if allow_relaxation and len(selected) < count:
        plan_pass(
            enforce_recognition_cap=True,
            enforce_recall_last_resort=False,
            stop_at=count,
        )
    if allow_relaxation and len(selected) < count:
        plan_pass(
            enforce_recognition_cap=False,
            enforce_recall_last_resort=False,
            stop_at=count,
        )

    return [
        QuestionBlueprint(
            id=f"bp-{index + 1}",
            concept_id=target.concept_id,
            concept=target.concept_name,
            knowledge_target_id=target.target_id,
            knowledge_target=target.statement,
            knowledge_type=target.knowledge_type,
            cognitive_skill=target.cognitive_skill,
            question_type=question_type,
            difficulty=_difficulty_for(target, difficulty),
            importance=target.importance,
            evidence=target.evidence,
            pages=target.pages,
            topic=target.topic,
            supporting_ids=target.supporting_ids,
            facet_kind=target.facet_kind,
            answer_clause=target.answer_clause,
            importance_reason=target.importance_reason,
        )
        for index, (target, question_type) in enumerate(selected)
    ]


def blueprint_block(blueprints: list[QuestionBlueprint]) -> str:
    lines: list[str] = []
    for index, blueprint in enumerate(blueprints, start=1):
        lines.append(
            f"- [{blueprint.id}] Q{index} {blueprint.slot_label}: concept={blueprint.concept!r} "
            f"({blueprint.concept_id}); knowledge_target={blueprint.knowledge_target!r} "
            f"({blueprint.knowledge_target_id}); skill={blueprint.cognitive_skill}; "
            f"type={blueprint.question_type}; difficulty={blueprint.difficulty}; "
            f"pages={list(blueprint.pages)}; VERBATIM EVIDENCE={blueprint.evidence!r}"
        )
    return "\n".join(lines) or "(no blueprints)"
