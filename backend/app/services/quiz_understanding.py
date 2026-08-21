"""DOCUMENT UNDERSTANDING — the semantic study map built before any question.

This module answers "what is this PDF actually teaching?" and nothing else.
It produces a :class:`DocumentUnderstanding`: a structured, evidence-grounded
model of the document containing its subject, summary, topics, concepts,
knowledge relationships, definitions, processes, comparisons, principles,
examples, and learning objectives.

Two rules make it trustworthy:

1. **Grounding.**  Every concept, relationship, and objective must resolve to
   verbatim source evidence on a page that was actually supplied.  A provider
   proposal that cannot be located in the cleaned source is discarded, so the
   study map can never contain invented material.

2. **Educational importance, never frequency.**  Importance is computed by the
   backend from explanatory depth, conceptual centrality, prerequisite role,
   teaching emphasis, knowledge type, and topic spread.  Raw repetition has a
   weight of exactly zero: a term mentioned twenty times without ever being
   explained cannot outrank a mechanism explained once.

The provider proposes structure; the backend verifies, classifies, and ranks.
A deterministic builder produces the same shape without any provider when one
is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.quiz_boilerplate import is_boilerplate_text
from app.services.quiz_concepts import SourceUnit
from app.services.quiz_grounding import (
    SourceSentence,
    evidence_normalize,
    is_generic_label,
    is_heading_like,
    is_layout_detail,
    iter_sentences,
    quote_is_grounded,
)
from app.services.quiz_scoring import (
    content_token_list,
    content_tokens,
    normalize_question_text,
)

# --------------------------------------------------------------------------- #
# Knowledge types
# --------------------------------------------------------------------------- #

KnowledgeType = Literal[
    "definition",
    "process",
    "cause_effect",
    "comparison",
    "classification",
    "principle",
    "example",
    "fact",
]

KNOWLEDGE_TYPES: tuple[str, ...] = (
    "definition",
    "process",
    "cause_effect",
    "comparison",
    "classification",
    "principle",
    "example",
    "fact",
)

#: How much a knowledge type contributes to educational importance.  A
#: mechanism or causal relationship is worth more to a learner than an
#: isolated fact, independent of how often either appears.
KNOWLEDGE_TYPE_VALUE: dict[str, float] = {
    "process": 0.95,
    "cause_effect": 0.95,
    "principle": 0.93,
    "comparison": 0.92,
    "classification": 0.88,
    "definition": 0.85,
    "fact": 0.52,
    "example": 0.45,
}

#: Types that may carry a quiz question at all.  Examples are a small
#: supplement; bare facts are only usable when strongly explained.
TEACHABLE_TYPES: frozenset[str] = frozenset(
    {"definition", "process", "cause_effect", "comparison", "classification", "principle"}
)

#: The minimum importance a concept needs before it can drive a question.
#: Calibrated so that a well-explained definition/process/comparison clears it
#: on its own merits, while an isolated fact or example never can — even in a
#: one-page document where every other signal is necessarily zero.
IMPORTANCE_FLOOR = 0.60

#: Below this many question-worthy concepts, a document is too small for
#: "developed vs merely defined" to be a real distinction: the handful of terms
#: it defines are the whole syllabus.
_DEVELOPMENT_GATE_MIN_CONCEPTS = 6

#: How close to a document's typical strong concept another concept must score
#: before it is treated as exam-worthy.
#:
#: This is a backstop, not the main filter. Excluding passing asides is the job
#: of ``is_developed``, which asks whether the document does anything with the
#: concept. This ratio only removes the clearly-trailing tail, so it is set
#: loose: a legitimately taught supporting concept (the Golgi apparatus in a
#: cell-biology chapter) scores well below the chapter's headline concept and
#: must still be examinable.
RELATIVE_IMPORTANCE_RATIO = 0.62

#: Importance ceiling for a concept that is mentioned but never explained.
UNEXPLAINED_CEILING = 0.30
EXAMPLE_CEILING = 0.60


# --------------------------------------------------------------------------- #
# Study-map model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Evidence:
    """One verbatim source span and the page it was found on."""

    text: str
    page: int

    @property
    def tokens(self) -> set[str]:
        return content_tokens(self.text)


#: Kinds of relational claim a document can make about a concept.  These are
#: what make reasoning questions possible: without a stated purpose there is no
#: honest "why does it matter?", and without a stated contrast there is no
#: honest "how do X and Y differ?".
FACET_KINDS: tuple[str, ...] = (
    "purpose",     # what it is for / what it enables
    "cause",       # why it happens / what drives it
    "effect",      # what results from it
    "mechanism",   # how it works, step by step
    "contrast",    # how it differs from something else
    "category",    # what it divides into
    "condition",   # what it requires / depends on
)


@dataclass(frozen=True)
class Facet:
    """One relational claim the document makes about a concept.

    ``clause`` is the substantive half of the claim (the purpose, the cause,
    the outcome), already separated from the framing verb, so a question can
    be built around it without re-parsing the sentence.
    """

    kind: str
    clause: str
    evidence: str
    page: int
    partner: str = ""

    @property
    def tokens(self) -> set[str]:
        return content_tokens(self.clause)


@dataclass(frozen=True)
class ConceptNode:
    """A single thing the document teaches, with why it matters."""

    concept_id: str
    name: str
    description: str
    topic: str
    knowledge_type: str
    importance: float
    learning_value: float
    evidence: tuple[Evidence, ...]
    source_pages: tuple[int, ...]
    prerequisites: tuple[str, ...] = ()
    related_concepts: tuple[str, ...] = ()
    signals: dict[str, float] = field(default_factory=dict)
    mention_count: int = 0
    explained: bool = True
    rationale: str = ""
    #: Relational claims the document makes about this concept.
    facets: tuple[Facet, ...] = ()

    @property
    def primary_evidence(self) -> str:
        return self.evidence[0].text if self.evidence else ""

    def facet(self, kind: str) -> Facet | None:
        for item in self.facets:
            if item.kind == kind:
                return item
        return None

    @property
    def facet_kinds(self) -> frozenset[str]:
        return frozenset(item.kind for item in self.facets)

    @property
    def is_developed(self) -> bool:
        """Does the document *develop* this concept, or merely name it?

        Development means the document does something with the concept beyond
        stating what it is: explains how it works, why it matters, what it
        causes, how it contrasts with something else (a facet); or returns to
        it elsewhere (centrality, prerequisite role, multi-page treatment); or
        flags it as important (teaching emphasis).

        A term that is defined once and never touched again — "a program is a
        passive entity stored on disk" in a chapter about scheduling — is real
        content but not exam material. Requiring development is what separates
        the two, and it is a property of the *document's treatment*, so it
        stays subject-neutral.
        """
        signals = self.signals
        return bool(
            self.facets
            or signals.get("centrality", 0.0) >= 0.30
            or signals.get("teaching_emphasis", 0.0) >= 0.25
            or signals.get("prerequisite_role", 0.0) > 0.0
            or signals.get("topic_spread", 0.0) >= 0.50
        )

    @property
    def question_worthy(self) -> bool:
        if not self.explained or not self.evidence:
            return False
        if self.knowledge_type in TEACHABLE_TYPES:
            return self.importance >= IMPORTANCE_FLOOR
        # Examples are a small supplement and must be unusually well explained.
        return self.knowledge_type == "example" and self.importance >= 0.56

    def key(self) -> str:
        return normalize_question_text(self.name)


@dataclass(frozen=True)
class Relationship:
    """A taught connection between two concepts (cause, part-of, contrast...)."""

    source_id: str
    target_id: str
    kind: str
    evidence: str
    pages: tuple[int, ...]


@dataclass(frozen=True)
class Topic:
    """A major area of the document and the concepts that live inside it."""

    name: str
    subtopics: tuple[str, ...]
    concept_ids: tuple[str, ...]
    pages: tuple[int, ...]


@dataclass(frozen=True)
class LearningObjective:
    """What a learner should be able to do after studying the document."""

    text: str
    concept_ids: tuple[str, ...]
    pages: tuple[int, ...]


@dataclass(frozen=True)
class DocumentUnderstanding:
    """The semantic study map: what the document is about, before any quiz."""

    title: str
    subject: str
    summary: str
    main_topics: tuple[Topic, ...]
    concepts: tuple[ConceptNode, ...]
    relationships: tuple[Relationship, ...]
    learning_objectives: tuple[LearningObjective, ...]
    source: str = "provider"

    # -- typed views ------------------------------------------------------- #
    def _by_type(self, knowledge_type: str) -> tuple[ConceptNode, ...]:
        return tuple(c for c in self.concepts if c.knowledge_type == knowledge_type)

    @property
    def definitions(self) -> tuple[ConceptNode, ...]:
        return self._by_type("definition")

    @property
    def processes(self) -> tuple[ConceptNode, ...]:
        return self._by_type("process")

    @property
    def comparisons(self) -> tuple[ConceptNode, ...]:
        return self._by_type("comparison")

    @property
    def principles(self) -> tuple[ConceptNode, ...]:
        return self._by_type("principle")

    @property
    def classifications(self) -> tuple[ConceptNode, ...]:
        return self._by_type("classification")

    @property
    def examples(self) -> tuple[ConceptNode, ...]:
        return self._by_type("example")

    def concept(self, concept_id: str) -> ConceptNode | None:
        for node in self.concepts:
            if node.concept_id == concept_id:
                return node
        return None

    def important_concepts(self, limit: int = 24) -> list[ConceptNode]:
        """Concepts ranked by educational importance, question-worthy only.

        Two gates apply. ``question_worthy`` is absolute: is this teachable
        content at all? The second is *relative*: a concept must hold up
        against what else this document teaches. A passing remark such as "a
        program is a passive entity stored on disk" is a real definition and
        clears the absolute bar, yet next to the chapter's scheduling
        algorithms it is plainly not exam material. Only comparison within the
        document can make that distinction.
        """
        ranked = [node for node in self.concepts if node.question_worthy]
        ranked.sort(key=lambda node: (-node.importance, -node.learning_value, node.name.casefold()))

        # Require development only where the document is rich enough for the
        # distinction to be meaningful. In a short handout the few concepts it
        # defines *are* the syllabus, and there is no room for any of them to
        # demonstrate centrality or multi-page treatment.
        if len(ranked) > _DEVELOPMENT_GATE_MIN_CONCEPTS:
            developed = [node for node in ranked if node.is_developed]
            if len(developed) >= 3:
                ranked = developed

        if len(ranked) > 3:
            # Measure against a typical strong concept rather than the single
            # best, which is often an outlier that absorbs the document's
            # cross-references.
            leading = ranked[: max(3, min(8, len(ranked)))]
            reference = leading[len(leading) // 2].importance
            cutoff = reference * RELATIVE_IMPORTANCE_RATIO
            kept = [node for node in ranked if node.importance >= cutoff]
            # Never let the relative gate starve a document of material.
            if len(kept) >= 3:
                ranked = kept
        return ranked[:limit]

    @property
    def is_usable(self) -> bool:
        return bool(self.important_concepts(limit=1))


# --------------------------------------------------------------------------- #
# Provider request/response shapes
# --------------------------------------------------------------------------- #


class _RawConcept(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    name: str = ""
    description: str = ""
    topic: str = ""
    knowledge_type: str = ""
    teaching_emphasis: str = "medium"
    evidence_quotes: list[str] = Field(default_factory=list)
    source_pages: list[Any] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    knowledge_targets: list[str] = Field(default_factory=list)
    why_important: str = ""


class _RawRelationship(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    source: str = ""
    target: str = ""
    kind: str = ""
    evidence: str = ""
    source_pages: list[Any] = Field(default_factory=list)


class _RawTopic(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = ""
    subtopics: list[str] = Field(default_factory=list)
    concept_ids: list[str] = Field(default_factory=list)
    source_pages: list[Any] = Field(default_factory=list)


class _RawObjective(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    text: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    source_pages: list[Any] = Field(default_factory=list)


class _RawUnderstanding(BaseModel):
    """Lenient provider shape.  Every field is verified before it is trusted."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    subject: str = ""
    summary: str = ""
    main_topics: list[_RawTopic] = Field(default_factory=list)
    concepts: list[_RawConcept] = Field(default_factory=list)
    relationships: list[_RawRelationship] = Field(default_factory=list)
    learning_objectives: list[_RawObjective] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Deterministic linguistic signals
# --------------------------------------------------------------------------- #

_DEFINITION_MARKERS = re.compile(
    r"\b(is|are)\s+defined\s+as\b|\brefers?\s+to\b|\bis\s+known\s+as\b|\bis\s+called\b|"
    r"\bmeans\s+that\b|\bis\s+the\s+(?:study|process|term|name)\b|\bcan\s+be\s+defined\b|"
    r"يعرف|تعرف|يقصد ب|هو عباره عن|هي عباره عن",
    re.IGNORECASE,
)
_PROCESS_MARKERS = re.compile(
    r"\b(process|procedure|mechanism|steps?|stages?|phases?|cycle|sequence|first|then|next|"
    r"finally|proceeds?|converts?|synthes\w+|assembl\w+|produces?|generates?|transforms?|"
    r"replicat\w+|transcrib\w+|translat\w+|iterat\w+)\b|"
    r"عمليه|خطوات|مراحل|اليه|يتم انتاج|يتم تحويل",
    re.IGNORECASE,
)
_CAUSE_MARKERS = re.compile(
    r"\b(because|therefore|thus|hence|causes?|caused by|leads? to|results? in|due to|"
    r"depends? on|so that|consequently|if\b.{0,60}\bthen|increases?|decreases?|affects?|"
    r"enables?|prevents?|allows?)\b|يسبب|يودي الي|بسبب|نتيجه|لذلك|يعتمد علي|يمنع|يسمح",
    re.IGNORECASE,
)
_COMPARISON_MARKERS = re.compile(
    r"\b(unlike|whereas|while\b.{0,60}\b(?:but|however)|in contrast|compared (?:to|with)|"
    r"differs? from|difference between|similar to|both\b.{0,40}\band\b|rather than|"
    r"instead of|distinguish\w*)\b|على عكس|بينما|مقارنه|يختلف عن|الفرق بين",
    re.IGNORECASE,
)
_CLASSIFICATION_MARKERS = re.compile(
    r"\b(types? of|kinds? of|categor\w+|classif\w+|divided into|consists? of|"
    r"grouped into|forms? of|exists? in two)\b|انواع|تصنيف|ينقسم الي|يتكون من",
    re.IGNORECASE,
)
_PRINCIPLE_MARKERS = re.compile(
    r"\b(law of|principle|theorem|rule|axiom|postulate|states? that|equation|formula|"
    r"must always|never|theory states)\b|=|قانون|مبدا|نظريه|قاعده|معادله",
    re.IGNORECASE,
)
_EXAMPLE_MARKERS = re.compile(
    r"\b(for example|for instance|such as|e\.g\.|as an example|consider the case|"
    r"commonly (?:called|remembered|abbreviated)|mnemonic)\b|مثال|علي سبيل المثال",
    re.IGNORECASE,
)
_OBJECTIVE_MARKERS = re.compile(
    r"\b(learning objectives?|you will be able to|by the end of|students? (?:should|must|will)"
    r"(?: be able)? (?:be able to|explain|describe|distinguish|understand|know)|"
    r"should be able to|preparing for an exam)\b|"
    r"الهدف التعليمي|سوف تتعلم|في نهايه هذا",
    re.IGNORECASE,
)
_EMPHASIS_MARKERS = re.compile(
    r"\b(important|essential|key|fundamental|central|crucial|most frequently tested|"
    r"remember that|note that|in summary|to summari[sz]e|most difficult|exam tip)\b|"
    r"مهم|اساسي|جوهري|تذكر|باختصار",
    re.IGNORECASE,
)


def infer_knowledge_type(text: str) -> str:
    """Classify what kind of knowledge a source span teaches."""
    if _DEFINITION_MARKERS.search(text):
        return "definition"
    if _COMPARISON_MARKERS.search(text):
        return "comparison"
    if _CAUSE_MARKERS.search(text):
        return "cause_effect"
    if _CLASSIFICATION_MARKERS.search(text):
        return "classification"
    if _PROCESS_MARKERS.search(text):
        return "process"
    if _PRINCIPLE_MARKERS.search(text):
        return "principle"
    if _EXAMPLE_MARKERS.search(text):
        return "example"
    return "fact"


def _canonical_type(value: str, evidence: str) -> str:
    key = re.sub(r"[\s/\-]+", "_", (value or "").strip().lower())
    aliases = {
        "core_concept": "definition",
        "central_concept": "definition",
        "concept": "definition",
        "definition": "definition",
        "important_definition": "definition",
        "term": "definition",
        "process": "process",
        "mechanism": "process",
        "process_mechanism": "process",
        "procedure": "process",
        "cause_effect": "cause_effect",
        "causal": "cause_effect",
        "cause": "cause_effect",
        "relationship": "cause_effect",
        "comparison": "comparison",
        "contrast": "comparison",
        "distinction": "comparison",
        "classification": "classification",
        "category": "classification",
        "taxonomy": "classification",
        "principle": "principle",
        "rule": "principle",
        "law": "principle",
        "formula": "principle",
        "formula_rule": "principle",
        "theorem": "principle",
        "example": "example",
        "illustration": "example",
        "fact": "fact",
        "detail": "fact",
    }
    canonical = aliases.get(key)
    if canonical:
        return canonical
    return infer_knowledge_type(evidence)


# --------------------------------------------------------------------------- #
# Evidence selection
# --------------------------------------------------------------------------- #


def _is_teaching_sentence(sentence: str) -> bool:
    """A usable evidence span asserts something about the subject."""
    if len(sentence) < 25:
        return False
    if is_boilerplate_text(sentence) or is_layout_detail(sentence):
        return False
    if is_heading_like(sentence):
        return False
    return len(content_tokens(sentence)) >= 5


#: Words a model bolts onto a concept label without changing which concept it
#: names ("the process of mitosis", "Mitosis mechanism"). Stripping them lets a
#: canonicalised provider label still be matched against the page's own
#: wording. Deliberately generic and subject-neutral -- nothing here is
#: specific to biology, databases, or any other field.
_LABEL_QUALIFIERS = frozenset(
    {
        "process",
        "processes",
        "mechanism",
        "mechanisms",
        "concept",
        "concepts",
        "principle",
        "principles",
        "method",
        "methods",
        "technique",
        "techniques",
        "operation",
        "operations",
        "procedure",
        "procedures",
        "stage",
        "stages",
        "phase",
        "phases",
        "step",
        "steps",
        "type",
        "types",
        "kind",
        "kinds",
        "form",
        "forms",
        "structure",
        "structures",
        "system",
        "systems",
        "model",
        "models",
        "theory",
        "overview",
        "introduction",
        "definition",
        "example",
        "examples",
    }
)


def _concept_sentences(
    name: str, sentences: list[SourceSentence], *, limit: int = 6
) -> list[SourceSentence]:
    """Sentences that talk about a concept, best-explaining first."""
    key_tokens = content_tokens(name)
    if not key_tokens:
        return []
    # A provider rarely echoes the page's exact surface wording. It
    # canonicalises: the slide says "Mitosis", the model returns "the process
    # of mitosis" or "Mitosis mechanism". Requiring 60% of *every* token of
    # that expanded label to appear in one sentence discarded the concept
    # entirely -- measured at 30 -> 11 surviving concepts on a 32-page deck,
    # which is how an 8-question exam collapsed to one.
    #
    # The distinctive tokens are what identify the concept; generic qualifiers
    # a model bolts on ("process", "mechanism", "concept") carry no identity.
    # Match on the distinctive part, and keep the strict rule as the preferred,
    # higher-scoring signal rather than the only admissible one.
    distinctive = key_tokens - _LABEL_QUALIFIERS
    match_tokens = distinctive or key_tokens
    normalized_name = normalize_question_text(name)
    matches: list[tuple[float, SourceSentence]] = []
    for sentence in sentences:
        normalized = normalize_question_text(sentence.text)
        tokens = sentence.tokens
        overlap = len(key_tokens & tokens) / len(key_tokens)
        # Fall back to the distinctive tokens when the full label does not fit.
        if overlap < 0.6 and match_tokens:
            overlap = max(overlap, len(match_tokens & tokens) / len(match_tokens))
        if normalized_name and normalized_name in normalized:
            overlap = max(overlap, 1.0)
        if overlap < 0.6:
            continue
        if not _is_teaching_sentence(sentence.text):
            continue
        weight = overlap + min(1.0, len(tokens) / 30)
        if _DEFINITION_MARKERS.search(sentence.text):
            weight += 0.8
        if _EMPHASIS_MARKERS.search(sentence.text):
            weight += 0.2
        matches.append((weight, sentence))
    matches.sort(key=lambda item: (-item[0], item[1].order))
    return [sentence for _, sentence in matches[:limit]]


# --------------------------------------------------------------------------- #
# Facet extraction: the relational claims that make reasoning questions possible
# --------------------------------------------------------------------------- #

#: Each pattern captures the *clause* that follows a relational connective.
#: Order matters: more specific connectives are tried first.
_FACET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "purpose",
        re.compile(
            r"\b(?:is|are)\s+used\s+(?:for|in|specifically\s+in|to)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "purpose",
        re.compile(r"\bresponsible\s+for\s+(?P<clause>[^.;]{8,140})", re.IGNORECASE),
    ),
    (
        # "... which is particularly important for interactive systems",
        # "... essential for correctly applying the law". A document saying
        # where something matters is stating its purpose, and that is the
        # reason that turns "What is Response time?" into "Why does response
        # time matter?" — the escalation the spec asks for. The reason comes
        # from the source; nothing is invented when it is absent.
        "purpose",
        re.compile(
            # Only "for"/"to" are taken. "useful IN physics, economics, and
            # engineering" names a field of application, so dropping the
            # preposition leaves a bare list ("physics, economics, and
            # engineering, where ...") that answers "why is X important?"
            # ungrammatically. "important for X" / "essential to X" state a
            # purpose whose object stands alone.
            r"\b(?:particularly\s+|especially\s+|critically\s+)?"
            r"(?:important|essential|critical|crucial|vital|necessary)\s+"
            r"(?:for|to)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # A definitional relative clause states what the thing *does*:
        # "an organelle that modifies, sorts, and packages proteins".
        #
        # Only a *subject* relative clause does this. In "the value that a
        # function approaches", the head noun is the object of the verb and the
        # clause says what the thing *is*, not what it accomplishes — reading it
        # as a purpose yields "The limit is responsible for a function f(x)
        # approaches…". A determiner or pronoun right after "that" marks that
        # object-relative shape, so those are excluded.
        "purpose",
        re.compile(
            r"\b(?:is|are)\s+(?:defined\s+as\s+)?(?:the|a|an)\s+[^.;]{0,40}?"
            # The verb may be followed by a comma in a coordinated list
            # ("that modifies, sorts, and packages proteins"), so do not
            # require whitespace immediately after it.
            r"\bthat\s+(?!(?:a|an|the|its?|his|her|their|our|your|my|this|these|those|"
            r"they|we|you|he|she|one|any|each|every|some|all|both|either|neither)\b)"
            r"(?P<clause>[a-z]+\b[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "purpose",
        re.compile(
            r"\bso\s+that\s+(?P<clause>[^.;]{8,140})|"
            r"\bin\s+order\s+to\s+(?P<clause2>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "cause",
        re.compile(
            r"\bbecause\s+(?:of\s+)?(?P<clause>[^.;]{8,140})|"
            r"\bdue\s+to\s+(?P<clause2>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # "X states that <clause>" is how a document teaches a law, rule, or
        # theorem. The clause IS the content of the rule, so it supports a real
        # "what does X state / predict?" question rather than a definition
        # lookup. Subject-neutral: laws, theorems, and principles are phrased
        # this way across physics, mathematics, economics, and law alike.
        "mechanism",
        re.compile(
            r"\b(?:states?|asserts?|holds?|establishes?|specifies?)\s+that\s+"
            # Stop at a colon or dash: what follows is elaboration, and a law's
            # statement is the part before it. Without this the clause runs past
            # the length limit and the whole facet is lost.
            r"(?P<clause>[^.;:—]{10,160})",
            re.IGNORECASE,
        ),
    ),
    (
        # "X is used to/for <clause>" and "X is used in <clause>" state what a
        # tool or technique accomplishes.
        "purpose",
        re.compile(
            r"\b(?:is|are)\s+used\s+(?:to|for|in|when)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # "X is essential/used/needed for <clause>" states what X is for.
        "purpose",
        re.compile(
            r"\b(?:is|are)\s+(?:essential|necessary|required|needed|useful|important|"
            r"critical|crucial|vital|suited|suitable)\s+(?:for|to|in)\s+"
            r"(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # A transitive predicate names what the concept does to what:
        # "assigns each process a fixed time slice", "partitions the ready queue".
        "mechanism",
        re.compile(
            r"(?<!to )(?<!To )"
            r"(?P<clause>(?:assigns?|allocates?|partitions?|divides?|separates?|"
            r"selects?|schedules?|maintains?|stores?|tracks?|computes?|calculates?|"
            r"measures?|relates?|converts?|transforms?|organis(?:es?|ing)|"
            r"organiz(?:es?|ing))\s+[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # "X forms where/when Y", "X occurs when Y", "X arises when Y": the
        # document states the circumstance under which the thing comes about.
        # This is the standard way process/landform/phenomenon concepts are
        # taught, and without it such a concept has no facet at all -- it was
        # then scored as merely mentioned and dropped, so documents that teach
        # through conditions produced far fewer questions than they support.
        # Connective-driven, so it is subject-neutral.
        "condition",
        re.compile(
            r"\b(?:forms?|occurs?|arises?|happens?|develops?|appears?|emerges?|"
            r"begins?|results?)\s+(?:when|where|whenever|wherever|if)\s+"
            r"(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # "exists if and only if …", "applies when …" state the governing condition.
        "condition",
        re.compile(
            r"\b(?:if\s+and\s+only\s+if|applies?\s+(?:only\s+)?when|holds?\s+when|"
            r"provided\s+that|as\s+long\s+as)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "effect",
        re.compile(
            r"\b(?:leads?\s+to|results?\s+in|can\s+lead\s+to|causes?|produces?|generates?|"
            r"ensuring|ensures?|allows?|enables?|prevents?)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        # "by/through/via <clause>" states a mechanism — but only when the
        # preposition is not part of a phrasal verb. In "cycles through all
        # processes" the "through" belongs to "cycles", and the phrase names
        # what is traversed, not how the thing works.
        "mechanism",
        re.compile(
            r"(?<!\bcycles)(?<!\bcycle)(?<!\bgoes)(?<!\bgo)(?<!\bpasses)(?<!\bpass)"
            r"(?<!\bmoves)(?<!\bmove)(?<!\bruns)(?<!\brun)(?<!\bloops)(?<!\bloop)"
            r"(?<!\biterates)(?<!\biterate)(?<!\bsearches)(?<!\bsearch)"
            r"(?<!\bscans)(?<!\bscan)(?<!\bsorts)(?<!\bsort)"
            r"\s\b(?:by|through|via)\s+(?P<clause>(?:which\s+)?[^.;]{10,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "condition",
        re.compile(
            r"\b(?:relies\s+on|depends\s+on|requires?|needs?)\s+(?P<clause>[^.;]{8,140})",
            re.IGNORECASE,
        ),
    ),
    (
        "category",
        re.compile(
            r"\b(?:exists?\s+in|divided\s+into|classified\s+into|grouped\s+into|"
            r"consists?\s+of)\s+(?P<clause>[^.;]{6,140})",
            re.IGNORECASE,
        ),
    ),
)

#: "X differs from Y in that ..." / "X differs from Y, while ...". The compared
#: thing is named right after "differ(s) from", so capture it directly. Without
#: this, the general pattern below matched the *explanatory* clause introduced
#: by "while"/"whereas" and handed the writer a sentence ("most covalent
#: compounds do not") where a noun phrase belongs -- which the writer then
#: correctly refused, silently losing the comparison target altogether.
_CONTRAST_PARTNER = re.compile(
    r"\bdiffers?\s+from\s+(?P<clause>[^.;,]{3,60}?)"
    r"(?=\s+(?:in\s+that|in\s+which|because|since|whereas|while|by|through)\b"
    r"|[.;,]|$)",
    re.IGNORECASE,
)


_CONTRAST_PATTERN = re.compile(
    r"\b(?:unlike|in\s+contrast\s+to|compared\s+(?:to|with)|whereas|while)\s+(?P<clause>[^.;,]{6,120})"
    r"|\b(?P<lead>[^.;,]{6,120}?),?\s+(?:whereas|while)\s+(?P<clause2>[^.;]{8,140})",
    re.IGNORECASE,
)

#: What a facet proves about the concept it belongs to. Ordered: the first
#: match wins, so the most explanatory relation decides the type.
_FACET_KNOWLEDGE_TYPE: dict[str, str] = {
    "mechanism": "process",
    "cause": "cause_effect",
    "effect": "cause_effect",
    "condition": "cause_effect",
    "contrast": "comparison",
    "category": "classification",
    "purpose": "principle",
}


#: A clause that is only scaffolding carries no testable content.
_EMPTY_CLAUSE = re.compile(r"^(?:it|this|that|them|these|those|which|such)\b", re.IGNORECASE)


#: A coordinate clause introducing a *different* subject: "... is responsible
#: for protein synthesis, while the smooth endoplasmic reticulum lacks
#: ribosomes". The contrast is a claim about the other thing, so carrying it
#: into this concept's answer makes the answer partly about something else.
_CONTRASTED_CLAUSE = re.compile(
    r",\s+(?:while|whereas|but|although|though|unlike)\s+", re.IGNORECASE
)


def _clean_clause(text: str) -> str:
    clause = re.sub(r"\s+", " ", text or "").strip(" ,;:.-—")
    clause = re.sub(r"^(?:which\s+|that\s+)", "", clause, flags=re.IGNORECASE).strip()
    contrast = _CONTRASTED_CLAUSE.search(clause)
    if contrast:
        # Keep the part before the contrast whenever anything is left. Even a
        # two-word head ("protein synthesis") is a better answer than one that
        # trails into a claim about a different subject; if nothing usable
        # remains, _usable_clause drops the facet.
        head = clause[: contrast.start()].strip(" ,;:.-—")
        if head:
            clause = head
    return clause


#: Talk about the *reader* rather than the subject matter. "students find this
#: difficult" is pedagogical commentary, not a claim a question can test.
_LEARNER_COMMENTARY = re.compile(
    r"\b(?:students?|learners?|readers?|beginners?|novices?|you)\b", re.IGNORECASE
)

#: A clause cut mid-construction: it ends on a word that must be followed by
#: more ("…since it requires", "…and is one of the"). Asserting it is asserting
#: a fragment.
_TRUNCATED_TAIL = re.compile(
    r"\b(?:requires?|includes?|means?|involves?|allows?|causes?|becomes?|"
    r"produces?|creates?|needs?|uses?|gives?|makes?|takes?|the|a|an|of|to|in|"
    r"for|with|by|from|that|which|and|or|but|as|than|is|are|was|were|be|been)\s*$",
    re.IGNORECASE,
)


#: A relational clause is normally a phrase, but a law or rule is stated as one
#: indivisible sentence ("an object at rest stays at rest and an object in
#: motion stays in motion ... unless acted upon by an unbalanced external
#: force"). Capping at phrase length discarded those outright, losing the
#: concept from the exam; the writer shortens where it safely can and otherwise
#: presents the full statement.
_MAX_CLAUSE_WORDS = 40


def _usable_partner(clause: str) -> bool:
    """Is this a usable *contrast partner*, i.e. the other thing compared?

    A partner is a name, so unlike a descriptive clause it is often a single
    word ("weathering", "militarism", "a symbol"). _usable_clause's two-word
    floor exists to reject descriptive stubs and would throw these away, taking
    the whole comparison target with them -- so apply the substance checks
    without the length floor.
    """
    cleaned = clause.strip()
    if not cleaned or len(cleaned.split()) > _MAX_CLAUSE_WORDS:
        return False
    if _EMPTY_CLAUSE.match(cleaned):
        return False
    if _LEARNER_COMMENTARY.search(cleaned) or _TRUNCATED_TAIL.search(cleaned):
        return False
    return bool(content_tokens(cleaned))


def _usable_clause(clause: str) -> bool:
    # Two content words are enough when both carry meaning ("interactive
    # systems", "lipid synthesis"). The floor exists to reject stubs like "the
    # cell", not to reject short but fully specified objects; the
    # content-token check at the end is what actually enforces substance.
    words = len(clause.split())
    if words < 2 or words > _MAX_CLAUSE_WORDS:
        return False
    if words == 2 and len(content_tokens(clause)) < 2:
        return False
    if _EMPTY_CLAUSE.match(clause):
        return False
    # A clause about the learner, or one cut mid-construction, cannot carry a
    # question: neither states a fact about the subject matter.
    if _LEARNER_COMMENTARY.search(clause) or _TRUNCATED_TAIL.search(clause):
        return False
    return len(content_tokens(clause)) >= 2


#: A subordinate clause opening the sentence, up to the comma that closes it.
#: What follows the comma carries the sentence's actual claim.
#: The subordinators recognised above, as a single-token test. A subordinator
#: opens a new clause, so a concept name can never continue through one.
_SUBORDINATOR_TOKEN = re.compile(
    r"^(?:although|though|while|whereas|whilst|if|unless|when|whenever|because|"
    r"since|after|before|until|so|that|which|who|whose|where|why|how)$",
    re.IGNORECASE,
)


_LEADING_SUBORDINATE = re.compile(
    r"^\s*(?:although|though|even\s+though|while|whereas|whilst|if|unless|"
    r"when|whenever|because|since|as\s+long\s+as|provided\s+that|"
    r"in\s+order\s+that|so\s+that|after|before|until)\b[^,]{3,120},\s*",
    re.IGNORECASE,
)


def sentence_subject(text: str) -> str:
    """The noun phrase a sentence is making a claim *about*.

    A relational claim belongs to the sentence's subject. "Meiosis ... is used
    in the production of gametes" states meiosis's purpose; it says nothing
    about "cell", even though the word appears inside "daughter cells".
    Attributing by mere token presence is what let facets bleed between
    concepts, so attribution goes through the subject instead.
    """
    # A leading subordinate clause is background, not the claim. "Although the
    # speed is constant, the direction of velocity is changing" asserts
    # something about the direction; treating "speed" as the subject would
    # attribute the whole sentence to a concept it merely concedes. This runs
    # before adverb stripping, which would otherwise remove the very
    # conjunction that marks the clause as subordinate.
    stripped = text.strip()
    subordinate = _LEADING_SUBORDINATE.match(stripped)
    if subordinate:
        stripped = stripped[subordinate.end():].strip()
    stripped = _LEADING_ADVERB.sub("", stripped, count=1)
    stripped = _DISCOURSE_OPENER.sub("", stripped, count=1).strip()
    match = _SUBJECT_HEAD.match(stripped)
    if not match:
        return ""
    return _trim_to_subject(
        _LEADING_DETERMINER.sub("", match.group(1).strip()).strip(),
        stripped[match.end(1):],
    )


#: A sentence opening with one of these refers back to the previous sentence's
#: subject ("The Golgi apparatus is ... It functions much like a shipping
#: centre."). Resolving them recovers claims that would otherwise be lost.
#: "the organelle" was a biology-specific hack; a category noun works for any
#: subject ("the algorithm", "the theorem", "the reaction"), so match the
#: *shape* — a determiner plus a single generic category noun — instead.
_ANAPHORIC_SUBJECT = re.compile(
    r"^\s*(?:it|they|this|these|"
    r"the\s+(?:process|structure|organelle|component|mechanism|algorithm|"
    r"method|technique|rule|law|principle|theorem|reaction|system|device|"
    r"element|compound|molecule|enzyme|force|function|operation|procedure|"
    r"phenomenon|concept|term|quantity|value|unit|stage|phase|step))\b",
    re.IGNORECASE,
)


#: Tokens that can pad a subject without making it name something else, so
#: "the mitochondria of the cell" still counts as a claim about mitochondria.
_GRAMMATICAL_MODIFIERS = frozenset(
    """the a an this that these those its their his her our your my
    of in on at for to from with by within inside outside
    such same other another each every both all any some
    cell cells organism organisms system systems""".split()
)


def _states_claim_about(concept_name: str, sentence: str) -> bool:
    """True when this sentence's subject is the concept in question."""
    subject = sentence_subject(sentence)
    if not subject:
        return False
    concept_key = normalize_question_text(concept_name)
    subject_key = normalize_question_text(subject)
    if not concept_key or not subject_key:
        return False
    # Accept an exact subject match or a subject that is a compound naming the
    # concept ("Mitochondria" / "The mitochondria of the cell").
    if concept_key == subject_key:
        return True
    concept_tokens = content_tokens(concept_name)
    subject_tokens = content_tokens(subject)
    if not concept_tokens or not concept_tokens <= subject_tokens:
        return False
    # A subject that adds a *qualifier* names a different, more specific thing:
    # "the first derivative test" is not "the derivative", and "kinetic
    # friction" is not "friction". Claims about the specific thing must not be
    # attributed to the general one, or a concept inherits statements the
    # document never made about it. A purely grammatical extra ("the ... of the
    # cell") is not a qualifier, so those still attach.
    extra = subject_tokens - concept_tokens
    return not (extra - _GRAMMATICAL_MODIFIERS)


def _attributable_sentences(
    name: str, sentences: list[SourceSentence]
) -> list[SourceSentence]:
    """Sentences whose claims belong to this concept, resolving pronouns.

    A sentence qualifies when the concept is its grammatical subject, or when
    it opens with a pronoun and the immediately preceding sentence was about
    the concept.
    """
    by_order = {sentence.order: sentence for sentence in sentences}
    attributed: list[SourceSentence] = []
    for sentence in _concept_sentences(name, sentences, limit=10):
        if _states_claim_about(name, sentence.text):
            attributed.append(sentence)
    direct_orders = {sentence.order for sentence in attributed}

    # One hop of anaphora: "<Concept> is ... . It does X."
    for order in sorted(direct_orders):
        follower = by_order.get(order + 1)
        if (
            follower is not None
            and follower.page == by_order[order].page
            and _ANAPHORIC_SUBJECT.match(follower.text)
            and follower.order not in direct_orders
        ):
            attributed.append(follower)
    attributed.sort(key=lambda sentence: sentence.order)
    return attributed


def _mention_end(name: str, text: str) -> int:
    """Index just past the concept's mention in ``text`` (0 when absent)."""
    match = re.search(rf"\b{re.escape(name.strip())}\b", text, re.IGNORECASE)
    return match.end() if match else 0


#: A clause boundary followed by a new noun-phrase subject and its verb. Text
#: after such a boundary is about something else.
_NEW_SUBJECT = re.compile(
    r"[,;]\s+(?:and\s+|but\s+|while\s+|whereas\s+)?"
    r"(?:the|a|an)?\s*[a-z][\w'’\-]*(?:\s+[a-z][\w'’\-]+){0,2}\s+"
    r"(?:is|are|was|were|has|have|requires?|needs?|depends?|measures?|describes?|"
    r"indicates?|means?|refers?|states?|uses?|allows?|ensures?|provides?)\b",
    re.IGNORECASE,
)


def _other_subject_intervenes(text: str, mention_end: int, match_start: int) -> bool:
    """True when a different subject takes over between the mention and the match.

    Long summary sentences chain claims about several concepts. Only the span
    before the next subject belongs to this concept.
    """
    if mention_end <= 0 or match_start <= mention_end:
        return False
    # A non-restrictive relative clause comments on the main clause, so its
    # claim belongs to the sentence's subject: "Response time is defined as the
    # time ..., WHICH is particularly important for interactive systems" says
    # response time is what matters for those systems. Everything before the
    # ", which" is that subject's own definition, so subjects appearing inside
    # it are not rivals. Only applied when the relative clause really does open
    # after the mention and the match sits inside it.
    relative = None
    for candidate in re.finditer(r",\s+which\s+", text, re.IGNORECASE):
        if mention_end <= candidate.start() < match_start:
            relative = candidate
    start = relative.end() if relative is not None else mention_end
    if _NEW_SUBJECT.search(text, start, match_start):
        return True
    # The rival subject may be detected only by the verb that the facet pattern
    # itself matched: "a limit describes ..., continuity REQUIRES that a
    # function have no gaps" -- the "condition" pattern fires on "requires",
    # which is the new subject's own verb, so a window ending at match_start
    # stops one word short and the clause is credited to the wrong concept.
    # Widening the window past that verb lets the guard see the switch.
    lookahead = _NEW_SUBJECT.search(text, start)
    return bool(lookahead and lookahead.start() < match_start <= lookahead.end())


#: Words that flip or suspend a claim. A relation captured downstream of one of
#: these is not asserted by the document at all: "stays in motion *unless*
#: acted upon by an unbalanced force" does not state that the law operates by
#: means of that force — it states the opposite.
_NEGATING_CONTEXT = re.compile(
    r"\b(?:unless|without|never|cannot|can\s+not|rather\s+than|instead\s+of|"
    r"not|no\s+longer|fails?\s+to|except)\b",
    re.IGNORECASE,
)


def _is_negated_context(text: str, mention_end: int, match_start: int) -> bool:
    """True when a negation stands between the concept and the captured relation."""
    if match_start <= 0:
        return False
    start = max(0, mention_end)
    return bool(_NEGATING_CONTEXT.search(text, start, match_start))


#: "X is a measure of Y" / "X is the amount by which…" are definitions. A
#: mechanism must be introduced by an instrumental preposition, not by a copula
#: whose complement merely happens to contain one.
_COPULA_BEFORE = re.compile(
    # Allow "defined as" and any adjectives between the copula and the noun:
    # "is defined as a quantitative measure of ...".
    # The copula must be close: "is a measure", "is defined as a quantitative
    # measure". Anything further away belongs to a different clause, as in
    # "It regulates what substances enter and exit the cell through processes
    # such as diffusion", where the mechanism is genuine.
    r"\b(?:is|are|was|were)\s+(?:defined\s+as\s+|known\s+as\s+|called\s+)?"
    r"(?:a|an|the)\s+(?:[a-z]+(?:ive|al|ic|ary|ous|able|ible)\s+){0,2}$",
    re.IGNORECASE,
)


def _is_copular_definition(text: str, match_start: int) -> bool:
    """True when the captured span is a definition's complement, not a method."""
    before = text[:match_start]
    if _COPULA_BEFORE.search(before):
        return True
    # The copula may be further back, separated by the definition's own head
    # noun phrase: "Erosion IS THE GRADUAL REMOVAL OF SOIL AND ROCK by wind,
    # water, or ice". The "by ..." names the agents of the defining noun, not a
    # mechanism, so asking "by what mechanism does erosion occur?" is answered
    # by a bare list. Require the copula to open the clause and nothing but the
    # noun phrase to lie between, so genuine mechanisms in later clauses ("It
    # regulates ... through processes such as diffusion") are unaffected.
    # The clause must BE the copula and its noun phrase, with no other verb in
    # between: "Erosion is the gradual removal of soil and rock | by wind".
    # If another verb intervenes the "by/through" attaches to that verb and
    # states a real mechanism ("Glaciers SHAPE landscapes by carving ...",
    # "It REGULATES what enters ... through diffusion"), which must survive.
    match = re.search(
        r"\b(?:is|are|was|were)\s+"
        r"(?:defined\s+as\s+|known\s+as\s+|called\s+)?"
        r"(?:a|an|the)\s+(?P<rest>[^.;:,]{0,60})$",
        before,
        re.IGNORECASE,
    )
    if not match:
        return False
    return not any(
        _looks_like_finite_verb(word) for word in match.group("rest").split()
    )


def _is_passive_agent(text: str, match_start: int) -> bool:
    """True when "by …" marks the agent of a passive verb rather than a method.

    "maintained by the operating system" says *who*, not *how*, so it is not a
    mechanism the learner can be asked to explain.
    """
    before = text[:match_start].rstrip()
    return bool(re.search(r"\b\w+(?:ed|en|wn|de|ne|pt|lt)\b\s*$", before, re.IGNORECASE))


#: "X states that ..." quotes a proposition verbatim; any negation inside it
#: belongs to the proposition rather than inverting the document's claim.
_STATES_THAT_CLAUSE = re.compile(
    r"\b(?:states?|asserts?|holds?|establishes?|specifies?)\s+that\b", re.IGNORECASE
)

#: The antecedent of a conditional: "if lim f/g produces an indeterminate
#: form, then ...". A relation verb inside it describes the hypothesis being
#: entertained, not something the concept does — the consequence lives after
#: "then". Splitting on the verb yields the antecedent's object as if it were
#: an effect, which is why L'Hopital's Rule appeared to "produce" an
#: indeterminate form. Domain-neutral: this is the grammar of conditionals.
_CONDITIONAL_ANTECEDENT = re.compile(r"\b(?:if|when|whenever|unless|suppose)\b", re.IGNORECASE)
_CONSEQUENT_MARKER = re.compile(r"\b(?:then|it\s+follows)\b", re.IGNORECASE)


def _inside_conditional_antecedent(text: str, start: int, end: int) -> bool:
    """True when [start, end) opens a conditional whose consequent follows."""
    span = text[start:end]
    opener = _CONDITIONAL_ANTECEDENT.search(span)
    if not opener:
        return False
    return bool(_CONSEQUENT_MARKER.search(text[start + opener.end() :]))

#: An explicit comparison the document draws between two named things:
#: "the difference between turnaround time and waiting time", "X versus Y",
#: "distinguish X from Y". A textbook that poses such a comparison — often as a
#: review question — is telling us plainly that the distinction is examinable,
#: yet no connective like "whereas" appears, so the ordinary contrast pattern
#: misses it entirely.
_EXPLICIT_COMPARISON = re.compile(
    r"\b(?:difference|differences|distinction|contrast)\s+between\s+"
    r"(?P<left>[^.;?]{2,60}?)\s+and\s+(?P<right>[^.;?]{2,60}?)(?=[.;?,]|$)"
    r"|\b(?P<left2>[\w\- ']{2,50}?)\s+(?:versus|vs\.?)\s+(?P<right2>[\w\- ']{2,50})"
    r"|\bdistinguish(?:es|ed|ing)?\s+(?P<left3>[\w\- ']{2,50}?)\s+from\s+(?P<right3>[\w\- ']{2,50})",
    re.IGNORECASE,
)

#: A stated dependency between two concepts: "SJF minimizes average waiting
#: time", "throughput depends on the quantum". The *other* concept is what the
#: subject acts upon, which supports a genuine relationship question rather
#: than a definition lookup.
_DEPENDENCY_VERB = re.compile(
    r"\b(?:minimi[sz](?:es?|ing)|maximi[sz](?:es?|ing)|reduces?|increases?|"
    r"decreases?|improves?|worsens?|affects?|influences?|determines?|governs?|"
    r"optimi[sz](?:es?|ing)|balances?|trades?\s+off)\s+"
    # Stop at a coordinating clause boundary: "minimizes average waiting time,
    # but it requires ..." should yield only the object, not the caveat.
    r"(?P<clause>[^.;]{6,120}?)(?=,?\s+(?:but|although|though|however|while|whereas|"
    r"which|and\s+(?:it|they|this))\b|[.;]|$)",
    re.IGNORECASE,
)


def _comparison_partners(text: str) -> tuple[str, str] | None:
    """The two things an explicit comparison names, if any."""
    match = _EXPLICIT_COMPARISON.search(text)
    if not match:
        return None
    groups = match.groupdict()
    left = groups.get("left") or groups.get("left2") or groups.get("left3") or ""
    right = groups.get("right") or groups.get("right2") or groups.get("right3") or ""
    left, right = left.strip(" ,"), right.strip(" ,")
    if not left or not right:
        return None
    if normalize_question_text(left) == normalize_question_text(right):
        return None
    return left, right


def extract_facets(
    name: str, sentences: list[SourceSentence], *, limit: int = 6
) -> tuple[Facet, ...]:
    """Relational claims the document makes about one concept.

    A claim is only attached when the sentence is *about* the concept — that
    is, when the concept is the sentence's subject. This keeps one concept's
    purpose from being attributed to another concept that merely appears in
    the same sentence.
    """
    facets: list[Facet] = []
    seen: set[tuple[str, str]] = set()
    name_tokens = content_tokens(name)
    if not name_tokens:
        return ()

    for sentence in _attributable_sentences(name, sentences):
        text = sentence.text

        mention_end = _mention_end(name, text)

        for kind, pattern in _FACET_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            # The concept must own the clause the relation lives in. In "a limit
            # describes the value a function approaches, continuity requires
            # that a function have no gaps", the "requires" belongs to
            # continuity — attributing it to the limit invents a false claim.
            if _other_subject_intervenes(text, mention_end, match.start()):
                continue
            # A relation reached through a negation is not a claim the
            # document makes; asserting it would state the opposite. A
            # "states that" clause is exempt: the negation lives *inside* the
            # proposition being quoted ("stays in motion unless acted upon by
            # a force"), which is the law itself, not an inverted reading.
            # The exemption covers the proposition a document quotes, not any
            # fragment lifted from inside it. "states that an object stays in
            # motion UNLESS acted upon by an unbalanced external force" quotes
            # one claim; the span after "unless" is the negated condition, and
            # asserting it alone inverts the law. So the exemption applies only
            # when no negation sits between the quote marker and the match.
            states_start = _STATES_THAT_CLAUSE.search(text[: match.start()])
            quoted_from = states_start.end() if states_start else mention_end
            if _is_negated_context(text, quoted_from, match.start()):
                continue
            # A relation verb inside a conditional's antecedent states a
            # hypothesis, not a claim about the concept.
            if _inside_conditional_antecedent(text, quoted_from, match.start()):
                continue
            groups = match.groupdict()
            raw = groups.get("clause") or groups.get("clause2") or ""
            # The clause patterns cap their capture at a character count to
            # stay bounded. When the sentence continues past that cap the
            # capture ends mid-phrase ("...provided the latter limit"), and
            # asserting it states something the document did not. Extend to
            # the real sentence boundary; if the full clause is then too long
            # to use, _usable_clause drops the facet and the writer falls back
            # to the concept's complete claim, which is long but true.
            if raw:
                tail_start = match.start() + match.group(0).find(raw) + len(raw)
                tail = text[tail_start:]
                if tail and tail[0] not in ".;":
                    extended = raw + re.split(r"[.;]", tail)[0]
                    raw = extended
            if kind == "mechanism" and _is_copular_definition(text, match.start()):
                # "is a measure of ..." defines the concept; it does not say
                # how it operates.
                continue
            if kind == "mechanism" and _is_passive_agent(text, match.start()):
                # "maintained by the operating system" names who does it, not
                # how it works.
                continue
            clause = _clean_clause(raw)
            if not _usable_clause(clause):
                continue
            key = (kind, normalize_question_text(clause))
            if key in seen:
                continue
            seen.add(key)
            facets.append(
                Facet(kind=kind, clause=clause, evidence=text, page=sentence.page)
            )

        # A stated dependency: "SJF minimizes average waiting time". The
        # sentence's subject acts on something, which is a real relationship
        # rather than a definition.
        dependency = _DEPENDENCY_VERB.search(text)
        if dependency and not _is_negated_context(text, mention_end, dependency.start()):
            clause = _clean_clause(dependency.group("clause"))
            if _usable_clause(clause):
                key = ("effect", normalize_question_text(clause))
                if key not in seen:
                    seen.add(key)
                    facets.append(
                        Facet(kind="effect", clause=clause, evidence=text, page=sentence.page)
                    )

        # An explicitly named partner wins over the generic connective pattern.
        partner = _CONTRAST_PARTNER.search(text)
        contrast = partner or _CONTRAST_PATTERN.search(text)
        if contrast:
            groups = contrast.groupdict()
            clause = _clean_clause(groups.get("clause") or groups.get("clause2") or "")
            # "X ..., while Y ..." contrasts the two SUBJECTS; the connective
            # pattern captures Y's whole clause ("the Triple Entente linked
            # France, Russia, and Britain"). A comparison question needs the
            # thing, not the sentence about it, so reduce a finite clause to
            # its subject. The writer refuses a clause-shaped partner, so
            # without this the comparison target was silently lost.
            if not partner and clause:
                subject = sentence_subject(clause)
                if subject and len(subject.split()) < len(clause.split()):
                    clause = subject
            if _usable_partner(clause):
                key = ("contrast", normalize_question_text(clause))
                if key not in seen:
                    seen.add(key)
                    facets.append(
                        Facet(
                            kind="contrast",
                            clause=clause,
                            evidence=text,
                            page=sentence.page,
                        )
                    )

    # Explicit comparisons are scanned across ALL sentences, not just the
    # subject-attributable ones. Subject attribution exists to stop a claim
    # bleeding onto a concept that merely appears in the sentence, but a
    # comparison names both participants outright ("the difference between
    # turnaround time and waiting time"), so there is nothing to mistake. Such
    # sentences are frequently review prompts whose grammatical subject is
    # "question", which attribution would otherwise discard.
    own = normalize_question_text(name)
    if own:
        for sentence in sentences:
            pair = _comparison_partners(sentence.text)
            if not pair:
                continue
            left_key, right_key = (normalize_question_text(value) for value in pair)
            if own == left_key:
                other = pair[1]
            elif own == right_key:
                other = pair[0]
            else:
                continue
            key = ("contrast", normalize_question_text(other))
            if key in seen:
                continue
            seen.add(key)
            facets.append(
                Facet(
                    kind="contrast",
                    clause=other,
                    evidence=sentence.text,
                    page=sentence.page,
                )
            )

    # Stable, deterministic ordering by facet kind then source order.
    facets.sort(key=lambda item: (FACET_KINDS.index(item.kind), item.clause.casefold()))
    return tuple(facets[:limit])


def _mention_count(name: str, sentences: list[SourceSentence]) -> int:
    normalized_name = normalize_question_text(name)
    if not normalized_name:
        return 0
    return sum(
        normalize_question_text(sentence.text).count(normalized_name) for sentence in sentences
    )


# --------------------------------------------------------------------------- #
# Importance model (frequency has weight zero, by construction)
# --------------------------------------------------------------------------- #

#: Educational importance has two parts.
#:
#: *Intrinsic* signals say what a learner gets from the concept itself: what
#: kind of knowledge it is, and how thoroughly the document explains it. These
#: dominate, because they are the only signals every document can express.
#:
#: *Structural* signals — how central the concept is to the rest of the
#: document, whether it is emphasised or listed as an objective, whether other
#: concepts depend on it, how widely it is discussed — refine the ranking. They
#: are a bounded bonus rather than a required component, so a short handout's
#: central definition is not scored as unimportant merely because a two-page
#: document has no cross-references to offer.
#:
#: Repetition contributes nothing at all: there is deliberately no frequency
#: term anywhere in this model.
INTRINSIC_WEIGHTS: dict[str, float] = {
    "knowledge_type_value": 0.65,
    "explanatory_depth": 0.35,
}

STRUCTURAL_WEIGHTS: dict[str, float] = {
    "centrality": 0.30,
    "relational_richness": 0.25,
    "teaching_emphasis": 0.20,
    "prerequisite_role": 0.13,
    "topic_spread": 0.12,
}

#: How much of the final score the structural signals can contribute.
#:
#: This is deliberately large. Intrinsic traits ("is it a definition?", "is it
#: explained?") are satisfied by *every* glossary term a document defines, so
#: when they dominate, a peripheral aside such as "a program is a passive
#: entity stored on disk" scores nearly as high as the chapter's central
#: subject. Educational importance is precisely the structural part: what the
#: rest of the document depends on, returns to, and builds upon.
STRUCTURAL_SHARE = 0.55

#: ...but a short document has no cross-references to offer, and its central
#: definition must not be scored as unimportant merely for lack of a second
#: page to be referenced from. So the structural share is applied in proportion
#: to how much structural evidence the document could realistically supply,
#: measured by how many concepts it teaches. Below this many concepts, the
#: structural share tapers toward the intrinsic-only score.
STRUCTURAL_EVIDENCE_FLOOR = 6


def _structural_share(concept_total: int) -> float:
    """How much structural signals may influence importance in this document.

    A one-page handout with three concepts cannot demonstrate centrality, so
    judging it structurally would be judging it on evidence it never had the
    chance to provide. A full chapter can, and there the structural signals are
    exactly what separates the subject from the asides.
    """
    if concept_total >= STRUCTURAL_EVIDENCE_FLOOR:
        return STRUCTURAL_SHARE
    return STRUCTURAL_SHARE * (concept_total / STRUCTURAL_EVIDENCE_FLOOR)

#: Flattened view of the model, used by tests and diagnostics. Shows the
#: weighting for a document rich enough to supply full structural evidence;
#: shorter documents taper toward the intrinsic weights via _structural_share.
IMPORTANCE_WEIGHTS: dict[str, float] = {
    **{
        name: round(weight * (1 - STRUCTURAL_SHARE), 4)
        for name, weight in INTRINSIC_WEIGHTS.items()
    },
    **{
        name: round(weight * STRUCTURAL_SHARE, 4)
        for name, weight in STRUCTURAL_WEIGHTS.items()
    },
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _score_importance(
    *,
    knowledge_type: str,
    evidence: tuple[Evidence, ...],
    explanatory_tokens: int,
    reference_count: int,
    relation_degree: int,
    facet_count: int = 0,
    prerequisite_for: int,
    objective_hits: int,
    emphasis_hits: int,
    topic_spread: int,
    provider_emphasis: str,
    concept_total: int,
) -> tuple[float, dict[str, float]]:
    """Educational importance from teaching signals — never from repetition."""
    peers = max(1, concept_total - 1)
    # Depth is "is this actually explained?" first and "how thoroughly?"
    # second.  One complete teaching sentence already earns most of the score:
    # a crisp one-line definition is taught content, not a passing mention.
    # Extended treatment then adds the remainder.
    depth = 0.60 * float(explanatory_tokens >= 5) + 0.40 * _clamp(explanatory_tokens / 40.0)
    signals = {
        "knowledge_type_value": KNOWLEDGE_TYPE_VALUE.get(knowledge_type, 0.5),
        "explanatory_depth": round(depth, 3),
        "centrality": _clamp((reference_count + relation_degree) / max(3.0, peers * 0.5)),
        # How many distinct relational claims the document makes about this
        # concept — its purpose, cause, effect, mechanism, contrast. A document
        # that explains how something works and what it is for is teaching it,
        # not merely listing it. This is what separates a core algorithm from a
        # glossary aside that is defined once and never developed.
        "relational_richness": _clamp(facet_count / 2.0),
        "teaching_emphasis": _clamp(0.45 * objective_hits + 0.28 * emphasis_hits),
        "prerequisite_role": _clamp(prerequisite_for / 2.0),
        "topic_spread": _clamp((topic_spread - 1) / 2.0),
    }
    intrinsic = sum(weight * signals[name] for name, weight in INTRINSIC_WEIGHTS.items())
    structural = sum(weight * signals[name] for name, weight in STRUCTURAL_WEIGHTS.items())
    share = _structural_share(concept_total)
    score = (1 - share) * intrinsic + share * structural
    score += {"high": 0.04, "medium": 0.0, "low": -0.06}.get(
        (provider_emphasis or "medium").strip().lower(), 0.0
    )
    # "Explained" means the document asserts something substantive about the
    # concept, not merely that the phrase occurs. One complete teaching
    # sentence clears this; a bare mention or caption does not.
    explained = bool(evidence) and explanatory_tokens >= 5
    if not explained:
        score = min(score, UNEXPLAINED_CEILING)
    if knowledge_type == "example":
        score = min(score, EXAMPLE_CEILING)
    if knowledge_type == "fact" and explanatory_tokens < 18:
        score = min(score, 0.5)
    return round(_clamp(score), 3), {name: round(value, 3) for name, value in signals.items()}


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #


def build_understanding_prompt(*, source_block: str, title: str) -> str:
    """Ask for comprehension of the document — explicitly not for questions."""
    return f"""You are a subject-matter teacher reading a study document for the first time.
Your ONLY job right now is to UNDERSTAND what this document teaches. Do not write any quiz
questions, options, answers, or scenarios: a later stage does that.

Document title: {title!r}

Produce a structured understanding:
1. subject — the academic subject/field this document belongs to.
2. summary — 2-4 sentences stating what the document actually teaches, naming its real content.
3. main_topics — the major areas the document covers, with their subtopics and pages.
4. concepts — everything the document genuinely teaches. For each concept give:
   - id: a short stable slug (e.g. "cell-theory")
   - name: the concept as a learner would name it
   - description: what the document says about it, in your own words
   - topic: which main topic it belongs to
   - knowledge_type: one of {", ".join(KNOWLEDGE_TYPES)}
   - teaching_emphasis: high | medium | low — how central it is to the document's teaching
   - evidence_quotes: 1-3 quotes copied VERBATIM from the pages you cite (no ellipses, no edits)
   - source_pages: the pages those quotes are on
   - prerequisites: ids of concepts a learner must understand first
   - related_concepts: ids of concepts this one connects to
   - knowledge_targets: 1-4 things a learner must be able to do with this concept
     (for example: state what it is, explain its mechanism, predict its effect,
     distinguish it from a similar concept, apply it to a situation)
   - why_important: why understanding it matters for the rest of the document
5. relationships — taught connections between concepts: cause, enables, part_of,
   contrast, prerequisite, produces. Each needs verbatim evidence and pages.
6. learning_objectives — what a learner should be able to do after studying, tied to concept ids.

Judgement rules:
- Importance is about what a learner must understand, NOT about what words repeat.
  A concept explained once in a major explanatory passage is more important than a
  phrase that appears twenty times in headers, captions, or running text.
- Headings, page furniture, copyright, publishers, URLs, ISBNs, figure numbers, colours,
  layout, and typography are NOT concepts. Never list them.
- A heading on its own is not evidence: quote the sentence that explains the idea.
- Only include a concept the document actually explains. If it is merely named in passing,
  either omit it or mark teaching_emphasis low.
- Every quote must appear verbatim on the page you cite; the backend verifies this and
  silently discards anything it cannot find.

CLEANED SOURCE:
{source_block}
"""


# --------------------------------------------------------------------------- #
# Normalization: the backend decides what the study map contains
# --------------------------------------------------------------------------- #


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    slug = slug[:48]
    return slug or fallback


def _coerce_pages(raw_pages: Iterable[Any], included_pages: set[int]) -> list[int]:
    pages: list[int] = []
    for value in raw_pages:
        try:
            page = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if page in included_pages and page not in pages:
            pages.append(page)
    return pages[:10]


def _valid_evidence(
    quotes: Iterable[str],
    *,
    pages: list[int],
    page_text: dict[int, str],
    name: str,
) -> list[Evidence]:
    """Keep only quotes that exist verbatim, teach something, and match the concept."""
    name_tokens = content_tokens(name)
    found: list[Evidence] = []
    seen: set[str] = set()
    for quote in quotes:
        text = re.sub(r"\s+", " ", (quote or "").strip())
        if not text or not _is_teaching_sentence(text):
            continue
        key = evidence_normalize(text)
        if not key or key in seen:
            continue
        page = next(
            (page for page in pages if key in evidence_normalize(page_text.get(page, ""))),
            None,
        )
        if page is None:
            continue
        if name_tokens and not (name_tokens & content_tokens(text)):
            continue
        seen.add(key)
        found.append(Evidence(text=text, page=page))
    return found[:3]


def _resolve_ids(values: Iterable[str], known: dict[str, str]) -> tuple[str, ...]:
    resolved: list[str] = []
    for value in values:
        candidate = known.get(_slug(value, "")) or known.get(normalize_question_text(value))
        if candidate and candidate not in resolved:
            resolved.append(candidate)
    return tuple(resolved[:6])


def _deterministic_summary(
    concepts: list[ConceptNode], topics: list[Topic], title: str
) -> str:
    top = [node.name for node in sorted(concepts, key=lambda c: -c.importance)[:6]]
    topic_names = [topic.name for topic in topics[:4]]
    parts = []
    if topic_names:
        parts.append("covers " + ", ".join(topic_names))
    if top:
        parts.append("and teaches " + ", ".join(top))
    body = " ".join(parts) if parts else "presents study material"
    return f"The document {body}."


def normalize_understanding(
    raw: _RawUnderstanding,
    units: list[SourceUnit],
    *,
    title: str,
) -> DocumentUnderstanding:
    """Verify, classify, and rank a provider-proposed understanding."""
    sentences = iter_sentences(units)
    page_text = {unit.page: unit.text for unit in units}
    included_pages = set(page_text)

    # -- pass 1: keep only grounded, non-boilerplate, non-heading concepts -- #
    staged: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    id_lookup: dict[str, str] = {}
    for index, item in enumerate(raw.concepts[:60]):
        name = re.sub(r"\s+", " ", item.name.strip()).strip("-:;,. ")
        if not (2 < len(name) <= 120):
            continue
        if is_generic_label(name) or is_boilerplate_text(name) or is_layout_detail(name):
            continue
        if is_heading_like(name) and not content_tokens(name):
            continue
        pages = _coerce_pages(item.source_pages, included_pages) or sorted(included_pages)
        evidence = _valid_evidence(
            item.evidence_quotes, pages=pages, page_text=page_text, name=name
        )
        if not evidence:
            # A provider quote may be lightly reformatted by the PDF extractor;
            # fall back to locating the concept's own teaching sentences.
            evidence = [
                Evidence(text=sentence.text, page=sentence.page)
                for sentence in _concept_sentences(name, sentences, limit=3)
            ]
        if not evidence:
            continue
        knowledge_type = _canonical_type(item.knowledge_type, evidence[0].text)
        concept_id = _slug(item.id or name, f"concept-{index + 1}")
        while concept_id in used_ids:
            concept_id = f"{concept_id}-{index + 1}"
        used_ids.add(concept_id)
        id_lookup[_slug(item.id or name, "")] = concept_id
        id_lookup[_slug(name, "")] = concept_id
        id_lookup[normalize_question_text(name)] = concept_id
        staged.append(
            {
                "concept_id": concept_id,
                "name": name,
                "description": re.sub(r"\s+", " ", item.description.strip())[:400],
                "topic": re.sub(r"\s+", " ", item.topic.strip())[:120],
                "knowledge_type": knowledge_type,
                "evidence": tuple(evidence),
                "pages": tuple(sorted({e.page for e in evidence})),
                "raw": item,
                "targets": list(item.knowledge_targets),
            }
        )

    if not staged:
        return deterministic_understanding(units, title=title)

    concepts = _finalize_concepts(staged, sentences=sentences, id_lookup=id_lookup)

    known_ids = {node.concept_id for node in concepts}
    relationships = _normalize_relationships(
        raw.relationships, id_lookup=id_lookup, known_ids=known_ids,
        page_text=page_text, included_pages=included_pages,
    )
    # Relationship degree feeds centrality, so importance is recomputed once the
    # graph is known.
    concepts = _apply_relationship_centrality(concepts, relationships)

    topics = _normalize_topics(raw.main_topics, concepts, id_lookup, included_pages)
    objectives = _normalize_objectives(
        raw.learning_objectives, concepts, id_lookup, included_pages, sentences
    )

    summary = re.sub(r"\s+", " ", raw.summary.strip())[:800]
    summary_tokens = content_tokens(summary)
    concept_tokens: set[str] = set()
    for node in concepts:
        concept_tokens |= content_tokens(node.name)
    if len(summary) < 40 or not (summary_tokens & concept_tokens):
        # A summary that does not mention anything the document teaches is not a
        # summary of this document.
        summary = _deterministic_summary(list(concepts), list(topics), title)

    subject = re.sub(r"\s+", " ", raw.subject.strip())[:120] or _infer_subject(concepts, title)
    return DocumentUnderstanding(
        title=title,
        subject=subject,
        summary=summary,
        main_topics=topics,
        concepts=concepts,
        relationships=relationships,
        learning_objectives=objectives,
        source="provider",
    )


def _finalize_concepts(
    staged: list[dict[str, Any]],
    *,
    sentences: list[SourceSentence],
    id_lookup: dict[str, str],
) -> tuple[ConceptNode, ...]:
    """Compute grounded descriptions, relationships-free importance, and signals."""
    total = len(staged)
    names = {entry["concept_id"]: entry["name"] for entry in staged}

    prerequisite_for: dict[str, int] = {}
    for entry in staged:
        for value in entry["raw"].prerequisites:
            resolved = id_lookup.get(_slug(value, "")) or id_lookup.get(
                normalize_question_text(value)
            )
            if resolved and resolved != entry["concept_id"]:
                prerequisite_for[resolved] = prerequisite_for.get(resolved, 0) + 1

    # Whether English subject detection works at all for this document. Used to
    # tell "this concept is never the subject" apart from "subject detection
    # does not apply to this language".
    _any_attribution_possible = any(
        sentence_subject(sentence.text) for sentence in sentences[:40]
    )

    nodes: list[ConceptNode] = []
    for entry in staged:
        name = entry["name"]
        evidence: tuple[Evidence, ...] = entry["evidence"]
        related_sentences = _concept_sentences(name, sentences)
        # Depth must measure sentences that are *about* this concept, not every
        # sentence its name appears in. "Speed" occurs inside Newton's First Law
        # and inside a sentence about centripetal acceleration, but the document
        # never explains speed itself; counting those would make an incidental
        # term look thoroughly taught.
        explaining_sentences = _attributable_sentences(name, sentences)
        explanatory_tokens = sum(
            len(content_tokens(sentence.text))
            for sentence in explaining_sentences
            if len(content_tokens(sentence.text)) >= 5
        )
        if not explaining_sentences and not _any_attribution_possible:
            # Subject detection is English-grammar based. If it resolved no
            # subject anywhere in the document, it cannot be trusted here
            # (a non-English source), so fall back to verified evidence.
            #
            # When attribution DOES work elsewhere, a concept with no
            # attributable sentence is one the document never makes a claim
            # about — "speed" appears only inside sentences about Newton's
            # First Law and centripetal acceleration — and its depth is
            # genuinely zero.
            explanatory_tokens = sum(len(content_tokens(item.text)) for item in evidence)
        objective_hits = sum(
            1
            for sentence in related_sentences
            if _OBJECTIVE_MARKERS.search(sentence.text)
        )
        emphasis_hits = sum(
            1 for sentence in related_sentences if _EMPHASIS_MARKERS.search(sentence.text)
        )
        # "Referenced by other concepts" is a semantic centrality signal: how
        # many *other* taught ideas need this one to be explained.
        reference_count = 0
        own_tokens = content_tokens(name)
        for other in staged:
            if other["concept_id"] == entry["concept_id"]:
                continue
            other_text = " ".join(item.text for item in other["evidence"])
            if own_tokens and own_tokens <= content_tokens(other_text):
                reference_count += 1
        topic_spread = len({item.page for item in evidence} | {s.page for s in related_sentences})
        # Facets are the document's relational claims about this concept. They
        # are extracted before scoring because "does the document explain this
        # concept's mechanism / purpose / effects?" is itself a strong signal
        # of educational importance, not merely raw material for questions.
        facets = extract_facets(name, sentences)
        importance, signals = _score_importance(
            knowledge_type=entry["knowledge_type"],
            evidence=evidence,
            explanatory_tokens=explanatory_tokens,
            reference_count=reference_count,
            relation_degree=0,
            facet_count=len(facets),
            prerequisite_for=prerequisite_for.get(entry["concept_id"], 0),
            objective_hits=objective_hits,
            emphasis_hits=emphasis_hits,
            topic_spread=topic_spread,
            provider_emphasis=entry["raw"].teaching_emphasis,
            concept_total=total,
        )
        description = entry["description"] or evidence[0].text
        # The knowledge type above comes from the sentence pattern that first
        # named the term. The facets are stronger evidence: a concept the
        # document explains a mechanism, cause, effect, or governing condition
        # for is not a bare "fact", whatever the naming sentence looked like.
        # Classifying by first mention alone marked landform and phenomenon
        # concepts ("a river delta forms where ...") as facts, which are not a
        # teachable type, so they were dropped before they could be tested even
        # though the document clearly teaches them. Derived from the document's
        # own relations, so it stays subject-neutral.
        knowledge_type = entry["knowledge_type"]
        if knowledge_type in {"fact", "example"} and facets:
            observed = {facet.kind for facet in facets}
            for facet_kind, upgraded in _FACET_KNOWLEDGE_TYPE.items():
                if facet_kind in observed:
                    knowledge_type = upgraded
                    break
        nodes.append(
            ConceptNode(
                concept_id=entry["concept_id"],
                name=name,
                description=description[:400],
                topic=entry["topic"] or _infer_topic(name, evidence),
                knowledge_type=knowledge_type,
                importance=importance,
                learning_value=round(
                    KNOWLEDGE_TYPE_VALUE.get(knowledge_type, 0.5) * 0.5
                    + signals["explanatory_depth"] * 0.5,
                    3,
                ),
                evidence=evidence,
                source_pages=entry["pages"],
                prerequisites=_resolve_ids(entry["raw"].prerequisites, id_lookup),
                related_concepts=_resolve_ids(entry["raw"].related_concepts, id_lookup),
                signals=signals,
                mention_count=_mention_count(name, sentences),
                explained=explanatory_tokens >= 5,
                rationale=re.sub(r"\s+", " ", entry["raw"].why_important.strip())[:300],
                facets=facets,
            )
        )
    # A stable, deterministic study map: identical input yields identical order.
    nodes.sort(key=lambda node: (-node.importance, node.name.casefold()))
    _ = names
    return _normalize_importance(tuple(nodes))


def _normalize_importance(nodes: tuple[ConceptNode, ...]) -> tuple[ConceptNode, ...]:
    """Rescale importance so it means "important *within this document*".

    Structural signals are inherently relative: a dense textbook chapter
    produces far higher centrality values than a two-page handout, so a single
    absolute cutoff would admit almost everything from the former and almost
    nothing from the latter. Anchoring the scale to the document's own strongest
    concept keeps IMPORTANCE_FLOOR meaning the same thing everywhere — "clearly
    among what this document is actually teaching".

    Ordering is untouched; only the scale changes. Ceilings that mark a concept
    as unteachable are re-applied afterwards so normalisation can never promote
    an unexplained mention or a mere example.
    """
    if not nodes:
        return nodes
    # Anchor to the median of the document's leading concepts rather than to
    # its single best. One concept often absorbs nearly all centrality (in a
    # cell-biology chapter, everything references "cell"), and scaling against
    # that outlier would push genuine teaching targets like the Golgi apparatus
    # below the floor. A median over the top tier is robust to that.
    ranked = sorted((node.importance for node in nodes), reverse=True)
    leading = ranked[: max(3, min(8, len(ranked)))]
    anchor = leading[len(leading) // 2]
    if anchor <= 0.0:
        return nodes
    # Place that typical strong concept comfortably above the floor.
    scale = 0.78 / anchor
    # Never depress a document whose concepts already score well.
    if scale <= 1.0:
        return nodes
    rescaled: list[ConceptNode] = []
    for node in nodes:
        importance = _clamp(node.importance * scale)
        if not node.explained:
            importance = min(importance, UNEXPLAINED_CEILING)
        if node.knowledge_type == "example":
            importance = min(importance, EXAMPLE_CEILING)
        rescaled.append(replace(node, importance=round(importance, 3)))
    return tuple(rescaled)


def _apply_relationship_centrality(
    concepts: tuple[ConceptNode, ...], relationships: tuple[Relationship, ...]
) -> tuple[ConceptNode, ...]:
    if not relationships:
        return concepts
    degree: dict[str, int] = {}
    for relationship in relationships:
        degree[relationship.source_id] = degree.get(relationship.source_id, 0) + 1
        degree[relationship.target_id] = degree.get(relationship.target_id, 0) + 1
    total = len(concepts)
    updated: list[ConceptNode] = []
    for node in concepts:
        extra = degree.get(node.concept_id, 0)
        if not extra:
            updated.append(node)
            continue
        signals = dict(node.signals)
        signals["centrality"] = round(
            _clamp(signals.get("centrality", 0.0) + extra / max(3.0, total * 0.5)), 3
        )
        importance = sum(
            IMPORTANCE_WEIGHTS[name] * signals.get(name, 0.0) for name in IMPORTANCE_WEIGHTS
        )
        if not node.explained:
            importance = min(importance, UNEXPLAINED_CEILING)
        if node.knowledge_type == "example":
            importance = min(importance, EXAMPLE_CEILING)
        updated.append(
            ConceptNode(
                **{
                    **node.__dict__,
                    "signals": signals,
                    "importance": round(_clamp(max(node.importance, importance)), 3),
                }
            )
        )
    updated.sort(key=lambda node: (-node.importance, node.name.casefold()))
    return tuple(updated)


def _normalize_relationships(
    raw_relationships: list[_RawRelationship],
    *,
    id_lookup: dict[str, str],
    known_ids: set[str],
    page_text: dict[int, str],
    included_pages: set[int],
) -> tuple[Relationship, ...]:
    kinds = {
        "cause": "cause",
        "causes": "cause",
        "causal": "cause",
        "effect": "cause",
        "enables": "enables",
        "requires": "prerequisite",
        "prerequisite": "prerequisite",
        "part_of": "part_of",
        "part of": "part_of",
        "contains": "part_of",
        "contrast": "contrast",
        "compares": "contrast",
        "comparison": "contrast",
        "produces": "produces",
        "related": "related",
    }
    seen: set[tuple[str, str, str]] = set()
    relationships: list[Relationship] = []
    for item in raw_relationships[:60]:
        source = id_lookup.get(_slug(item.source, "")) or id_lookup.get(
            normalize_question_text(item.source)
        )
        target = id_lookup.get(_slug(item.target, "")) or id_lookup.get(
            normalize_question_text(item.target)
        )
        if not source or not target or source == target:
            continue
        if source not in known_ids or target not in known_ids:
            continue
        kind = kinds.get(re.sub(r"[\s\-]+", "_", item.kind.strip().lower()), "related")
        evidence = re.sub(r"\s+", " ", item.evidence.strip())
        pages = _coerce_pages(item.source_pages, included_pages)
        if evidence and pages and not quote_is_grounded(
            evidence, pages=pages, page_text=page_text
        ):
            continue
        key = (source, target, kind)
        if key in seen:
            continue
        seen.add(key)
        relationships.append(
            Relationship(
                source_id=source,
                target_id=target,
                kind=kind,
                evidence=evidence[:400],
                pages=tuple(pages),
            )
        )
    return tuple(relationships)


def _normalize_topics(
    raw_topics: list[_RawTopic],
    concepts: tuple[ConceptNode, ...],
    id_lookup: dict[str, str],
    included_pages: set[int],
) -> tuple[Topic, ...]:
    known = {node.concept_id for node in concepts}
    topics: list[Topic] = []
    seen: set[str] = set()
    for item in raw_topics[:16]:
        name = re.sub(r"\s+", " ", item.name.strip()).strip("-:;,. ")
        if not (2 < len(name) <= 140) or is_boilerplate_text(name):
            continue
        key = normalize_question_text(name)
        if not key or key in seen:
            continue
        seen.add(key)
        concept_ids = tuple(
            value for value in _resolve_ids(item.concept_ids, id_lookup) if value in known
        )
        if not concept_ids:
            concept_ids = tuple(
                node.concept_id
                for node in concepts
                if normalize_question_text(node.topic) == key
            )
        subtopics = tuple(
            re.sub(r"\s+", " ", value.strip())[:120]
            for value in item.subtopics[:8]
            if 2 < len(value.strip()) <= 120 and not is_boilerplate_text(value)
        )
        topics.append(
            Topic(
                name=name,
                subtopics=subtopics,
                concept_ids=concept_ids,
                pages=tuple(_coerce_pages(item.source_pages, included_pages)),
            )
        )
    if topics:
        return tuple(topics)
    # Derive topics from concept topic labels when the provider omitted them.
    grouped: dict[str, list[ConceptNode]] = {}
    for node in concepts:
        grouped.setdefault(node.topic or node.name, []).append(node)
    return tuple(
        Topic(
            name=name,
            subtopics=(),
            concept_ids=tuple(node.concept_id for node in nodes),
            pages=tuple(sorted({page for node in nodes for page in node.source_pages})),
        )
        for name, nodes in list(grouped.items())[:12]
    )


def _normalize_objectives(
    raw_objectives: list[_RawObjective],
    concepts: tuple[ConceptNode, ...],
    id_lookup: dict[str, str],
    included_pages: set[int],
    sentences: list[SourceSentence],
) -> tuple[LearningObjective, ...]:
    known = {node.concept_id for node in concepts}
    objectives: list[LearningObjective] = []
    seen: set[str] = set()
    for item in raw_objectives[:12]:
        text = re.sub(r"\s+", " ", item.text.strip())
        if not (8 < len(text) <= 300) or is_boilerplate_text(text):
            continue
        key = normalize_question_text(text)
        if key in seen:
            continue
        concept_ids = tuple(
            value for value in _resolve_ids(item.concept_ids, id_lookup) if value in known
        )
        if not concept_ids:
            tokens = content_tokens(text)
            concept_ids = tuple(
                node.concept_id
                for node in concepts
                if content_tokens(node.name) & tokens
            )[:4]
        if not concept_ids:
            continue
        seen.add(key)
        objectives.append(
            LearningObjective(
                text=text,
                concept_ids=concept_ids,
                pages=tuple(_coerce_pages(item.source_pages, included_pages)),
            )
        )
    if objectives:
        return tuple(objectives)
    return _derived_objectives(concepts, sentences)


def _derived_objectives(
    concepts: tuple[ConceptNode, ...], sentences: list[SourceSentence]
) -> tuple[LearningObjective, ...]:
    """Objectives stated by the document, else derived from top concepts."""
    stated: list[LearningObjective] = []
    for sentence in sentences:
        if not _OBJECTIVE_MARKERS.search(sentence.text):
            continue
        tokens = content_tokens(sentence.text)
        concept_ids = tuple(
            node.concept_id for node in concepts if content_tokens(node.name) & tokens
        )[:5]
        if concept_ids:
            stated.append(
                LearningObjective(
                    text=sentence.text[:300], concept_ids=concept_ids, pages=(sentence.page,)
                )
            )
        if len(stated) >= 6:
            break
    if stated:
        return tuple(stated)
    verbs = {
        "definition": "Explain what {name} is and what distinguishes it",
        "process": "Describe how {name} works and what it produces",
        "cause_effect": "Explain the cause and effect involved in {name}",
        "comparison": "Distinguish {name} from the ideas it is contrasted with",
        "classification": "Classify the categories involved in {name}",
        "principle": "Apply {name} correctly",
        "example": "Explain which idea {name} illustrates",
        "fact": "Recall and use {name} correctly",
    }
    return tuple(
        LearningObjective(
            text=verbs[node.knowledge_type].format(name=node.name),
            concept_ids=(node.concept_id,),
            pages=node.source_pages,
        )
        for node in sorted(concepts, key=lambda n: -n.importance)[:6]
    )


def _infer_topic(name: str, evidence: tuple[Evidence, ...]) -> str:
    return name if not evidence else name


_SUBJECT_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Biology", ("cell", "organelle", "dna", "protein", "mitosis", "enzyme", "organism", "gene")),
    ("Chemistry", ("molecule", "reaction", "acid", "atom", "compound", "bond", "ion")),
    ("Physics", ("force", "velocity", "energy", "momentum", "newton", "acceleration", "mass")),
    ("Mathematics", ("theorem", "derivative", "integral", "limit", "equation", "function", "proof")),
    ("Computer Science", ("algorithm", "recursion", "process", "memory", "scheduling", "thread", "data")),
    ("History", ("century", "war", "empire", "revolution", "treaty", "dynasty")),
    ("Geography", ("climate", "region", "erosion", "population", "terrain", "river")),
    ("Business", ("market", "revenue", "customer", "strategy", "profit", "supply")),
]


def _infer_subject(concepts: tuple[ConceptNode, ...], title: str) -> str:
    corpus = " ".join(
        [title] + [node.name for node in concepts] + [node.primary_evidence for node in concepts]
    ).lower()
    for subject, hints in _SUBJECT_HINTS:
        if sum(hint in corpus for hint in hints) >= 2:
            return subject
    return "General study material"


# --------------------------------------------------------------------------- #
# Deterministic understanding (no provider available)
# --------------------------------------------------------------------------- #

# A term is a noun phrase of up to four words.  Continuation words may be
# capitalized so multi-word proper terms survive intact ("Industrial
# Revolution", "Calvin Cycle") rather than being clipped to their last word.
_TERM_HEAD = r"[A-Za-z][A-Za-z0-9'’\-]*(?:\s+[A-Za-z][A-Za-z0-9'’\-]+){0,3}"

_TERM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(rf"\b(?:The\s+|A\s+|An\s+)?({_TERM_HEAD})\s+(?:is|are)\s+defined\s+as\b"),
        "definition",
    ),
    (
        re.compile(rf"\b(?:The\s+|A\s+|An\s+)?({_TERM_HEAD})\s+refers?\s+to\b"),
        "definition",
    ),
    (
        re.compile(rf"\b(?:The\s+|A\s+|An\s+)?({_TERM_HEAD})\s+(?:is|are)\s+(?:the|a|an)\b"),
        "definition",
    ),
    (
        re.compile(rf"\b(?:The\s+|A\s+|An\s+)?({_TERM_HEAD})\s+(?:is|are)\s+(?:called|known\s+as)\b"),
        "definition",
    ),
    (
        re.compile(r"([\u0600-\u06FF][\u0600-\u06FF\s]{2,40}?)\s+(?:هو|هي)\s"),
        "definition",
    ),
]

#: The subject span of a sentence. The window is 5 tokens rather than 4: a
#: multi-word proper name ("assassination of Archduke Franz Ferdinand") was cut
#: at the old cap, which both mis-named the concept and left the remainder
#: ("Ferdinand in June 1914 ...") to open the answer. _trim_to_subject cuts at
#: the real predicate, so the extra token costs nothing when the subject is
#: short. It is deliberately not widened further: at 6 tokens an overview
#: sentence ("Newton's three laws of motion form the foundation ...") yields a
#: catch-all concept that duplicates the individual laws it summarises.
_SUBJECT_HEAD = re.compile(
    r"^(?:The\s+|A\s+|An\s+)?([A-Za-z][A-Za-z0-9'’\-]*(?:\s+[A-Za-z][A-Za-z0-9'’\-]+){0,4})\b"
)

# Discourse connectives introduce a clause; they never name a concept. A term
# such as "In contrast" or "Because of this role" is a rhetorical link, not
# something a learner can be asked about.
_DISCOURSE_OPENER = re.compile(
    r"^\s*(?:in\s+(?:contrast|summary|addition|fact|other\s+words|general|particular)|"
    r"unlike|instead|rather|similarly|likewise|conversely|nevertheless|meanwhile|"
    r"together|overall|finally|first|second|third|next|then|also|"
    r"because(?:\s+of)?|however|therefore|thus|hence|moreover|furthermore|although|though|"
    r"while|whereas|since|for\s+example|for\s+instance|as\s+a\s+result|consequently|"
    r"on\s+the\s+other\s+hand|by\s+contrast|many\s+students|students|a\s+key\s+exam\s+tip|"
    r"each\s+group|this|these|those|it|they|there|such|both|every|some|many|most|"
    r"understanding|remember|note)\b[\s,]*",
    re.IGNORECASE,
)

_LEADING_DETERMINER = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

#: A quantifier introduces an instance, not a named concept: "each algorithm"
#: is a sentence talking about algorithms in general, not a concept called
#: "each algorithm".
_QUANTIFIER_START = re.compile(
    r"^(?:each|every|all|both|any|some|either|neither|several|many|most|few|"
    r"this|that|these|those|such|other|another|its|their|his|her)\b",
    re.IGNORECASE,
)

# Sentence-initial adverbs ("Formally, ...", "Geometrically, ...") frame a
# statement; they are not the thing being described.
_LEADING_ADVERB = re.compile(r"^[A-Za-z]+ly\b[\s,]*", re.IGNORECASE)

# A concept name must contain at least one content-bearing word that is not a
# pure discourse/scaffolding token.
_NON_CONCEPT_WORDS = frozenset(
    """contrast summary addition fact example instance result role thing things way ways
    part parts case cases point points group groups form forms type types kind kinds
    student students exam tip tips chapter section page approach approaches idea ideas
    note notes topic topics misconception misconceptions mastery overview aspect aspects
    detail details item items feature features step steps new old common simple
    important key main basic general""".split()
)

# Meta-labels about the *teaching* rather than the subject. "A key theorem
# states ..." introduces a theorem; the label itself teaches nothing.
_META_LABEL = re.compile(
    r"^(?:a\s+|an\s+|the\s+)?(?:common|key|important|useful|typical|classic|general|main|"
    r"basic|simple|helpful|final|first|last|next|another|related)\s+"
    r"(?:exam\s+)?(?:tip|note|point|idea|example|misconception|mistake|error|theorem|rule|"
    r"result|case|approach|method|technique|strategy|observation|remark|question|problem|"
    r"step|feature|property|fact|topic|concept|term|definition)s?$",
    re.IGNORECASE,
)


# A concept name is a noun phrase.  These endings mean the phrase was cut
# mid-clause and names nothing a learner can be asked about.
_TRAILING_FUNCTION_WORD = re.compile(
    r"\b(?:the|a|an|of|to|in|on|for|with|from|by|as|at|into|and|or|but|that|which|"
    r"between|within|through|during|before|after|much|like|this|these|those|its|their)$",
    re.IGNORECASE,
)

# Gerunds and imperatives start a clause, not a concept name.
_VERBAL_START = re.compile(
    r"^(?:preparing|studying|reviewing|understanding|remembering|learning|noting|"
    r"considering|using|applying|explaining|describing|mastering|find|remember|note|"
    r"consider|explain|describe|compare|identify|list|state|see|read)\b",
    re.IGNORECASE,
)

# An adverb cannot open a noun phrase ("frequently struggle").
_ADVERB_START = re.compile(r"^[A-Za-z]{3,}ly\s", re.IGNORECASE)

# Head nouns that describe the act of studying rather than a subject concept.
_META_HEAD_WORDS = frozenset(
    """mastery understanding knowledge familiarity awareness recall revision practice
    study studying preparation review summary overview introduction conclusion""".split()
)

#: Generic container nouns. On their own they name no subject matter: "the
#: equation", "the process", "the diagram" tell a learner nothing about what
#: is being taught, so they must not become concepts. (A *qualified* phrase
#: such as "equation for cellular respiration" is fine and is not matched here,
#: because the check applies only to the whole normalized name.)
_BARE_CONTAINER_NOUNS = frozenset(
    """equation formula process procedure method technique system structure function
    diagram figure table chart graph model theory law rule principle concept term
    definition example section chapter unit topic subject material content item
    element component factor value number result output input step stage phase
    part piece portion aspect property attribute characteristic
    problem issue case situation approach way idea point detail note
    advantage disadvantage benefit drawback limitation feature purpose role""".split()
)


#: Adjectives that grade or flag a noun without naming subject matter. They mark
#: a phrase as the document *pointing at* a topic rather than naming one.
_EVALUATIVE_ADJECTIVES = frozenset(
    """significant important major minor common general specific particular
    key main primary secondary basic simple complex critical essential crucial
    notable typical special useful practical fundamental central""".split()
)


def _acceptable_term(term: str) -> bool:
    cleaned = _LEADING_DETERMINER.sub("", term).strip()
    if not (2 < len(cleaned) <= 70):
        return False
    if _DISCOURSE_OPENER.match(cleaned) or _VERBAL_START.match(cleaned):
        return False
    if _TRAILING_FUNCTION_WORD.search(cleaned):
        return False
    if _META_LABEL.match(cleaned) or _FUNCTION_WORD_START.match(cleaned):
        return False
    if _ADVERB_START.match(cleaned):
        return False
    if _QUANTIFIER_START.match(cleaned):
        return False
    # A name ending in a preposition was cut before its object.
    if re.search(r"\b(?:of|in|on|for|to|with)\s+(?:the|a|an)?$", cleaned, re.IGNORECASE):
        return False
    tokens_in_order = content_token_list(cleaned)
    # The head noun decides what a phrase names. "Mastery of the power rule"
    # is a sentence about studying, not a concept called "mastery".
    if tokens_in_order and tokens_in_order[0] in _META_HEAD_WORDS:
        return False
    tokens = content_tokens(cleaned)
    if not tokens or tokens <= _NON_CONCEPT_WORDS:
        return False
    # A bare container noun names no subject matter on its own. The list is
    # written in the singular, so fold inflection before comparing: "processes"
    # is exactly as contentless a name as "process".
    if {_name_stem(token) for token in tokens} <= {
        _name_stem(noun) for noun in _BARE_CONTAINER_NOUNS
    }:
        return False
    # An evaluative adjective in front of a container noun still names nothing:
    # "a significant problem" and "an important factor" are how a document
    # *introduces* a topic, not the topic itself. The concept is whatever the
    # sentence goes on to name, so this phrase must not become one.
    if tokens_in_order and tokens_in_order[0] in _EVALUATIVE_ADJECTIVES:
        if set(tokens_in_order[1:]) <= _BARE_CONTAINER_NOUNS:
            return False
    return True


#: Nouns ending in -s that are not third-person verbs. Without these the
#: morphological test below would cut "Newton's Laws" or "Related rates" at
#: their own head word. Kept deliberately small and domain-neutral: these are
#: English morphology exceptions, not subject vocabulary.
_NOUNLIKE_S_SUFFIX = re.compile(
    r"(?:ss|us|is|ics|ness|ies|sis|ses|nces|ments|tions|sions|ions)$",
    re.IGNORECASE,
)


#: Words that typically open a verb's complement rather than continue a noun
#: phrase. "problems use THE chain rule" -> verb; "Related rates PROBLEMS" ->
#: another noun, so "rates" was a modifier.
_COMPLEMENT_OPENER = re.compile(
    # "of" is deliberately absent: it binds a head noun to its own complement
    # ("three laws OF motion", "assassination OF the Archduke"), so treating it
    # as a predicate complement would truncate legitimate names.
    r"^(?:the|a|an|to|from|into|onto|with|by|for|in|on|at|as|than|between|"
    r"through|against|among|upon|over|under|toward|towards|about|"
    r"that|this|these|"
    r"those|its|their|his|her|our|your|only|completely|partially|entirely|"
    r"always|never|often|usually|specifically|directly|when|where|how|why)$",
    re.IGNORECASE,
)


def _looks_like_finite_verb(word: str) -> bool:
    """True when a token is a present-tense third-person verb or a past tense.

    The explicit stop-word list cannot be completed: every new document brings
    verbs it does not contain ("differs", "concerns", "triggered", "dissociates"),
    and each omission let the verb be absorbed into the concept name, producing
    names like "Nationalism differs" and "Erosion differs". Morphology
    generalises where an inventory cannot, and stays subject-neutral.
    """
    bare = re.sub(r"[^\w\u0600-\u06FF]", "", word)
    if len(bare) < 4 or not bare.isascii() or not bare.isalpha():
        return False
    if bare[:1].isupper():
        # A capitalised token mid-phrase is part of a proper name
        # ("Archduke Franz Ferdinand"), not a predicate.
        return False
    lowered = bare.lower()
    if lowered.endswith("ed") and len(lowered) > 4:
        return True
    if lowered.endswith("s"):
        # A noun-shaped suffix is only a hint, never the decision: "partitions",
        # "functions" and "results" all end in -tions/-s and are verbs as often
        # as nouns. The caller resolves the ambiguity structurally, by looking
        # at whether a complement follows; this returns True for any -s token so
        # that check is reached.
        return True
    return False


def _predicate_follows(following: str) -> bool:
    """True when the text after a candidate span still supplies a predicate.

    Used to decide whether an ambiguous -s/-ed token inside the span is the
    sentence's verb or a noun modifier. Punctuation ends the search: a clause
    boundary means the span's own clause is already complete.
    """
    for raw in following.split():
        # A clause boundary ends the search before anything after it counts:
        # in "Foreshadowing shapes expectation, AND IT MAKES ...", the verb
        # after the comma belongs to a coordinated clause, not to this span.
        if re.search(r"[,;:.]", raw):
            return False
        bare = re.sub(r"[^\w\u0600-\u06FF]", "", raw)
        if not bare:
            continue
        lowered = bare.lower()
        if _SUBORDINATOR_TOKEN.match(lowered):
            return False
        if lowered in _PREDICATE_STOP or _looks_like_finite_verb(raw):
            return True
    return False


def _trim_to_subject(term: str, following: str = "") -> str:
    """Cut a candidate term at the first predicate word.

    ``"Mitochondria are membrane-bound organelles"`` names the concept
    ``"Mitochondria"``; everything from the verb onwards is the claim, not the
    name.
    """
    words = term.split()
    # A subordinator opens a new clause ("Imperialism increased friction
    # BECAUSE industrial powers competed"). Everything from there on belongs to
    # that clause, including any verb, so the name ends here AND the text after
    # the span can no longer supply this clause's predicate.
    for index, word in enumerate(words):
        if index == 0:
            continue
        bare = re.sub(r"[^\w\u0600-\u06FF]", "", word).lower()
        # A predicate word inside the span already terminates the name, and it
        # does so *before* any subordinator further along ("Golgi apparatus IS
        # defined AS ..."). Stop scanning so the clause-truncation below cannot
        # cut earlier than the real predicate.
        if bare in _PREDICATE_STOP:
            break
        if _SUBORDINATOR_TOKEN.match(bare):
            words = words[:index]
            following = ""
            break
    kept: list[str] = []
    for index, word in enumerate(words):
        bare = re.sub(r"[^\w\u0600-\u06FF]", "", word).lower()
        if bare in _PREDICATE_STOP:
            break
        # A subordinator starts a new clause, so the name ended before it:
        # "Imperialism increased friction BECAUSE industrial powers competed".
        if index > 0 and _SUBORDINATOR_TOKEN.match(bare):
            break
        # Beyond the last captured word, look at what the *sentence* continues
        # with. The subject-head window is bounded, so a predicate can land on
        # its final token with its complement just outside the span -- which is
        # how "multilevel queue scheduling algorithm partitions" survived.
        if index + 1 < len(words):
            nxt = words[index + 1]
        else:
            nxt = following.split()[0] if following.split() else ""
        # Never cut at the very first word: the head noun itself may end in -s
        # ("Ribosomes are ...", "Buffers are ...").
        #
        # A verb must also be the LAST token for the cut to be safe. In
        # "Related rates problems use ...", "rates" is morphologically a verb
        # but is followed by "problems", so it is a noun modifier inside the
        # name. A genuine predicate runs to the end of the candidate span,
        # because _SUBJECT_HEAD only ever captures the sentence's opening
        # words -- so a verb with more name-like tokens after it is not one.
        # A morphological verb is only a real predicate when what follows opens
        # a complement ("problems use THE chain rule") or nothing follows. When
        # another bare noun follows ("Related rates PROBLEMS"), the token was a
        # noun modifier inside the name.
        # Structural, not lexical: a token is the predicate when a complement
        # follows it ("... partitions THE ready queue", "... differs FROM
        # deposition"), or when nothing follows and its shape is unambiguously
        # verbal. When another bare noun follows ("Related rates PROBLEMS") the
        # token is a modifier inside the name. This is what lets the rule work
        # on vocabulary it has never seen.
        # A bare-form verb agreeing with a plural subject ("Ionic bonds DIFFER
        # from ...", "Glaciers SHAPE landscapes") carries no -s or -ed, so
        # morphology cannot see it. Its position does: it sits after the head
        # noun and takes a complement, which is the signature of a predicate
        # rather than of a noun modifier. Requiring BOTH a preceding plural
        # head and a following complement keeps compound names intact --
        # "Related rates problems" has no complement after "problems".
        if (
            index > 0
            and not _looks_like_finite_verb(word)
            and nxt
            and _COMPLEMENT_OPENER.match(nxt)
            and _looks_like_finite_verb(words[index - 1])
            and not word[:1].isupper()
        ):
            break
        # An irregular past tense carries no -ed or -s ("the Triple Alliance
        # BOUND Germany", "the plan HELD the line"), so morphology cannot see
        # it. Capitalisation can: a lower-case token sitting between two
        # capitalised words inside a proper name is the verb joining them, not
        # part of either name. Orthographic, so it needs no verb vocabulary.
        if (
            index > 0
            and kept
            and not word[:1].isupper()
            and kept[-1][:1].isupper()
            and nxt[:1].isupper()
            and not _looks_like_finite_verb(word)
        ):
            break
        if index > 0 and _looks_like_finite_verb(word):
            if nxt and _COMPLEMENT_OPENER.match(nxt):
                break
            if not nxt and not _NOUNLIKE_S_SUFFIX.search(
                re.sub(r"[^\w]", "", word).lower()
            ):
                break
            # A subject noun phrase is followed by its predicate. When the text
            # after the span supplies one ("Related rates problems USE ..."),
            # the ambiguous token was a modifier inside the name. When no
            # predicate follows, the sentence's verb must lie *within* the span
            # -- which is exactly what "Foreshadowing shapes expectation" and
            # "sediment settles and builds" are -- so cut here. This reads the
            # sentence's own structure rather than any vocabulary, so it holds
            # on documents whose verbs no list anticipates.
            # "No predicate after this token" must consider the rest of the
            # span as well as the text beyond it. In "Golgi apparatus IS
            # defined as", the real predicate ("is") sits later in the span, so
            # the ambiguous "apparatus" is a head noun, not the verb.
            rest = " ".join(words[index + 1 :])
            if nxt and not _predicate_follows(f"{rest} {following}".strip()):
                break
        kept.append(word)
    # A trailing prepositional phrase that opens a new modifier is not part of
    # the name: "assassination of Archduke Franz Ferdinand IN JUNE" names the
    # event, and "in June" is circumstance. "of"-phrases are kept because they
    # are the head's own complement ("assassination OF Archduke ...").
    # Cutting at a predicate can leave a stranded adverb ("Germany THEN").
    # An adverb modifies the verb that was just removed, so it is not part of
    # the name either.
    while len(kept) >= 2 and _STRANDED_MODIFIER.match(kept[-1]):
        kept = kept[:-1]
    while len(kept) >= 2 and kept[-2].lower() in _TRAILING_MODIFIER_PREPOSITIONS:
        kept = kept[:-2]
    if kept and kept[-1].lower() in _TRAILING_MODIFIER_PREPOSITIONS:
        kept = kept[:-1]
    return " ".join(kept).strip()


#: A plural common noun: "-s" but not the "-ss/-us/-is" endings that are
#: singular, and not a capitalised proper name.
_PLURAL_HEAD = re.compile(r"^\w.*(?<![su])s$", re.IGNORECASE)


#: Adverb-shaped tails that can only modify a verb, never head a noun phrase.
_STRANDED_MODIFIER = re.compile(
    r"^(?:then|now|later|soon|thus|hence|also|already|still|again|often|always|"
    r"never|usually|generally|typically|eventually|finally|therefore|however|"
    r"\w+ly)[^\w]*$",
    re.IGNORECASE,
)


#: Prepositions that introduce circumstance rather than the head noun's own
#: complement. "of" is deliberately absent: it binds to the head.
_TRAILING_MODIFIER_PREPOSITIONS = frozenset(
    {"in", "on", "at", "during", "after", "before", "since", "from", "by", "with"}
)


#: Words that end a noun phrase.  Everything from here on is predicate, not
#: name, so a candidate term is cut at the first one.
_PREDICATE_STOP = frozenset(
    """is are was were be been being has have had do does did can could may might must
    should would will shall which that who whose when where while to for with from by
    consists contains includes occurs occur uses use used produces produce generate
    generates refers refer means states state exists exist proceeds proceed lacks lack
    breaks break carries carry houses house converts convert modifies modify allows
    allow regulates regulate assigns assign selects select chooses choose schedules
    schedule executes execute runs run holds hold requires require provides provide
    describes describe measures measure represents represent equals equal gives give
    takes take makes make keeps keep prevents prevent enables enable causes cause
    determines determine depends depend applies apply write writes writing said says""".split()
)

# A concept name cannot begin with a preposition, conjunction, or pronoun: a
# phrase like "for every action there" is a clause fragment, not a name.
_FUNCTION_WORD_START = re.compile(
    r"^(?:for|with|from|by|to|in|on|at|as|of|into|about|between|within|through|during|"
    r"after|before|since|because|if|when|while|that|which|we|you|they|it|he|she|there|"
    r"here|its|their|our|his|her)\b",
    re.IGNORECASE,
)


#: A correlative comparative: "The greater the inertial mass of an object, the
#: smaller the acceleration produced by a given force." Both halves are
#: comparative phrases, not subject-predicate clauses, so the subject-head
#: reader takes "greater the inertial mass" for a concept name and leaves the
#: fragment "of an object, the smaller the acceleration ..." behind as its
#: evidence. Domain-neutral: this is a construction, not a subject.
#: Both halves are required: "The greater X ..., the smaller Y ...". Matching
#: only the opening would reject ordinary subjects like "The larger organelle
#: is ...", which are perfectly good concept names.
_CORRELATIVE_COMPARATIVE = re.compile(
    r"^\s*the\s+(?:\w+er|more|less|greater|smaller|larger|fewer|higher|lower)\b"
    r"[^,]{3,120},\s*the\s+(?:\w+er|more|less|greater|smaller|larger|fewer|higher|lower)\b",
    re.IGNORECASE,
)


def _candidate_terms(sentence: str) -> list[tuple[str, str]]:
    """Extract (term, knowledge_type) candidates from one teaching sentence.

    Sentences that begin mid-clause (a PDF page break splitting one sentence)
    can support a concept as evidence, but they never *name* one: their first
    words are a continuation, not a subject.
    """
    if not re.match(r"^[A-Z\u0600-\u06FF]", sentence.strip()):
        return []
    found: list[tuple[str, str]] = []
    for pattern, knowledge_type in _TERM_PATTERNS:
        for match in pattern.finditer(sentence):
            term = _trim_to_subject(
                _LEADING_DETERMINER.sub("", match.group(1).strip()).strip(),
                sentence[match.end(1):],
            )
            if _acceptable_term(term):
                found.append((term, knowledge_type))
    if found:
        return found
    # No explicit definition: fall back to the grammatical subject, but only
    # after discarding any discourse opener so that "In contrast, a prokaryotic
    # cell ..." yields "prokaryotic cell" rather than "In contrast".
    #
    # A leading subordinate clause is discarded first, for the same reason
    # sentence_subject discards it: "Although the speed is constant, the
    # direction of velocity is continuously changing" concedes something about
    # speed and asserts something about direction. Naming "speed" from it makes
    # a concept whose evidence, once its name is removed, is only the fragment
    # "constant, the direction of velocity is continuously changing".
    trimmed = sentence.strip()
    if _CORRELATIVE_COMPARATIVE.match(trimmed):
        return found
    subordinate = _LEADING_SUBORDINATE.match(trimmed)
    if subordinate:
        trimmed = trimmed[subordinate.end() :].strip()
    trimmed = _LEADING_ADVERB.sub("", trimmed, count=1).strip()
    trimmed = _DISCOURSE_OPENER.sub("", trimmed, count=1).strip()
    match = _SUBJECT_HEAD.match(trimmed) or _SUBJECT_HEAD.match(trimmed.capitalize())
    if match:
        term = _trim_to_subject(
            _LEADING_DETERMINER.sub("", match.group(1).strip()).strip(),
            trimmed[match.end(1):],
        )
        if _acceptable_term(term):
            found.append((term, infer_knowledge_type(sentence)))
    return found


#: "commonly abbreviated as PCB", "(SJF)", "also known as the law of inertia" —
#: the document telling us two names denote one concept.
_ALIAS_DECLARATION = re.compile(
    r"(?P<full>[A-Za-z][\w\- ']{2,60}?)\s*"
    r"(?:\(\s*(?P<abbr1>[A-Za-z][\w\-]{1,20})\s*\)|"
    r",?\s*(?:commonly\s+)?(?:abbreviated|known|referred\s+to|called)\s+"
    r"(?:as\s+)?(?P<abbr2>[A-Za-z][\w\- ']{1,40}?)(?=[,.;]|$))",
)


def _declared_aliases(sentences: list[SourceSentence]) -> list[tuple[str, str]]:
    """Name pairs the document itself declares equivalent."""
    pairs: list[tuple[str, str]] = []
    for sentence in sentences:
        for match in _ALIAS_DECLARATION.finditer(sentence.text):
            full = (match.group("full") or "").strip()
            abbr = (match.group("abbr1") or match.group("abbr2") or "").strip()
            if not full or not abbr:
                continue
            if normalize_question_text(full) == normalize_question_text(abbr):
                continue
            pairs.append((full, abbr))
    return pairs


def _has_own_definition(key: str, entry: dict[str, Any]) -> bool:
    """True when the document defines this term in its own right."""
    name = re.escape((entry.get("name") or key).strip())
    pattern = re.compile(
        rf"\b(?:the\s+|a\s+|an\s+)?{name}\b\s+(?:is|are)\s+"
        rf"(?:defined\s+as|the\s|a\s|an\s)",
        re.IGNORECASE,
    )
    return any(pattern.search(item.text) for item in entry.get("evidence", []))


def _merge_alias_groups(
    grouped: dict[str, dict[str, Any]], sentences: list[SourceSentence]
) -> dict[str, dict[str, Any]]:
    """Fold aliases of one concept together.

    "Round Robin" and "Round Robin scheduling", or "SJF" and "Shortest Job
    First", are one idea. Left separate they consume two slots and the quiz
    asks the same thing twice under different names. Merging is driven by the
    document's own alias declarations plus containment, never a term list.
    """
    canonical_of: dict[str, str] = {}

    # 1. Aliases the document declares outright.
    for full, abbr in _declared_aliases(sentences):
        full_key, abbr_key = normalize_question_text(full), normalize_question_text(abbr)
        if full_key in grouped and abbr_key in grouped:
            canonical_of[abbr_key] = full_key

    # 2. A shorter name that is a prefix of a longer one, where the extra words
    #    are a generic qualifier: "Round Robin" / "Round Robin scheduling".
    #    Containment alone is not enough — "cell" is a prefix of "cell theory",
    #    yet a theory about cells is not a cell. The deciding signal is whether
    #    the document defines the shorter name in its own right: if it does, it
    #    is a concept of its own and must survive.
    keys = sorted(grouped, key=len)
    # A word that recurs across many of this document's concept names is a
    # topic label ("scheduling" in an OS chapter), not what distinguishes one
    # concept from another. Derived from the document, so no domain terms are
    # hardcoded: in a biology chapter "theory" appears once and stays
    # distinguishing, keeping "cell" and "cell theory" apart.
    name_token_counts: dict[str, int] = {}
    for candidate in keys:
        for token in set(content_token_list(candidate)):
            name_token_counts[token] = name_token_counts.get(token, 0) + 1
    generic_qualifiers = {
        token for token, hits in name_token_counts.items() if hits >= 3
    }

    for short in keys:
        short_tokens = content_token_list(short)
        if not short_tokens or _has_own_definition(short, grouped[short]):
            continue
        for long in keys:
            if long == short or short in canonical_of:
                continue
            long_tokens = content_token_list(long)
            if len(long_tokens) <= len(short_tokens):
                continue
            if long_tokens[: len(short_tokens)] != short_tokens:
                continue
            extra = set(long_tokens[len(short_tokens) :])
            if extra <= _BARE_CONTAINER_NOUNS or extra <= generic_qualifiers:
                canonical_of[short] = long

    if not canonical_of:
        return grouped

    merged: dict[str, dict[str, Any]] = {}
    for key, entry in grouped.items():
        target = canonical_of.get(key, key)
        while target in canonical_of and canonical_of[target] != target:
            target = canonical_of[target]
        if target == key or target not in grouped:
            merged.setdefault(key, entry)
            continue
        host = merged.setdefault(target, dict(grouped[target]))
        host["types"] = [*host.get("types", []), *entry.get("types", [])]
        seen = {item.text for item in host.get("evidence", [])}
        for item in entry.get("evidence", []):
            if len(host["evidence"]) >= 3:
                break
            if item.text not in seen:
                host["evidence"].append(item)
                seen.add(item.text)
    return merged


def _name_stem(word: str) -> str:
    """Fold inflection for name comparison only (not for display)."""
    bare = re.sub(r"[^\w\u0600-\u06FF]", "", word).casefold()
    if bare.endswith("ies") and len(bare) > 4:
        return bare[:-3] + "y"
    # "-ses/-xes/-zes/-ches/-shes" are plurals of stems that already end in a
    # sibilant ("processes" -> "process"); a bare "-es" elsewhere is usually
    # just "-e" plus "-s" ("rules"). Strip only "s" in that case so the stemmer
    # is idempotent: stem("process") must equal stem("processes").
    if re.search(r"(?:s|x|z|ch|sh)es$", bare) and len(bare) > 4:
        return bare[:-2]
    if bare.endswith("s") and not bare.endswith("ss") and len(bare) > 3:
        return bare[:-1]
    return bare


def _name_key(name: str) -> tuple[str, ...]:
    return tuple(k for k in (_name_stem(w) for w in name.split()) if k)


def _consolidate_prefix_names(
    grouped: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Merge a long candidate into a shorter one the document also names.

    Morphology cannot reliably tell a predicate ("Ionic bonds DIFFER") from a
    noun modifier ("Related rates PROBLEMS"), and no closed verb list ever
    covers the next document's vocabulary. The document itself supplies the
    missing evidence: when it *elsewhere* names the exact token-prefix of a
    longer candidate -- "unreliable narrator" alongside "unreliable narrator
    forces active", "ionic bond" alongside "Ionic bonds differ" -- the prefix is
    the thing being taught and the extra tokens are the claim being made about
    it.

    Only the document's own concept inventory is consulted, so this carries no
    vocabulary, no subject assumptions, and no grammar rules; it behaves the
    same on chemistry, literature, and history. Evidence sentences from the
    longer form are preserved on the surviving concept, because those sentences
    genuinely teach about it.
    """
    by_key = {_name_key(entry["name"]): key for key, entry in grouped.items()}

    # A one-word candidate that is the HEAD of a longer name the document also
    # uses is a shortened back-reference, not a second concept: "The plan
    # required ..." after "The Schlieffen Plan was ...". Merging it keeps the
    # sentence's teaching attached to the real concept instead of inventing a
    # vague one called "plan". This is the mirror of the prefix rule below and
    # likewise consults only the document's own inventory, so no list of
    # generic nouns has to be maintained.
    head_index: dict[tuple[str, ...], list[str]] = {}
    for key, entry in grouped.items():
        tokens = _name_key(entry["name"])
        if len(tokens) > 1:
            head_index.setdefault(tokens[-1:], []).append(key)
    for key, entry in list(grouped.items()):
        tokens = _name_key(entry["name"])
        if len(tokens) != 1:
            continue
        owners = [owner for owner in head_index.get(tokens, []) if owner != key]
        # Ambiguous when several longer names share the head; leave it alone.
        if len(owners) == 1:
            by_key[tokens] = owners[0]

    merged: dict[str, dict[str, Any]] = {}
    for key, entry in grouped.items():
        tokens = _name_key(entry["name"])
        target = key
        # A single-token name may resolve to the longer name it abbreviates.
        if len(tokens) == 1:
            owner = by_key.get(tokens)
            if owner is not None and owner != key:
                host = merged.setdefault(owner, grouped[owner])
                host["types"].extend(entry["types"])
                for item in entry["evidence"]:
                    if len(host["evidence"]) >= 3:
                        break
                    if all(item.text != seen.text for seen in host["evidence"]):
                        host["evidence"].append(item)
                continue
        # Longest proper prefix wins, so a three-word claim collapses onto the
        # two-word concept rather than onto a one-word fragment.
        for width in range(len(tokens) - 1, 0, -1):
            candidate = by_key.get(tokens[:width])
            if candidate is None or candidate == key:
                continue
            # Sharing a prefix is not enough. "cell theory" extends "cell" with
            # another NOUN and names a genuinely different concept, while
            # "unreliable narrator forces active" extends "unreliable narrator"
            # with a PREDICATE and merely asserts something about it. Only the
            # second is a claim, so only the second may be absorbed.
            extra = entry["name"].split()[width:]
            if not any(_looks_like_finite_verb(word) for word in extra):
                continue
            target = candidate
            break
        if target == key:
            merged.setdefault(key, entry)
            continue
        host = merged.setdefault(target, grouped[target])
        host["types"].extend(entry["types"])
        for item in entry["evidence"]:
            if len(host["evidence"]) >= 3:
                break
            if all(item.text != seen.text for seen in host["evidence"]):
                host["evidence"].append(item)
    return merged


def deterministic_understanding(
    units: list[SourceUnit], *, title: str
) -> DocumentUnderstanding:
    """Provider-free study map built only from explanatory source sentences.

    This path is deliberately conservative: it only recognises a concept when a
    sentence *explains* it.  Headings, repeated phrases, captions, and metadata
    contribute nothing, so a document with no teaching prose yields an empty —
    and therefore unusable — understanding rather than filler.
    """
    sentences = iter_sentences(units)
    teaching = [sentence for sentence in sentences if _is_teaching_sentence(sentence.text)]

    grouped: dict[str, dict[str, Any]] = {}
    for sentence in teaching:
        for term, knowledge_type in _candidate_terms(sentence.text):
            if is_generic_label(term) or is_boilerplate_text(term) or is_layout_detail(term):
                continue
            key = normalize_question_text(term)
            if not key or len(key) < 3:
                continue
            entry = grouped.setdefault(
                key,
                {
                    "name": term,
                    "types": [],
                    "evidence": [],
                },
            )
            entry["types"].append(knowledge_type)
            if len(entry["evidence"]) < 3:
                entry["evidence"].append(Evidence(text=sentence.text, page=sentence.page))

    grouped = _consolidate_prefix_names(grouped)

    # A sentence can teach about a concept without naming a new one. "The
    # greater the inertial mass of an object, the smaller the acceleration
    # produced by a given force" is a correlative comparative: it has no
    # subject noun phrase to extract, so the loop above skips it entirely and
    # the concept it develops loses a mention it genuinely earned. Attach such
    # sentences as supporting evidence to concepts already named, judged by the
    # same subject-attribution rule used elsewhere rather than by mere
    # occurrence of the name.
    for sentence in teaching:
        if _candidate_terms(sentence.text):
            continue
        correlative = _CORRELATIVE_COMPARATIVE.match(sentence.text.strip())
        for entry in grouped.values():
            if len(entry["evidence"]) >= 3:
                continue
            # In a correlative the topic sits inside the opening comparative
            # phrase ("The greater the inertial mass of an object, ..."), never
            # in subject position, so subject attribution cannot see it. The
            # phrase is bounded by the comma, which keeps this as strict as the
            # subject rule: a name mentioned later in the sentence still does
            # not qualify.
            if correlative:
                head = sentence.text.split(",", 1)[0]
                if entry["name"].casefold() not in head.casefold():
                    continue
            elif not _states_claim_about(entry["name"], sentence.text):
                continue
            if any(item.text == sentence.text for item in entry["evidence"]):
                continue
            entry["evidence"].append(Evidence(text=sentence.text, page=sentence.page))

    grouped = _merge_alias_groups(grouped, sentences)

    staged: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    id_lookup: dict[str, str] = {}
    for index, (key, entry) in enumerate(grouped.items()):
        evidence: list[Evidence] = entry["evidence"]
        if not evidence:
            continue
        types: list[str] = entry["types"]
        # Prefer the strongest knowledge type observed for this term. Several
        # types share a value (process and cause_effect are both 0.95), so a
        # tie on value *and* observation count is common; without a final
        # deterministic key `max` over a set resolved it by hash order, and the
        # same document could be classified differently between runs. The type
        # name is an arbitrary but stable last resort.
        knowledge_type = max(
            sorted(set(types)),
            key=lambda value: (
                KNOWLEDGE_TYPE_VALUE.get(value, 0.0),
                types.count(value),
                value,
            ),
        )
        concept_id = _slug(entry["name"], f"concept-{index + 1}")
        while concept_id in used_ids:
            concept_id = f"{concept_id}-{index + 1}"
        used_ids.add(concept_id)
        id_lookup[concept_id] = concept_id
        id_lookup[key] = concept_id
        staged.append(
            {
                "concept_id": concept_id,
                "name": entry["name"],
                "description": evidence[0].text,
                "topic": "",
                "knowledge_type": knowledge_type,
                "evidence": tuple(evidence),
                "pages": tuple(sorted({item.page for item in evidence})),
                "raw": _RawConcept(name=entry["name"], teaching_emphasis="medium"),
                "targets": [],
            }
        )

    if not staged:
        return DocumentUnderstanding(
            title=title,
            subject="Unknown",
            summary="",
            main_topics=(),
            concepts=(),
            relationships=(),
            learning_objectives=(),
            source="deterministic",
        )

    concepts = _finalize_concepts(staged, sentences=sentences, id_lookup=id_lookup)
    relationships = _derive_relationships(concepts, teaching)
    concepts = _apply_relationship_centrality(concepts, relationships)
    topics = _derive_topics(concepts, units)
    objectives = _derived_objectives(concepts, sentences)
    summary = _deterministic_summary(list(concepts), list(topics), title)
    return DocumentUnderstanding(
        title=title,
        subject=_infer_subject(concepts, title),
        summary=summary,
        main_topics=topics,
        concepts=concepts,
        relationships=relationships,
        learning_objectives=objectives,
        source="deterministic",
    )


def _derive_relationships(
    concepts: tuple[ConceptNode, ...], sentences: list[SourceSentence]
) -> tuple[Relationship, ...]:
    """Connect two concepts when one sentence explicitly relates both."""
    relationships: list[Relationship] = []
    seen: set[tuple[str, str, str]] = set()
    for sentence in sentences:
        tokens = content_tokens(sentence.text)
        present = [node for node in concepts if content_tokens(node.name) <= tokens]
        if len(present) < 2:
            continue
        if _CAUSE_MARKERS.search(sentence.text):
            kind = "cause"
        elif _COMPARISON_MARKERS.search(sentence.text):
            kind = "contrast"
        elif _PROCESS_MARKERS.search(sentence.text):
            kind = "produces"
        else:
            kind = "related"
        for left, right in zip(present, present[1:]):
            key = (left.concept_id, right.concept_id, kind)
            if key in seen:
                continue
            seen.add(key)
            relationships.append(
                Relationship(
                    source_id=left.concept_id,
                    target_id=right.concept_id,
                    kind=kind,
                    evidence=sentence.text[:400],
                    pages=(sentence.page,),
                )
            )
        if len(relationships) >= 40:
            break
    return tuple(relationships)


def _derive_topics(
    concepts: tuple[ConceptNode, ...], units: list[SourceUnit]
) -> tuple[Topic, ...]:
    """Group concepts under the nearest preceding heading on their page."""
    headings: dict[int, list[str]] = {}
    for unit in units:
        for line in unit.text.splitlines():
            line = line.strip()
            if line and is_heading_like(line) and not is_generic_label(line):
                headings.setdefault(unit.page, []).append(line)

    topics: dict[str, list[ConceptNode]] = {}
    for node in concepts:
        page = node.source_pages[0] if node.source_pages else 1
        name = (headings.get(page) or [node.topic or node.name])[0]
        topics.setdefault(name, []).append(node)
    return tuple(
        Topic(
            name=name,
            subtopics=(),
            concept_ids=tuple(node.concept_id for node in nodes),
            pages=tuple(sorted({page for node in nodes for page in node.source_pages})),
        )
        for name, nodes in list(topics.items())[:12]
    )


# --------------------------------------------------------------------------- #
# Rendering for downstream prompts / diagnostics
# --------------------------------------------------------------------------- #


def understanding_block(understanding: DocumentUnderstanding, *, limit: int = 20) -> str:
    """Compact, human-readable rendering of the study map for prompts/logs."""
    lines = [
        f"SUBJECT: {understanding.subject}",
        f"SUMMARY: {understanding.summary}",
        "MAIN TOPICS:",
    ]
    for topic in understanding.main_topics[:10]:
        subtopics = f" — subtopics: {', '.join(topic.subtopics)}" if topic.subtopics else ""
        lines.append(f"- {topic.name} (pages {list(topic.pages)}){subtopics}")
    lines.append("IMPORTANT CONCEPTS (ranked by educational importance, not frequency):")
    for node in understanding.important_concepts(limit=limit):
        lines.append(
            f"- [{node.concept_id}] {node.name} — type={node.knowledge_type}; "
            f"importance={node.importance:.2f}; pages={list(node.source_pages)}; "
            f"evidence={node.primary_evidence!r}"
        )
    if understanding.relationships:
        lines.append("KNOWLEDGE RELATIONSHIPS:")
        for relationship in understanding.relationships[:12]:
            lines.append(
                f"- {relationship.source_id} --{relationship.kind}--> {relationship.target_id}"
            )
    if understanding.learning_objectives:
        lines.append("LEARNING OBJECTIVES:")
        for objective in understanding.learning_objectives[:8]:
            lines.append(f"- {objective.text}")
    return "\n".join(lines)
