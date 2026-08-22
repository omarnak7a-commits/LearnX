"""KNOWLEDGE TARGETS — what a learner must be able to *do* with a concept.

Questions are never generated from sentences.  They are generated from
knowledge targets: explicit statements of the understanding being tested, each
one derived from a concept in the semantic study map and grounded in the exact
evidence that teaches it.

For example, the concept "Mitosis" (knowledge_type=process) yields targets
such as:

    - understand the purpose and outcome of mitosis        (understanding)
    - order the stages of mitosis                          (process_order)
    - predict the outcome when mitosis is disrupted        (application)
    - distinguish mitosis from meiosis                     (comparison)

A target is only created when the source actually supports it.  If the
document contains no comparison for a concept, no comparison target exists,
and therefore no comparison question can ever be written about it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.quiz_scoring import content_tokens, normalize_question_text
from app.services.quiz_understanding import (
    _states_claim_about,
    ConceptNode,
    DocumentUnderstanding,
    Relationship,
)

CognitiveSkill = str

#: Cognitive skills, ordered from recall to transfer.
COGNITIVE_SKILLS: tuple[str, ...] = (
    "factual_recall",
    "understanding",
    "process_order",
    "misconception",
    "classification",
    "comparison",
    "cause_effect",
    "analysis",
    "application",
)

#: Question types each cognitive skill can be expressed as without becoming
#: malformed (an "application fill-blank", for example, is not a real thing).
SKILL_QUESTION_TYPES: dict[str, frozenset[str]] = {
    "factual_recall": frozenset({"mcq", "fill-blank", "short-answer"}),
    "understanding": frozenset({"mcq", "true-false", "short-answer", "fill-blank"}),
    "process_order": frozenset({"mcq", "true-false", "short-answer"}),
    # A misconception check asserts a relationship and asks whether it holds,
    # which is a true/false task by construction. There is no honest MCQ form:
    # the writer would have to invent three further wrong relationships.
    "misconception": frozenset({"true-false"}),
    "classification": frozenset({"mcq", "true-false", "short-answer"}),
    "comparison": frozenset({"mcq", "true-false", "short-answer"}),
    "cause_effect": frozenset({"mcq", "true-false", "short-answer"}),
    "analysis": frozenset({"mcq", "true-false", "short-answer"}),
    "application": frozenset({"mcq", "short-answer"}),
}

_SKILL_DIFFICULTY = {
    "factual_recall": "easy",
    "understanding": "medium",
    "process_order": "medium",
    "misconception": "medium",
    "classification": "medium",
    "comparison": "hard",
    "cause_effect": "hard",
    "analysis": "hard",
    "application": "hard",
}


@dataclass(frozen=True)
class KnowledgeTarget:
    """One testable understanding, grounded in the study map."""

    target_id: str
    concept_id: str
    concept_name: str
    statement: str
    cognitive_skill: str
    knowledge_type: str
    importance: float
    evidence: str
    pages: tuple[int, ...]
    topic: str = ""
    supporting_ids: tuple[str, ...] = ()
    difficulty: str = "medium"
    #: The relational claim this target tests, when it has one. ``facet_kind``
    #: says what sort of claim it is (purpose/cause/effect/...), and
    #: ``answer_clause`` is the source's own wording of the answer. Reasoning
    #: questions are written from these, so a question can only ask "why does
    #: X matter?" when the document actually says why.
    facet_kind: str = ""
    answer_clause: str = ""
    #: Why this concept is worth testing — surfaced in diagnostics so a human
    #: can audit the teacher-judgement, per requirement 4.
    importance_reason: str = ""

    @property
    def question_types(self) -> frozenset[str]:
        return SKILL_QUESTION_TYPES.get(self.cognitive_skill, frozenset({"mcq"}))

    def objective_key(self) -> str:
        """Stable identity of the knowledge tested — independent of wording."""
        return f"{self.concept_id}::{self.cognitive_skill}"


# --------------------------------------------------------------------------- #
# Source-support tests: a target may only exist if the PDF teaches it
# --------------------------------------------------------------------------- #

_SEQUENCE_SUPPORT = re.compile(
    r"\b(first|second|third|then|next|finally|after|before|begins?|followed by|"
    r"stages?|steps?|phases?|sequence|order|proceeds? through|cycle)\b|"
    r"اولا|ثم|بعد|مراحل|خطوات|ترتيب",
    re.IGNORECASE,
)
_OUTCOME_SUPPORT = re.compile(
    r"\b(produces?|generates?|results? in|leads? to|yields?|forms?|creates?|ensures?|"
    r"causes?|so that|allows?|enables?|prevents?|breaks? down|converts?|synthes\w+|"
    r"used for|responsible for|required for|essential for|regulat\w+|controls?)\b|"
    r"ينتج|يودي الي|يسبب|يسمح|يمنع|ضروري|مسوول عن",
    re.IGNORECASE,
)
_CONTRAST_SUPPORT = re.compile(
    r"\b(unlike|whereas|in contrast|compared (?:to|with)|differs? from|difference between|"
    r"rather than|instead of|while\b.{0,60}\b(?:not|lacks?)|lacks?|both\b.{0,40}\band\b|"
    r"distinguish\w*)\b|على عكس|بينما|يختلف عن|الفرق بين|مقارنه",
    re.IGNORECASE,
)
#: Classification requires the source to actually enumerate categories — a
#: phrase such as "a specialized type of cell division" names one thing and is
#: therefore not a taxonomy.
_CATEGORY_SUPPORT = re.compile(
    r"\b(?:(?:two|three|four|five|several|different|main|major)\s+(?:types?|kinds?|forms?|"
    r"categor\w+|classes|groups|varieties)|categor(?:y|ies|ized|ised)\s+(?:as|into)|"
    r"classif(?:y|ied|ication)\s+(?:as|into)|divided into|separated into|grouped into|"
    r"exists? in (?:two|three|several)|either\b.{0,40}\bor\b)\b|"
    r"ينقسم الي|يصنف الي|انواع",
    re.IGNORECASE,
)
_RULE_SUPPORT = re.compile(
    r"=|\b(law|principle|theory|rule|theorem|must|always|never|equation|formula|"
    r"states that)\b|قانون|مبدا|نظريه|قاعده|معادله",
    re.IGNORECASE,
)


def _concept_text(concept: ConceptNode) -> str:
    return " ".join([concept.description, *(item.text for item in concept.evidence)])


def _pick_evidence(concept: ConceptNode, pattern: re.Pattern[str] | None) -> tuple[str, tuple[int, ...]] | None:
    """The concept's best evidence span for a given kind of target."""
    if not concept.evidence:
        return None
    if pattern is None:
        best = concept.evidence[0]
        return best.text, (best.page,)
    for item in concept.evidence:
        if pattern.search(item.text):
            return item.text, (item.page,)
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:64]


def _statement(skill: str, concept: ConceptNode, extra: str = "") -> str:
    name = concept.name
    templates = {
        "factual_recall": f"recall the defining term or value associated with {name}",
        "understanding": f"understand what {name} is and what role it plays",
        "process_order": f"understand the order and mechanism of {name}",
        "misconception": f"reject a plausible misconception about {name}",
        "classification": f"understand the categories that {name} is divided into",
        "comparison": f"distinguish {name} from {extra or 'the idea it is contrasted with'}",
        "cause_effect": f"explain the cause and effect involved in {name}",
        "analysis": f"infer the conclusion that {name} supports",
        "application": f"apply {name} to predict an outcome in a new situation",
    }
    return templates.get(skill, f"understand {name}")


def _contrast_partner(
    concept: ConceptNode,
    understanding: DocumentUnderstanding,
    relationships: tuple[Relationship, ...],
) -> ConceptNode | None:
    for relationship in relationships:
        if relationship.kind != "contrast":
            continue
        if relationship.source_id == concept.concept_id:
            partner = understanding.concept(relationship.target_id)
            if partner:
                return partner
        if relationship.target_id == concept.concept_id:
            partner = understanding.concept(relationship.source_id)
            if partner:
                return partner
    # Fall back to a concept named inside this concept's own contrast evidence.
    text = _concept_text(concept)
    if not _CONTRAST_SUPPORT.search(text):
        return None
    tokens = content_tokens(text)
    for other in understanding.concepts:
        if other.concept_id == concept.concept_id:
            continue
        other_tokens = content_tokens(other.name)
        if other_tokens and other_tokens <= tokens:
            return other
    return None


def _provider_target_skill(statement: str) -> str | None:
    """Map a proposed target phrase onto a cognitive skill, if it is one."""
    text = normalize_question_text(statement)
    if not text:
        return None
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("application", ("apply", "predict", "use it to", "scenario", "what would happen")),
        ("comparison", ("distinguish", "compare", "contrast", "difference", "differ")),
        ("cause_effect", ("cause", "effect", "because", "why", "leads to", "results in")),
        ("process_order", ("order", "steps", "stages", "sequence", "phases", "mechanism")),
        ("classification", ("classify", "categor", "types of", "kinds of")),
        ("analysis", ("infer", "conclude", "conclusion", "analyse", "analyze", "relationship")),
        ("misconception", ("misconception", "not true", "incorrect", "confuse")),
        ("understanding", ("understand", "explain", "describe", "role", "purpose", "function")),
        ("factual_recall", ("state", "name", "recall", "identify", "list", "define")),
    ]
    for skill, needles in rules:
        if any(needle in text for needle in needles):
            return skill
    return None


def _importance_reason(concept: ConceptNode, understanding: DocumentUnderstanding) -> str:
    """A human-readable answer to 'why is this concept important?'."""
    if concept.rationale:
        return concept.rationale
    parts: list[str] = []
    signals = concept.signals
    label = {
        "process": "explains a mechanism the document teaches",
        "cause_effect": "states a causal relationship",
        "comparison": "draws a distinction the document emphasises",
        "classification": "organises the material into categories",
        "principle": "states a rule the learner must apply",
        "definition": "defines a term the rest of the document builds on",
        "example": "illustrates a taught idea",
        "fact": "states a supporting fact",
    }.get(concept.knowledge_type, "is taught by the document")
    parts.append(label)
    if signals.get("explanatory_depth", 0) >= 0.8:
        parts.append("is explained in depth")
    if signals.get("centrality", 0) >= 0.5:
        parts.append("other taught concepts depend on it")
    if signals.get("teaching_emphasis", 0) >= 0.4:
        parts.append("the document flags it as important")
    if len(concept.source_pages) > 1:
        parts.append("developed across several pages")
    return "; ".join(parts)


#: Which cognitive skill each relational facet supports, and how the target
#: reads. A facet is the document's own statement of the relation, so a
#: question built on it is answerable from the source rather than invented.
#: Skills that reuse a claim rather than restate it: the student must apply the
#: knowledge to a case, so sharing an answer clause with a reasoning target is
#: not duplication.
#: A misconception check deliberately reuses a reasoning target's clause: it
#: asserts the same relationship with the WRONG concept attached and asks the
#: student to reject it. That is the opposite task, not a restatement, and it
#: is the only source of "False" answers — excluding it here made every
#: true/false answer in every quiz "True", which a student can game without
#: understanding anything.
_TRANSFER_SKILLS: frozenset[str] = frozenset({"application", "misconception"})

_FACET_SKILL: dict[str, tuple[str, str]] = {
    "purpose": ("cause_effect", "explain why {name} matters and what it accomplishes"),
    "cause": ("cause_effect", "explain what causes {name}"),
    "effect": ("cause_effect", "explain what results from {name}"),
    "mechanism": ("process_order", "explain how {name} works"),
    "contrast": ("comparison", "distinguish {name} from what it is contrasted with"),
    "category": ("classification", "identify the categories {name} divides into"),
    "condition": ("analysis", "explain what {name} depends on"),
}


#: How a *graph edge* becomes an exam target. These mirror _FACET_SKILL but are
#: driven by relationships between two concepts rather than by a clause inside
#: one sentence, so they can ask how two ideas connect. "related" is deliberately
#: absent: an untyped association states nothing specific enough to test.
_RELATION_SKILL: dict[str, tuple[str, str]] = {
    "contrast": ("comparison", "distinguish {name} from {other}"),
    "cause": ("cause_effect", "explain how {name} leads to {other}"),
    "produces": ("cause_effect", "explain what {name} produces"),
    "depends_on": ("analysis", "explain what {name} depends on"),
    "part_of": ("classification", "explain how {name} fits within {other}"),
    "prerequisite": ("analysis", "explain why {name} is needed before {other}"),
}

#: The facet kind each relation behaves like, so the writer reuses the same
#: grammar-aware stems instead of needing a parallel set.
_RELATION_FACET: dict[str, str] = {
    "contrast": "contrast",
    "cause": "cause",
    "produces": "effect",
    "depends_on": "condition",
    "part_of": "category",
    "prerequisite": "condition",
}


#: A transfer question asks the learner to reason about consequences, so the
#: document must state a *consequence*, not merely describe what something is.
#: "so that the cell can recycle damaged components" supports transfer; "a
#: number system that extends the complex numbers" is a definition wearing a
#: relative clause, and reasoning from it would mean inventing the scenario.
_OUTCOME_MARKER = re.compile(
    r"\b(?:so\s+that|in\s+order\s+to|which\s+(?:allows|enables|ensures|results)|"
    r"resulting\s+in|leads?\s+to|ensuring|allowing|enabling|thereby|"
    r"is\s+used\s+(?:for|in|to)|responsible\s+for)\b",
    re.IGNORECASE,
)


def _states_an_outcome(evidence: str) -> bool:
    """True when the evidence states a consequence a learner can reason from."""
    return bool(_OUTCOME_MARKER.search(evidence))


#: A sentence that actually draws the contrast, rather than merely mentioning
#: that one exists. "X differs from Y in that ...", "Unlike Y, X ...", and
#: "X ..., whereas Y ..." all state the distinction; an interrogative or a
#: bare "the difference between X and Y" does not.
_DRAWS_DISTINCTION = re.compile(
    r"\bdiffers?\s+from\b|\bunlike\b|\bin\s+contrast\s+to\b|"
    r"\bwhereas\b|\bwhile\b|\bcompared\s+(?:to|with)\b",
    re.IGNORECASE,
)


def _states_the_distinction(evidence: str) -> bool:
    """Does this sentence state the difference, or only point at one?"""
    text = (evidence or "").strip()
    if not text or text.endswith("?"):
        return False
    return bool(_DRAWS_DISTINCTION.search(text))


def derive_targets_for_concept(
    concept: ConceptNode,
    understanding: DocumentUnderstanding,
) -> list[KnowledgeTarget]:
    """All source-supported knowledge targets for one concept.

    Reasoning targets come from *facets*: relational claims the document
    actually makes. Where there is no stated purpose there is no "why does it
    matter?" target, and so no such question can ever be written. This is what
    keeps higher-order questions honest instead of templated.
    """
    reason = _importance_reason(concept, understanding)
    targets: list[KnowledgeTarget] = []
    seen_skills: set[str] = set()
    # Answer clauses already claimed for this concept. One sentence can satisfy
    # several relation patterns — Newton's First Law reads as both a mechanism
    # and an effect — producing two targets whose answers are the same words
    # under different skill labels. Asking both puts one concept in the exam
    # twice and costs another concept its slot, so the second is refused here
    # rather than downstream, leaving the slot free for a new concept.
    seen_clauses: list[set[str]] = []

    def _clause_is_new(clause: str) -> bool:
        tokens = content_tokens(clause)
        if len(tokens) < 4:
            return True
        for existing in seen_clauses:
            overlap = len(tokens & existing) / max(1, len(tokens | existing))
            if overlap >= 0.70:
                return False
        seen_clauses.append(tokens)
        return True

    def add(
        skill: str,
        statement: str,
        *,
        evidence: str,
        pages: tuple[int, ...],
        facet_kind: str = "",
        answer_clause: str = "",
        supporting: tuple[str, ...] = (),
    ) -> None:
        if skill in seen_skills or not evidence:
            return
        # Only reasoning targets that *state* the clause compete for it. An
        # application target asks the student to transfer the same fact to a
        # situation, which is a different task, not a restatement.
        #
        # A target with no clause of its own is answered from its evidence, so
        # the evidence is what it will end up testing. Comparing that keeps a
        # graph edge from re-asking the sentence a facet target already covers
        # under a different skill label.
        # Only *reasoning* targets are compared. A concept's definitional
        # targets share the same evidence by nature — "what is X?" and "how
        # does X work?" both cite the sentence that introduces X — and they ask
        # genuinely different things, so evidence sharing is not duplication
        # there. Two relational targets resting on one sentence with no clause
        # to tell them apart, however, will produce the same question twice.
        claim_text = answer_clause or (evidence if facet_kind else "")
        if (
            claim_text
            and skill not in _TRANSFER_SKILLS
            and not _clause_is_new(claim_text)
        ):
            return
        seen_skills.add(skill)
        targets.append(
            KnowledgeTarget(
                target_id=f"{concept.concept_id}--{_slug(skill)}",
                concept_id=concept.concept_id,
                concept_name=concept.name,
                statement=statement,
                cognitive_skill=skill,
                knowledge_type=concept.knowledge_type,
                importance=concept.importance,
                evidence=evidence,
                pages=pages or concept.source_pages,
                topic=concept.topic,
                supporting_ids=supporting,
                difficulty=_SKILL_DIFFICULTY.get(skill, "medium"),
                facet_kind=facet_kind,
                answer_clause=answer_clause,
                importance_reason=reason,
            )
        )

    # 1. Reasoning targets, straight from the document's relational claims.
    #    These come first so they win the blueprint's preference ordering.
    for facet in concept.facets:
        mapping = _FACET_SKILL.get(facet.kind)
        if mapping is None:
            continue
        skill, template = mapping
        partner = ""
        if facet.kind == "contrast":
            found = _contrast_partner(concept, understanding, understanding.relationships)
            partner = found.name if found is not None else ""
        # A comparison must be answered by the distinction itself. Where the
        # document actually draws it ("Erosion differs from weathering in that
        # weathering breaks material down in place"), that sentence IS the
        # answer and must stay as the evidence -- substituting the concept's
        # definition produced "How does Erosion differ from weathering?"
        # answered by "the gradual removal of soil and rock", which never
        # states a difference.
        #
        # Only when the contrast was revealed by a sentence that asserts
        # nothing -- typically a review prompt, "What is the difference between
        # turnaround time and waiting time?" -- does the definition have to
        # stand in, because there is no stated distinction to quote.
        evidence, pages = facet.evidence, (facet.page,)
        if facet.kind == "contrast" and not _states_the_distinction(facet.evidence):
            picked = _pick_evidence(concept, None)
            if picked is None:
                continue
            evidence, pages = picked
        add(
            skill,
            template.format(name=concept.name)
            + (f" ({partner})" if partner else ""),
            evidence=evidence,
            pages=pages,
            facet_kind=facet.kind,
            answer_clause=facet.clause,
            supporting=(),
        )

    # 1a. Targets from the KNOWLEDGE GRAPH. The study map records typed edges
    #     between concepts (contrast, cause, produces, ...) with their own
    #     verbatim evidence. Previously these were only consulted to *name* a
    #     partner for a contrast facet, so a concept whose relationships lived
    #     entirely in the graph — the chapter's central "cell", which the
    #     document contrasts with prokaryotic cells — was left with nothing but
    #     its definition and produced "What is the cell?". A relationship the
    #     document actually asserts is exactly what a teacher tests, so each
    #     one becomes a target in its own right.
    for relationship in understanding.relationships:
        if relationship.source_id == concept.concept_id:
            other_id = relationship.target_id
        elif relationship.target_id == concept.concept_id and relationship.kind == "contrast":
            # Contrast is symmetric; direction-only relations are not.
            other_id = relationship.source_id
        else:
            continue
        other = understanding.concept(other_id)
        if other is None or not relationship.evidence:
            continue
        mapping = _RELATION_SKILL.get(relationship.kind)
        if mapping is None:
            continue
        # The edge must be *demonstrated* by its evidence, not merely inferred
        # from co-occurrence. Token presence is not enough: "a prokaryotic cell
        # is a cell that lacks a nucleus" contains both "nucleus" and "cell"
        # yet contrasts prokaryotic with eukaryotic cells, not the nucleus with
        # the cell. The sentence must actually be *about* this concept, which
        # is the same subject-attribution rule facets already use.
        evidence_tokens = content_tokens(relationship.evidence)
        if not content_tokens(other.name) <= evidence_tokens:
            continue
        if not _states_claim_about(concept.name, relationship.evidence):
            continue
        skill, template = mapping
        add(
            skill,
            template.format(name=concept.name, other=other.name),
            evidence=relationship.evidence,
            pages=relationship.pages,
            facet_kind=_RELATION_FACET.get(relationship.kind, ""),
            answer_clause=other.name if relationship.kind == "contrast" else "",
            supporting=(other_id,),
        )

    # 1b. A transfer target exists only where the document states an *outcome*
    #     — a purpose or effect. That stated outcome is what a learner reasons
    #     from ("what happens if this fails?"), so the question stays anchored
    #     to the source instead of inventing an external scenario. Without such
    #     a facet no application target is offered, and none can be written.
    outcome = next(
        (
            facet
            for facet in concept.facets
            if facet.kind in {"purpose", "effect"} and _states_an_outcome(facet.evidence)
        ),
        None,
    )
    if outcome is not None:
        add(
            "application",
            _statement("application", concept),
            evidence=outcome.evidence,
            pages=(outcome.page,),
            facet_kind=outcome.kind,
            answer_clause=outcome.clause,
        )

    # 1c. A misconception check: is the stated relation attached to the RIGHT
    #     concept? Built from the same facet, but answered "False" once another
    #     concept is swapped in. Without these every true/false question in a
    #     quiz is answerable with "True", which a student can game without
    #     understanding anything. Only relational facets qualify — swapping a
    #     concept inside a bare definition often yields something accidentally
    #     true.
    swappable = next(
        (
            facet
            for facet in concept.facets
            if facet.kind in {"purpose", "effect", "mechanism", "cause"}
        ),
        None,
    )
    if swappable is not None:
        add(
            "misconception",
            f"recognise whether a stated relationship really belongs to {concept.name}",
            evidence=swappable.evidence,
            pages=(swappable.page,),
            facet_kind=swappable.kind,
            answer_clause=swappable.clause,
        )

    # 2. Understanding of the concept itself is always available once it is
    #    explained, but it ranks below any reasoning target.
    picked = _pick_evidence(concept, None)
    if picked is not None:
        evidence, pages = picked
        add(
            "understanding",
            _statement("understanding", concept),
            evidence=evidence,
            pages=pages,
        )

    # 3. Recall only where the term appears verbatim in its own evidence, so a
    #    blank can be formed around a real technical term.
    if concept.knowledge_type in {"definition", "principle"} and normalize_question_text(
        concept.name
    ) in normalize_question_text(concept.primary_evidence):
        picked = _pick_evidence(concept, None)
        if picked is not None:
            evidence, pages = picked
            add(
                "factual_recall",
                _statement("factual_recall", concept),
                evidence=evidence,
                pages=pages,
            )

    return targets


def build_knowledge_targets(
    understanding: DocumentUnderstanding,
    *,
    max_concepts: int = 24,
) -> list[KnowledgeTarget]:
    """Knowledge targets for every important concept, ranked by importance.

    Deterministic: the same study map always produces the same targets in the
    same order.  Seeded variation happens later, during selection.
    """
    targets: list[KnowledgeTarget] = []
    for concept in understanding.important_concepts(limit=max_concepts):
        targets.extend(derive_targets_for_concept(concept, understanding))
    targets.sort(
        key=lambda target: (
            -target.importance,
            COGNITIVE_SKILLS.index(target.cognitive_skill)
            if target.cognitive_skill in COGNITIVE_SKILLS
            else 99,
            target.concept_name.casefold(),
        )
    )
    return targets


def targets_block(targets: list[KnowledgeTarget], limit: int = 40) -> str:
    lines = [
        f"- [{target.target_id}] concept={target.concept_name!r} ({target.concept_id}); "
        f"target={target.statement!r}; skill={target.cognitive_skill}; "
        f"pages={list(target.pages)}; evidence={target.evidence!r}"
        for target in targets[:limit]
    ]
    return "\n".join(lines) or "(no knowledge targets)"
