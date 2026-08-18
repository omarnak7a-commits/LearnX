"""Deterministic question writer driven by the semantic study map.

This is *not* the old sentence-transformation fallback.  It cannot see raw
pages, headings, or frequency counts: its only inputs are quiz blueprints
(concept + knowledge target + cognitive skill + verified evidence) and the
document understanding they came from.

It exists so that a provider outage degrades to "a smaller, still meaningful
quiz" rather than "a quiz of trivia".  Everything it writes goes through the
same backend gates, semantic deduplication, and quality scoring as provider
prose.  Where it cannot write a genuinely good question — most notably a
transfer/application scenario, which requires authoring a situation the source
never states — it writes nothing at all, and the pipeline reports the
controlled "AI quiz generation unavailable" state rather than padding.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_scoring import content_tokens, normalize_question_text
from app.services.quiz_understanding import DocumentUnderstanding

#: Cognitive skills this writer can express honestly without a provider.
#: ``application`` is deliberately absent: a transfer question needs a scenario
#: the source never states, and inventing one is precisely the failure this
#: rewrite exists to remove.
SUPPORTED_SKILLS: frozenset[str] = frozenset(
    {
        "understanding",
        "comparison",
        "cause_effect",
        "process_order",
        "classification",
        "factual_recall",
        "misconception",
    }
)

_LEADING_COPULA = re.compile(
    r"^(?:,|:|-|—)?\s*(?:is|are|was|were|can\s+be|may\s+be)?\s*"
    # A reporting verb introduces the claim without being part of it: the
    # answer to "What does Newton's First Law state?" is the law itself, not
    # "states that ...". Stripped for the same reason as "is defined as".
    r"(?:defined\s+as|known\s+as|called|refers?\s+to|means|"
    r"states?\s+that|states?|asserts?\s+that|holds?\s+that|"
    r"establishes?\s+that|specifies?\s+that|says?\s+that)?\s*",
    re.IGNORECASE,
)
_APPOSITIVE = re.compile(
    r"^\s*,?\s*(?:or|also\s+called|also\s+known\s+as|commonly\s+called)\s+[^,]{1,40},\s*",
    re.IGNORECASE,
)
#: Only *strong* clause boundaries may truncate a claim.  A bare comma is not
#: one: "a cell that contains a true, membrane-bound nucleus" would be cut to
#: "a cell that contains a true", which reads as a broken fragment.
_CLAUSE_BOUNDARY = re.compile(
    # A colon or dash separates a statement from its elaboration: "for every
    # action there is an equal and opposite reaction: whenever object A exerts
    # a force on object B, ...". The part before it stands alone, which is
    # exactly what a clause boundary means.
    r":\s+|\s+—\s+|\s+--\s+"
    r"|;\s+"
    r"|,?\s+(?:which|whereas|while|although|though|because|so\s+that|and\s+is|and\s+are)\s+"
    r"|,\s+(?:and|but|or)\s+"
    r"|\s+(?:ensuring|allowing|preventing|resulting\s+in|before\s+they|along\s+with|"
    r"such\s+as|commonly\s+(?:called|abbreviated|remembered))\s+",
    re.IGNORECASE,
)

# A clause that ends on a dangling function word reads as a broken fragment.
_DANGLING_TAIL = re.compile(
    r"\b(?:the|a|an|of|to|in|on|for|with|from|by|as|at|into|and|or|but|that|which|"
    # "it"/"this"/"these" are NOT listed: as a pronoun *object* each legitimately
    # closes a clause ("...approaches some value, without ever reaching it"),
    # and treating them as dangling discarded whole definitions. A stranded
    # pronoun *subject* is caught by the finite-verb tests instead.
    r"is|are|was|were|be|been|its|their|through|during|before|"
    r"after|between|within|along|commonly|abbreviated|called|known|"
    # A transitive past participle still needs its complement: "...equal to the
    # mass of the object multiplied" is cut before "by its acceleration".
    r"provided|assuming|given\s+that|such\s+that|so\s+long\s+as|"
    r"multiplied|divided|combined|compared|added|subtracted|expressed|"
    r"measured|defined|determined|calculated|represented|denoted|given|"
    r"followed|preceded|accompanied|replaced|separated)$",
    re.IGNORECASE,
)

#: A relational predicate whose second operand was cut away. "...is equal to
#: the mass of the object" is grammatical but states something the document
#: never claims — the original said "equal to the mass ... MULTIPLIED BY its
#: acceleration". Silently dropping the rest turns a true statement into a
#: false one, which is worse than dropping the question.
_TRUNCATES_A_RELATION = re.compile(
    r"\b(?:equal\s+to|equals|proportional\s+to|greater\s+than|less\s+than|"
    r"the\s+same\s+as|equivalent\s+to|relative\s+to|divided\s+by|"
    r"multiplied\s+by|the\s+ratio\s+of|the\s+product\s+of|the\s+sum\s+of)\s+"
    # A reciprocal pronoun IS the second operand: "relative to each other" and
    # "equal to one another" are complete relations, not truncated ones.
    r"(?!(?:each\s+other|one\s+another)\b)"
    r"(?:[\w'’\-]+\s+){0,6}[\w'’\-]+$",
    re.IGNORECASE,
)

#: A relational predicate left without its second operand anywhere in the text.
_OPEN_RELATION = re.compile(
    r"\b(?:equal|equals|equal\s+to|proportional|proportional\s+to|greater|"
    r"less|equivalent|relative|multiplied|divided|the\s+ratio|the\s+product|"
    r"the\s+sum)\s*$",
    re.IGNORECASE,
)

#: Words that can only continue the phrase already under way: a preposition or
#: infinitival marker needs an object, so a cut placed before one lands inside
#: an unfinished phrase ("with respect" / "to time").
_PHRASE_CONTINUATION = frozenset(
    """to of in on for with from by as at into onto upon through during before
    after between within across against over under about around along than
    that which who whom whose""".split()
)

#: A trailing operator with nothing after it ("... f(x)/g(x) =") states half a
#: relation. Notation, not subject knowledge, so this stays domain-neutral.
_TRAILING_OPERATOR = re.compile(r"[=<>≤≥≠≈≡+\-*/^]\s*$")


#: A word that cannot itself close a phrase. An adverb modifies something that
#: has to follow it ("without necessarily |reaching it"), and a comparative
#: needs its complement ("two or more |related quantities").
_NEEDS_A_COMPLEMENT = re.compile(
    # "each other"/"one another" end a clause legitimately, so "other" there is
    # not a modifier waiting for a noun.
    r"(?<!each\s)(?<!one\s)"
    # "\w+ly" targets adverbs ("acts differently"), but it also matched the
    # proper nouns Italy, Sicily, Chile and July, which are complete objects --
    # "bound Germany, Austria-Hungary, and Italy" was discarded as incomplete.
    # A capitalised token is a name, so require lower case.
    # (?-i:...) keeps this one alternative case-sensitive inside an otherwise
    # case-insensitive pattern.
    r"\b(?:(?-i:[a-z]+ly)|more|less|fewer|most|least|other|such|same|both|either|"
    r"neither|very|quite|rather|nearly|almost|"
    # A transitive verb stranded without its object: "the operating system
    # decides" stops before saying what it decides.
    r"decides?|determines?|selects?|chooses?|controls?|produces?|causes?|"
    r"requires?|allows?|prevents?|affects?|includes?|contains?|uses?)$",
    re.IGNORECASE,
)


#: An enumeration in progress: "velocity, marginal cost, and growth rate".
#: Cutting at the comma before the final "and" keeps all but the last item,
#: which reads as a finished phrase but silently drops content the source
#: listed. The list is only complete once its final conjunct is included.
_INCOMPLETE_LIST = re.compile(r",\s*$")


def _continues_phrase(cleaned: str, prefix: str) -> bool:
    """True when `cleaned` carries `prefix`'s final phrase past the cut.

    Truncation is only honest at a phrase boundary. Punctuation marks one
    explicitly; otherwise two signals show the cut fell inside a phrase: the
    word dropped can only be a continuation (a preposition, an infinitival
    "to", a participle), or the last word kept still demands a complement (an
    adverb, a comparative). Either way the text does not stop where we cut it.
    """
    if _TRAILING_OPERATOR.search(prefix):
        return True
    remainder = cleaned[len(prefix) :].strip()
    if not remainder:
        return False
    # A comma followed by the list's closing conjunct means the cut fell inside
    # an enumeration, so the phrase does continue. A coordinated *clause* is
    # different: ", and it is always directed toward the centre" has its own
    # subject and verb, so the text before it stands complete. Only a conjunct
    # that is a bare phrase continues the list.
    conjunct = re.match(r"^,\s*(?:and|or)\s+(?P<rest>.+)$", remainder, re.IGNORECASE)
    if conjunct:
        # Look only as far as the conjunct itself — up to the comma that closes
        # it — not the rest of the sentence. A closing conjunct is followed by
        # the predicate belonging to the whole series ("..., and growth rate
        # ARE all derivatives"), so scanning further always finds a verb and
        # every list looked like a new clause.
        item = re.split(r",", conjunct.group("rest"), maxsplit=1)[0]
        if not _FINITE_VERB.search(item):
            return True
    # An exemplar list still open: "quantities such as velocity, marginal cost"
    # has not reached the end of its examples. Anything after the introducer
    # with no finite verb is still inside the enumeration.
    introducer = None
    for match in re.finditer(
        r"\b(?:such\s+as|including|for\s+example)\b", prefix, re.IGNORECASE
    ):
        introducer = match
    if introducer and not _FINITE_VERB.search(prefix[introducer.end() :]):
        return True
    # Multi-word continuations. "…where quantities | such as velocity" reads as
    # a finished phrase but the relative clause has not reached its verb.
    if re.match(
        r"^(?:such\s+as|including|for\s+example|e\.g\.|i\.e\.|rather\s+than)\b",
        remainder,
        re.IGNORECASE,
    ):
        return True
    if remainder[0] in ",;:.":
        return False
    if _NEEDS_A_COMPLEMENT.search(prefix.strip(" ,;:.-—")):
        return True
    nxt = re.sub(r"[^\w'’\-]", "", remainder.split()[0]).casefold()
    if not nxt:
        return False
    return nxt in _PHRASE_CONTINUATION or nxt.endswith("ing")


#: A coordinate clause that switches to a different subject: "... is
#: responsible for protein synthesis, WHILE the smooth endoplasmic reticulum
#: lacks ribosomes". Everything from the connective onward is a claim about
#: something else, so it cannot form part of this concept's answer. The same
#: rule already guards facet clauses during understanding; a claim rebuilt
#: from raw evidence needs it too.
_CONTRAST_TAIL = re.compile(
    r",\s+(?:while|whereas|but|although|though|unlike)\s+", re.IGNORECASE
)

#: A mathematical statement: a relational operator with content on both sides.
#: Domain-neutral — this is notation, not subject knowledge.
_EQUATION = re.compile(r"[\w\)\]]\s*(?:=|≠|≈|≡|<|>|≤|≥)\s*[\w\(\[\-]")

_MAX_CLAIM_WORDS = 18

#: Upper bound for a true/false statement that cannot be safely shortened.
#: A statement of a law or rule is one sentence and cannot be split: "an object
#: at rest stays at rest and an object in motion stays in motion ... unless
#: acted upon by an unbalanced external force" has no internal clause boundary
#: that leaves a true claim behind. The bound admits one complete source
#: sentence, because the alternative is losing the concept entirely.
_MAX_STATEMENT_WORDS = 45
_MIN_CLAIM_WORDS = 4


def _shorten(text: str, max_words: int = _MAX_CLAIM_WORDS) -> str:
    """Trim to a natural clause boundary, never mid-phrase.

    Returns an empty string when no clean boundary exists, so a broken
    fragment such as ``"...condenses into chromosomes during"`` can never
    become an option or a statement.
    """
    cleaned = re.sub(r"\s+", " ", text).strip().strip(" ,;:.-—")
    if not cleaned:
        return ""

    def acceptable(value: str) -> bool:
        return (
            _MIN_CLAIM_WORDS <= len(value.split()) <= max_words
            and not _DANGLING_TAIL.search(value)
            and not _TRUNCATES_A_RELATION.search(value)
            # A transitive verb or comparative left without its complement ends
            # the text mid-thought: "the operating system decides" never says
            # what it decides. _continues_phrase applies the same rule when
            # there is following text; this covers the case where the cut is at
            # the very end and there is no remainder to inspect.
            and not _NEEDS_A_COMPLEMENT.search(value.strip(" ,;:.-—"))
            and value.count("(") == value.count(")")
        )

    if acceptable(cleaned):
        return cleaned

    # Prefer the longest clean cut at a real clause boundary.
    best = ""
    for match in _CLAUSE_BOUNDARY.finditer(cleaned):
        head = cleaned[: match.start()].strip(" ,;:.-—")
        if len(head.split()) > max_words:
            break
        # Not every clause boundary is a safe stop. "...the process by which
        # the operating system decides | which process is allocated the CPU"
        # breaks before a relative pronoun, stranding a transitive verb with
        # no object. The same phrase-continuation test used for the rest of
        # _shorten decides whether the source really stops here.
        if acceptable(head) and not _continues_phrase(cleaned, head):
            best = head
    if best:
        return best

    # No clause boundary fits the budget. Cutting at an arbitrary word count
    # and walking back off function words was tried and abandoned: a boundary
    # the source does not have cannot be found by inspecting the words around
    # the cut, and every rule added to catch one fragment ("with respect",
    # "without necessarily", "two or more related") left another. Only the
    # document's own punctuation and conjunctions mark where a phrase really
    # ends. Report failure instead; callers keep the full statement, which is
    # long but true, rather than a short fragment that is neither.
    return ""


#: Plural/mass technical nouns that read correctly without an article
#: ("Mitochondria produce ATP", not "the Mitochondria produce ATP" when used
#: as a bare subject) but take "the" when the source itself does.
_PLURAL_LIKE = re.compile(r"(?:ia|ae|es|s)$", re.IGNORECASE)


#: Suffixes of nouns that are normally uncountable, so they take no article
#: when named generically ("weathering", "nationalism", "hardness").
_UNCOUNTABLE_SUFFIX = re.compile(r"(?:ing|ism|ness|ity|tion|sion|ance|ence|ment|ology|"
                                 r"graphy|metry|sophy)$", re.IGNORECASE)


def _display(name: str, evidence: str = "") -> str:
    """Read a concept name naturally inside a question sentence.

    The article comes from the source itself: if the document writes "The Golgi
    apparatus is defined as ...", the question reads "the Golgi apparatus".
    """
    stripped = name.strip()
    if not stripped or re.match(r"^(a|an|the)\s", stripped, re.IGNORECASE):
        return stripped
    if evidence and re.search(rf"\bthe\s+{re.escape(stripped)}\b", evidence, re.IGNORECASE):
        return f"the {stripped}"
    if stripped[0].islower():
        # The article must be read from the source, never invented. A bare
        # plural names a class generically ("ionic bonds differ from covalent
        # bonds"), and so does an uncountable -ing/-ism/-ness noun
        # ("weathering", "militarism") -- the document writes "differs from
        # weathering", so "the weathering" would be our wording, not its.
        # Countable singulars keep their article ("the catalyst").
        head = stripped.split()[-1]
        if _PLURAL_LIKE.search(head) or _UNCOUNTABLE_SUFFIX.search(head):
            return stripped
        return f"the {stripped}"
    # A capitalised plural noun ("Mitochondria", "Ribosomes") is a class name
    # and reads naturally in lower case without an article.
    if _PLURAL_LIKE.search(stripped) and stripped[1:] == stripped[1:].lower():
        return stripped[0].lower() + stripped[1:]
    return stripped


def _claim(evidence: str, concept_name: str, *, max_words: int = _MAX_CLAIM_WORDS) -> str:
    """The predicate a piece of evidence asserts about its concept.

    ``max_words`` lets a caller that can display a long answer ask for the full
    statement. A law stated in one unbreakable sentence yields nothing at the
    default budget, and returning "" here would silently drop the concept from
    the exam even though its evidence is perfectly good.
    """
    text = re.sub(r"\s+", " ", evidence).strip()
    if concept_name:
        # Word-bounded: an unbounded search let a short name match INSIDE a
        # word -- "is" inside "issued" -- and the text was then sliced
        # mid-token, producing the distractor "sued an ultimatum to Serbia".
        match = re.search(
            rf"\b{re.escape(concept_name)}\b", text, re.IGNORECASE
        ) or re.search(re.escape(concept_name), text, re.IGNORECASE)
        if match:
            text = text[match.end() :]
    text = _APPOSITIVE.sub("", text.strip())
    text = _LEADING_COPULA.sub("", text.strip(), count=1)
    text = text.strip(" ,;:.-—")
    if len(text.split()) < _MIN_CLAIM_WORDS:
        return ""
    # Removing the concept name only yields a predicate when the name was the
    # subject. Where it sits mid-sentence ("This law quantifies the
    # relationship | between force, mass, and acceleration") what remains
    # starts inside a phrase and is not a claim about anything.
    #
    # A leading preposition alone does not prove that: "for every action there
    # is an equal and opposite reaction" opens with one and is a complete
    # proposition. What distinguishes the fragment is that it never reaches a
    # finite verb — the stranded phrase modifies a verb that was left behind on
    # the other side of the cut.
    first = re.sub(r"[^\w'’\-]", "", text.split()[0]).casefold()
    if first in _PHRASE_CONTINUATION and not _FINITE_VERB.search(text):
        return ""
    contrast = _CONTRAST_TAIL.search(text)
    if contrast:
        head = text[: contrast.start()].strip(" ,;:.-—")
        if len(head.split()) >= _MIN_CLAIM_WORDS:
            text = head
    if _is_contentless_claim(text):
        return ""
    return _shorten(text, max_words)


#: Predicates that announce that detail follows without supplying any. "The ER
#: exists in two forms." is a real sentence and long enough to pass a word
#: count, yet as an answer it teaches nothing: the substance lives in the
#: sentences after it. Answering "what is the ER?" with "exists in two forms"
#: is exactly the kind of hollow question a teacher would strike out.
_CONTENTLESS_PREDICATE = re.compile(
    r"^(?:exists?|comes?|occurs?|appears?|is\s+found|are\s+found|is\s+classified|"
    r"are\s+classified|is\s+divided|are\s+divided|is\s+grouped|are\s+grouped|"
    r"falls?|can\s+be\s+(?:classified|divided|grouped|found))\s+"
    r"(?:in|into|as|under|within)?\s*"
    r"(?:two|three|four|five|several|many|multiple|various|different|a\s+few|"
    r"[0-9]+)\s+"
    r"(?:forms?|types?|kinds?|ways?|categories|classes|groups?|varieties|"
    r"stages?|parts?|versions?)\s*$",
    re.IGNORECASE,
)


def _is_contentless_claim(text: str) -> bool:
    """True when the predicate promises detail instead of stating it."""
    return bool(_CONTENTLESS_PREDICATE.match(text.strip(" ,;:.-—")))


def _is_sole_opportunity(
    blueprint: QuestionBlueprint, understanding: DocumentUnderstanding
) -> bool:
    """True when this blueprint is the concept's only route into the exam.

    Relaxing the answer budget is a concession, not a default: a long answer is
    worse than a short one, and applying it everywhere let easy recognition
    targets outcompete reasoning targets on other concepts. It is worth making
    only to stop a concept vanishing entirely, which happens when the concept
    states no relationship the writer can turn into a reasoning question and
    its definition is one unbreakable clause over the concise budget.
    """
    concept = understanding.concept(blueprint.concept_id)
    if concept is None:
        return False
    # A concept with a relational facet has a reasoning question available and
    # does not need the concession.
    if concept.facets:
        return False
    # Nor is the concession for every definition-only concept: granting it
    # broadly let easy recognition targets outbid reasoning targets on *other*
    # concepts, costing tier-1 coverage. It exists for the case the document
    # itself makes unavoidable — a concept ranked among the document's most
    # important, which would otherwise be absent from its own exam.
    ranked = list(understanding.important_concepts())
    leaders = {node.concept_id for node in ranked[: max(1, len(ranked) // 4)]}
    return concept.concept_id in leaders


def _claim_pool(understanding: DocumentUnderstanding) -> list[tuple[str, str, str]]:
    """Candidate distractor claims: ``(concept_id, kind, claim)``.

    ``kind`` is the *facet kind* for relational claims (purpose, effect,
    mechanism, ...) and the knowledge type for definitional ones. Tagging them
    this way lets a distractor be matched to the question's own relation, so a
    "how does it work?" question is answered against other mechanisms rather
    than against unrelated definitions.
    """
    pool: list[tuple[str, str, str]] = []
    for concept in understanding.concepts:
        claim = _claim(concept.primary_evidence, concept.name)
        if claim:
            pool.append((concept.concept_id, concept.knowledge_type, claim))
        # Relational claims make far better parallel distractors.
        for facet in concept.facets:
            clause = _shorten(facet.clause)
            if clause:
                pool.append((concept.concept_id, facet.kind, clause))
    return pool


def _distractors(
    blueprint: QuestionBlueprint,
    correct: str,
    pool: list[tuple[str, str, str]],
) -> list[str]:
    """Three same-domain claims from other concepts, length-matched."""
    correct_key = normalize_question_text(correct)
    correct_length = max(1, len(correct.split()))
    correct_numeric = bool(re.search(r"\d", correct))
    candidates = [
        (knowledge_type, claim)
        for concept_id, knowledge_type, claim in pool
        if concept_id != blueprint.concept_id and normalize_question_text(claim) != correct_key
    ]
    # Prefer claims of the same *kind* as the correct answer: a distractor for
    # "how does X work?" should be another mechanism, not a definition. Parallel
    # options are what make a wrong answer genuinely tempting rather than
    # obviously off-category.
    preferred_kind = blueprint.facet_kind or blueprint.knowledge_type
    candidates.sort(
        key=lambda item: (
            item[0] != preferred_kind,
            abs(len(item[1].split()) - correct_length),
        )
    )
    chosen: list[str] = []
    seen = {correct_key}
    kept_tokens: list[set[str]] = [content_tokens(correct)]
    for _, claim in candidates:
        trimmed = _shorten(claim, max(6, min(_MAX_CLAIM_WORDS, correct_length + 5)))
        key = normalize_question_text(trimmed)
        if not key or key in seen or len(trimmed.split()) < _MIN_CLAIM_WORDS:
            continue
        # Never mix numeric and non-numeric options: it gives the answer away.
        if bool(re.search(r"\d", trimmed)) != correct_numeric:
            continue
        # Two options that restate the same fact are not two options. Exact-key
        # matching misses this because one may carry a leading verb ("is
        # responsible for the production of X" vs "the production of X"), so
        # compare content instead: a distractor overlapping heavily with an
        # option already present is redundant, and if it overlaps the *correct*
        # answer it is arguably also correct.
        tokens = content_tokens(trimmed)
        if tokens and any(
            len(tokens & existing) / max(1, len(tokens | existing)) >= 0.60
            for existing in kept_tokens
        ):
            continue
        seen.add(key)
        kept_tokens.append(tokens)
        chosen.append(trimmed)
        if len(chosen) == 3:
            break
    return chosen


#: Connectives that introduce a genuine consequence.  Relative pronouns such
#: as "which" are excluded: they continue a description, they do not state an
#: effect, so treating them as causal would fabricate a cause/effect claim.
_EFFECT_SPLIT = re.compile(
    r"\b(?:so\s+that|because\s+of\s+this|resulting\s+in|results?\s+in|leads?\s+to|"
    r"ensuring|ensures?|allowing|allows?|preventing|prevents?|"
    r"and\s+is\s+used\s+for|is\s+used\s+for|is\s+used\s+specifically\s+in|"
    r"is\s+responsible\s+for|through\s+a\s+process\s+called)\b",
    re.IGNORECASE,
)


def _effect_clause(evidence: str) -> str:
    """The consequence half of a causal statement, if the source states one."""
    match = _EFFECT_SPLIT.search(evidence)
    if not match:
        return ""
    tail = evidence[match.end() :].strip(" ,;:.-—")
    # Stop at a switch of subject: "responsible for protein synthesis, WHILE
    # the smooth ER lacks ribosomes" states one thing about this concept and
    # another about a different one. Carrying the second half into the answer
    # makes the answer partly about something the question never asked.
    contrast = _CONTRAST_TAIL.search(tail)
    if contrast:
        head = tail[: contrast.start()].strip(" ,;:.-—")
        if head:
            tail = head
    if len(tail.split()) < _MIN_CLAIM_WORDS:
        return tail if tail else ""
    return _shorten(tail)


def _explanation(blueprint: QuestionBlueprint, reason: str) -> str:
    """Grounded explanation: the evidence plus why the answer follows."""
    evidence = re.sub(r"\s+", " ", blueprint.evidence).strip()
    return f"{evidence} That is why {reason.rstrip('.')} is correct."


def _misconception_explanation(blueprint: QuestionBlueprint, subject: str) -> str:
    """Why a swapped-subject statement is false.

    The shared helper ends every explanation with "... is correct", which is
    exactly backwards after a False answer: it told the student the statement
    they just rejected was right. A misconception needs to name the concept the
    claim actually belongs to, which is the whole point of the question.
    """
    evidence = re.sub(r"\s+", " ", blueprint.evidence).strip()
    owner = _display(blueprint.concept, blueprint.evidence)
    return (
        f"{evidence} The statement is false because this describes "
        f"{owner}, not {subject}."
    )


#: How a relational claim reads as a declarative statement.
#: ``mechanism`` has two forms because a mechanism clause may be a noun phrase
#: ("a process called cellular respiration") or a finite clause ("ribosomes
#: decode the sequence…"). "works by ribosomes decode…" is ungrammatical, so
#: the finite form gets its own template.
_FACET_ASSERTION: dict[str, str] = {
    "purpose": "{concept} {is_are} responsible for {clause}",
    "cause": "{concept} {is_are} caused by {clause}",
    "effect": "{concept} {result_s} in {clause}",
    "mechanism": "{concept} {work_s} by means of {clause}",
    "condition": "{concept} {depend_s} on {clause}",
    "category": "{concept} {divide_s} into {clause}",
}

#: Concept names that are grammatically plural and need plural agreement
#: ("Mitochondria are…", not "Mitochondria is…").
_PLURAL_CONCEPT = re.compile(
    r"(?:ia|ae)$|(?<![su])s$", re.IGNORECASE
)


def _agreement(concept_name: str) -> dict[str, str]:
    """Subject-verb agreement forms for a concept used as a sentence subject."""
    head = concept_name.strip().split()[-1] if concept_name.strip() else ""
    plural = bool(_PLURAL_CONCEPT.search(head)) and not head.lower().endswith("sis")
    return {
        "is_are": "are" if plural else "is",
        "result_s": "result" if plural else "results",
        "work_s": "work" if plural else "works",
        "depend_s": "depend" if plural else "depends",
        "divide_s": "divide" if plural else "divides",
        "do_es": "do" if plural else "does",
        "differ_s": "differ" if plural else "differs",
    }

#: Frames for clauses that are already full statements. The concept becomes an
#: adverbial ("In photosynthesis, plants convert …") so the assertion stays
#: grammatical instead of stacking two subjects.
_FACET_ASSERTION_FINITE: dict[str, str] = {
    "mechanism": "In {concept}, {clause}",
    "purpose": "In {concept}, {clause}",
    "effect": "As a result of {concept}, {clause}",
    "cause": "{concept} occurs because {clause}",
    "condition": "{concept} requires that {clause}",
}

#: Verbs that, appearing as the clause's main verb, make it a full statement
#: rather than a noun phrase. "ribosomes decode the sequence" is finite;
#: "the production of ribosomal RNA" is not.
_FINITE_VERB = re.compile(
    r"\b(?:is|are|was|were|has|have|does|do|decode[sd]?|produce[sd]?|generate[sd]?|"
    r"synthesi[sz]e[sd]?|convert[sd]?|break[s]?|carr(?:y|ies)|contain[s]?|"
    r"regulate[sd]?|control[s]?|separate[sd]?|move[sd]?|bind[s]?|read[s]?|"
    r"assemble[sd]?|package[sd]?|modif(?:y|ies)|sort[s]?|store[s]?|release[s]?)\b",
    re.IGNORECASE,
)

#: A trailing participial aside ("commonly remembered with the mnemonic PMAT")
#: makes a noun phrase read badly inside an assertion template.
_TRAILING_ASIDE = re.compile(r",\s*(?:commonly|often|usually|typically|generally)\b", re.IGNORECASE)

#: A clause lifted out of a conditional keeps the consequent's connective
#: ("…0/0, then lim x->a f(x)/g(x) = …"). Detached from its "if", the fragment
#: asserts something the document never claims, so it cannot become a statement.
_DANGLING_CONNECTIVE = re.compile(
    r"(?:^|,)\s*(?:then|otherwise|else|whereas|while|but|however)\b", re.IGNORECASE
)


def _is_finite_clause(clause: str) -> bool:
    """True when the clause is a full statement rather than a noun phrase.

    "ribosomes decode the sequence" is finite and needs a frame that accepts a
    sentence ("In translation, ribosomes decode …"); "a process called cellular
    respiration" is a noun phrase and slots after a verb instead.
    """
    if re.match(r"^\s*(?:a|an|the)\s+\w+\s+(?:called|named|known)\b", clause, re.IGNORECASE):
        return False
    # A noun phrase may legitimately contain "of the …"; only a main verb close
    # to the front makes the clause a statement. Detect it structurally — a
    # noun-ish subject followed by a third-person verb — rather than by listing
    # verbs, which cannot generalise across subjects.
    # A subjectless predicate is handled separately; it is not a full clause.
    # A relation frame ends in a preposition ("responsible for ...", "by means
    # of ..."), so its clause must read as a noun phrase. A bare infinitive or
    # past-tense verb produces "is responsible for bound the major powers" /
    # "works by means of maintain a strong military". The document stated
    # something real here, but not in a form this frame can carry, so the
    # statement is declined rather than emitted ungrammatically.
    if _opens_with_bare_verb(clause) and not _is_bare_predicate(clause):
        return None
    if _is_bare_predicate(clause):
        return False
    head = " ".join(clause.split()[:7])
    if _FINITE_VERB.search(head):
        return True
    if re.match(
        r"^\s*(?:the|a|an)?\s*[\w'’\-]+(?:\s+[\w'’\-]+){0,2}\s+"
        r"[a-z]+(?:es|s)\s+(?:the|a|an|its|their|his|her|each|every|all|some|"
        r"which|what|that)\b",
        clause,
        re.IGNORECASE,
    ):
        return True
    # The patterns above only see present-tense "-s" verbs, so a past-tense
    # clause ("industrial powers COMPETED for colonies") looked like a noun
    # phrase and was pushed into a frame ending in a preposition, producing
    # "Imperialism is caused by industrial powers competed for colonies".
    # A subject followed by an "-ed" verb and its complement is just as finite.
    return bool(
        re.match(
            r"^\s*(?:the|a|an)?\s*[\w'’\-]+(?:\s+[\w'’\-]+){0,2}\s+"
            r"[a-z]{3,}ed\s+(?:the|a|an|its|their|his|her|each|every|all|some|"
            r"which|what|that|for|to|into|with|by|from|on|in|at|over|against)\b",
            clause,
            re.IGNORECASE,
        )
    )


#: A clause that opens with a third-person verb and no subject is a predicate
#: waiting for one: "opposes relative motion…", "regulates what enters…".
_BARE_PREDICATE = re.compile(
    r"^\s*(?:also\s+)?(?:[a-z]+(?:es|s))\s+(?!of\b|that\b|which\b|to\b|the\s+\w+\s+of\b)",
)


def _is_bare_predicate(clause: str) -> bool:
    """True when the clause is a subjectless predicate the concept can head."""
    if not _BARE_PREDICATE.match(clause):
        return False
    tokens = clause.split()
    # Guard against plural noun phrases ("processes such as diffusion"), which
    # also start with a word ending in -s but are not verbs.
    first = tokens[0].lower().strip(",")
    if first in _PLURAL_NOUN_STARTS:
        return False
    # "ribosomes decode the sequence" opens with a plural *subject* followed by
    # its verb, so it is a full clause, not a subjectless predicate.
    if len(tokens) > 1 and _FINITE_VERB.fullmatch(tokens[1].lower().strip(",")):
        return False
    return True


#: Plural nouns common at the head of a noun-phrase clause; these look like
#: third-person verbs but are not.
_PLURAL_NOUN_STARTS = frozenset(
    """processes phases stages steps structures organelles cells molecules
    enzymes proteins values numbers forces objects systems methods techniques
    algorithms rules laws principles types kinds categories classes groups
    states levels layers components elements factors properties""".split()
)


#: "X states that ..." introduces a self-contained proposition.
_STATES_THAT = re.compile(r"\bstates?\s+that\b|\basserts?\s+that\b|\bholds?\s+that\b", re.IGNORECASE)


def _states_a_proposition(evidence: str, concept: str, clause: str = "") -> bool:
    """True when the clause is a complete proposition the evidence quotes.

    "X states that ..." usually introduces a self-contained claim, but the
    clause handed here may have been captured by a *different* pattern from the
    same sentence. Newton's First Law "states that an object stays at rest ...
    unless acted upon by an unbalanced external force": the mechanism pattern
    extracts the bare noun phrase "an unbalanced external force", which is not
    a proposition and must not be asserted on its own.
    """
    if not _STATES_THAT.search(evidence):
        return False
    if not clause:
        return True
    # An equation is a complete proposition even though it contains no English
    # verb: "lim x->a [f+g] = lim f + lim g" asserts an identity. Without this
    # it is mistaken for a noun phrase and rendered as "The sum law works by
    # means of lim x->a ...", which is not English.
    if _EQUATION.search(clause):
        return True
    # Otherwise a proposition needs a subject and a verb; a noun phrase has
    # neither.
    return bool(_FINITE_VERB.search(clause)) or _is_finite_clause(clause)


def _is_unassertable(clause: str) -> bool:
    """True when no template can turn this clause into a clean assertion.

    A trailing participial aside ("…, commonly remembered with the mnemonic
    PMAT") reads as a fragment inside any frame, and a clause carrying a
    dangling connective ("…, then lim x->a …") asserts half a conditional. Such
    clauses simply do not become true/false questions.
    """
    if _TRAILING_ASIDE.search(clause) or _DANGLING_CONNECTIVE.search(clause):
        return True
    # A determiner-led fragment with no verb ("each process a fixed time
    # slice") is the object half of a predicate whose verb was cut away.
    if re.match(r"^\s*(?:each|every|all|both|some|any)\s+", clause, re.IGNORECASE):
        return not _FINITE_VERB.search(clause)
    return False


def _true_statement(blueprint: QuestionBlueprint) -> str | None:
    """A true statement asserting the *relation* the document states.

    Deliberately not a truncated copy of the source sentence: shortening a
    definition and asking "true or false?" tests nothing but reading. A
    relational assertion instead requires the learner to know that this
    concept really does have this purpose/effect/mechanism.
    """
    if not blueprint.facet_kind or not blueprint.answer_clause:
        return None
    # A true/false statement is kept short so it stays readable. But some
    # claims cannot be shortened without becoming false — "the net force ... is
    # equal to the mass ... multiplied by its acceleration" says something
    # different the moment it is cut. Rather than lose the concept entirely,
    # allow the full statement when a safe short form does not exist.
    clause = _shorten(blueprint.answer_clause, 16) or _shorten(
        blueprint.answer_clause, _MAX_STATEMENT_WORDS
    )
    if not clause or len(content_tokens(clause)) < 2:
        return None
    # The clause must slot grammatically into the frame. A finite clause
    # ("ribosomes decode the sequence…") cannot follow "works by means of", so
    # it takes a sentence frame instead; a clause no frame fits is dropped.
    if _is_unassertable(clause):
        return None
    if _states_a_proposition(blueprint.evidence, blueprint.concept, clause):
        # "Newton's Second Law states that the net force ... equals ma" is
        # already a complete claim. Wrapping it in "works by means of" produces
        # "Newton's Second Law works by means of the net force acting on an
        # object is equal to ...", so assert the proposition on its own.
        statement = clause[0].upper() + clause[1:]
        return statement if statement.endswith(".") else statement + "."
    if _is_bare_predicate(clause):
        # "opposes relative motion between surfaces" is a predicate missing its
        # subject: the concept supplies it directly ("Friction opposes …")
        # rather than going through a relation frame, which would otherwise
        # yield "Friction is responsible for opposes relative motion".
        template = "{concept} {clause}"
    elif _is_finite_clause(clause):
        template = _FACET_ASSERTION_FINITE.get(blueprint.facet_kind)
    else:
        template = _FACET_ASSERTION.get(blueprint.facet_kind)
    if template is None:
        return None
    concept = _display(blueprint.concept, blueprint.evidence)
    statement = template.format(
        concept=concept, clause=clause, **_agreement(blueprint.concept)
    )
    statement = statement[0].upper() + statement[1:]
    if normalize_question_text(statement) == normalize_question_text(blueprint.evidence):
        return None
    return statement.rstrip(".") + "."


#: An infinitive or past-tense verb at the head of a clause. Such a clause is
#: not a noun phrase and cannot follow a preposition.
_BARE_VERB_HEAD = re.compile(
    r"^(?:to\s+)?(?P<word>[a-z]{3,})\b", re.IGNORECASE
)

#: Common irregular past forms that carry no -ed marker.
_IRREGULAR_PAST = frozenset(
    """bound built brought bought caught chose came did drew drove fell felt
    found gave went grew had heard held kept knew led left lent lost made met
    paid put ran said saw sold sent set showed shut sat spoke spent stood took
    taught told thought understood wore won wrote became began broke""".split()
)


def _opens_with_bare_verb(clause: str) -> bool:
    """True when a clause begins with an infinitive or past-tense verb."""
    match = _BARE_VERB_HEAD.match(clause.strip())
    if not match:
        return False
    word = match.group("word").lower()
    if clause.strip().lower().startswith("to "):
        return True
    if word in _IRREGULAR_PAST:
        return True
    # "maintain a strong military" -- a bare stem followed by its object.
    if word.endswith(("ed", "ing", "s")):
        return False
    remainder = clause.strip()[match.end() :].strip()
    return bool(
        remainder
        and re.match(r"^(?:a|an|the|its|their|his|her|this|these)\b", remainder, re.I)
    )


def _false_statement(
    blueprint: QuestionBlueprint, understanding: DocumentUnderstanding
) -> tuple[str, str, str] | None:
    """A false statement made by swapping in a different taught concept.

    Returns ``(statement, basis_evidence, decoy_name)``. The decoy is returned
    so the explanation can name who the claim was wrongly credited to.
    """
    base = _true_statement(blueprint)
    if not base:
        return None
    concept = understanding.concept(blueprint.concept_id)
    if concept is None:
        return None
    # The decoy must be a concept the learner is actually expected to know.
    # Crediting a claim to a term the document never taught ("the speed states
    # that...") tests nothing: the statement is false for the wrong reason, and
    # a student who spots it has learned no distinction.
    taught = understanding.important_concepts()
    # The decoy must also be the same *kind of thing*. A scheduling metric
    # cannot host a mechanism ("In Response time, the operating system decides
    # ..."), so swapping one in yields a sentence that is ungrammatical rather
    # than merely false — the student rejects it on grammar, not on knowledge.
    # Matching the event/principle/agent classification keeps the decoy
    # plausible, and it is derived from the text, so it stays subject-neutral.
    def _shape(name: str, evidence: str) -> str:
        if _is_principle_concept(name, evidence):
            return "principle"
        if _is_event_concept(name, evidence):
            return "event"
        return "agent"

    own_shape = _shape(concept.name, blueprint.evidence)

    def _compatible(other) -> bool:
        if (
            other.concept_id == concept.concept_id
            or len(content_tokens(other.name)) > 3
            or (content_tokens(other.name) & content_tokens(blueprint.evidence))
        ):
            return False
        # knowledge_type is NOT required to match. It is an inferred label whose
        # value often differs between two concepts of the same kind ("sum law"
        # is a principle, "power rule" a cause_effect), and demanding equality
        # left several documents with no eligible decoy at all — so every
        # true/false answer came out "True", which a student can game without
        # reading the question. Grammatical plausibility is what actually
        # matters, and the shape test below enforces it.
        # Prefer a same-shape decoy, but only *require* it for the frames where
        # a mismatch reads as broken grammar rather than a false claim.
        if own_shape == _shape(other.name, other.primary_evidence):
            return True
        return blueprint.facet_kind not in {"mechanism", "cause"}

    eligible = [other for other in taught if _compatible(other)]
    if not eligible:
        return None
    # Rotate the partner by concept id so a quiz does not credit every false
    # statement to the same concept, which would make the pattern obvious.
    key = f"{concept.concept_id}|{blueprint.knowledge_target_id}"
    index = sum(ord(char) for char in key) % len(eligible)
    partner = eligible[index]
    match = re.search(re.escape(concept.name), base, re.IGNORECASE)
    if not match:
        # The statement is a bare proposition ("lim x->a [f+g] = ..."), so there
        # is no concept mention to swap. Attributing it to another concept
        # explicitly still produces an honest false claim, provided the reader
        # can see which concept is being credited.
        if _states_a_proposition(blueprint.evidence, blueprint.concept):
            name = _display(partner.name, blueprint.evidence)
            name = name[0].upper() + name[1:]
            statement = f"{name} states that {base[0].lower()}{base[1:]}"
            return statement.rstrip(".") + ".", blueprint.evidence, name
        return None
    swapped = _display(partner.name, blueprint.evidence)
    # The statement frame may already carry an article before the concept
    # ("The plasma membrane works by ..."). _display adds one of its own when
    # the source uses it, which produced "The the endoplasmic reticulum". Drop
    # whichever article is redundant, keeping the frame's own capitalisation.
    head = base[: match.start()]
    article = re.search(r"(?:^|\s)(a|an|the)\s+$", head, re.IGNORECASE)
    if article:
        stripped = re.sub(r"^(?:a|an|the)\s+", "", swapped, flags=re.IGNORECASE)
        if stripped:
            swapped = stripped
    elif match.start() == 0:
        swapped = swapped[0].upper() + swapped[1:]
    tail = base[match.end() :]
    # The verb was inflected for the ORIGINAL subject. Swapping a singular name
    # into a plural frame leaves "Translation result in ..." / "The chain rule
    # are responsible ...", which a student rejects on grammar rather than on
    # knowledge — the question then tests nothing. Re-inflect for the decoy.
    own = _agreement(concept.name)
    new = _agreement(partner.name)
    for key, was in own.items():
        now = new[key]
        if was == now:
            continue
        tail = re.sub(rf"^(\s*){re.escape(was)}\b", rf"\g<1>{now}", tail, count=1)
    statement = base[: match.start()] + swapped + tail
    if normalize_question_text(statement) == normalize_question_text(base):
        return None
    return statement, blueprint.evidence, swapped


#: Words that are never worth blanking: blanking them tests reading, not recall.
_UNBLANKABLE = frozenset(
    """process cell cells thing things part parts system structure function type kind
    form stage step phase number amount level state group set way method material
    substance object result output value time place area point""".split()
)


def _fill_blank(blueprint: QuestionBlueprint) -> tuple[str, str] | None:
    """Blank one meaningful technical term inside a relational claim.

    Deliberately *not* "blank the subject of its own definition": that leaves
    the entire definition on screen and reduces the task to copying a sentence,
    which is one of the failure modes this pipeline exists to remove.

    Instead the blank falls on a distinctive term inside the clause the
    document uses to explain the concept, so answering requires recalling that
    term rather than reading it off the prompt.
    """
    clause = re.sub(r"\s+", " ", blueprint.answer_clause or "").strip()
    if not clause or len(content_tokens(clause)) < 3:
        return None

    concept_tokens = content_tokens(blueprint.concept)
    # Prefer a multi-word technical term, else a distinctive single word.
    candidates: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9'’\-]*(?:\s+[A-Z][A-Za-z0-9'’\-]+)*\b", clause):
        term = match.group(0).strip()
        if 2 < len(term) <= 40:
            candidates.append(term)
    for match in re.finditer(r"\b[a-z][a-z\-]{5,}\b", clause):
        candidates.append(match.group(0))

    for term in candidates:
        key = normalize_question_text(term)
        if not key or key in _UNBLANKABLE:
            continue
        # Never blank the concept's own name: that is the definitional
        # give-away shape again.
        if content_tokens(term) & concept_tokens:
            continue
        if len(content_tokens(term)) < 1:
            continue
        pattern = re.compile(rf"\b{re.escape(term)}\b")
        if len(pattern.findall(clause)) != 1:
            continue
        prompt_clause = pattern.sub("_____", clause, count=1)
        concept = _display(blueprint.concept, blueprint.evidence)
        prompt = f"Complete this statement about {concept}: {prompt_clause}."
        if len(re.findall(r"_{3,}", prompt)) != 1:
            continue
        if len(content_tokens(prompt)) < 4:
            continue
        return prompt, term
    return None


#: Question stems keyed by the *relational claim* being tested. Because the
#: facet guarantees the document states this relation, each stem has a real
#: source-grounded answer — unlike a generic "what is X?" template.
#:
#: Three phrasings per relation: an *agent* form for things that act (organelles,
#: components, structures), an *event* form for things that happen (processes,
#: reactions), and a *principle* form for stated rules (laws, theorems, formulas).
#: Using the wrong one produces sentences like "What is the direct result of
#: Mitochondria?" or "How does Newton's First Law carry out its function?".
#: Stems stay subject-neutral: the writer serves every document, so nothing here
#: may assume biology or any other field.
_FACET_STEMS_AGENT: dict[str, str] = {
    "purpose": "Why {is_are} {concept} important?",
    "cause": "What causes {concept} to form or act?",
    "effect": "What does {concept} produce?",
    "mechanism": "How does {concept} carry out its function?",
    "category": "Into which categories does {concept} divide?",
    "condition": "What does {concept} depend on?",
}

_FACET_STEMS_EVENT: dict[str, str] = {
    "purpose": "Why does {concept} matter?",
    "cause": "What causes {concept}?",
    "effect": "What is the direct result of {concept}?",
    "mechanism": "By what mechanism does {concept} occur?",
    "category": "Into which categories does {concept} divide?",
    "condition": "What does {concept} depend on?",
}

#: A *principle* is a law, rule, theorem, or definition: it does not act and it
#: does not occur, so it needs its own stems.
_FACET_STEMS_PRINCIPLE: dict[str, str] = {
    "purpose": "Why does {concept} matter?",
    "cause": "Under what circumstances does {concept} apply?",
    "effect": "What does {concept} predict?",
    "mechanism": "What does {concept} state?",
    "category": "Into which cases does {concept} divide?",
    "condition": "What condition must hold for {concept} to apply?",
}

#: Names that denote a stated rule rather than an actor or an occurrence.
_PRINCIPLE_LIKE = re.compile(
    r"\b(?:law|rule|theorem|principle|postulate|axiom|identity|equation|formula|"
    r"lemma|corollary|hypothesis|conjecture)\b",
    re.IGNORECASE,
)


def _is_principle_concept(name: str, evidence: str) -> bool:
    """True when the concept is a stated rule rather than a thing or an event."""
    if _PRINCIPLE_LIKE.search(name):
        return True
    # The concept must be the thing doing the stating, and its mention must not
    # be a fragment of a longer name: "The first derivative test states that
    # ..." is about the test, not about the derivative.
    escaped = re.escape(name.strip())
    match = re.search(
        rf"\b{escaped}\b(?![\w\-]|\s+(?:test|rule|law|theorem|method))"
        rf"\s*(?:,[^.;]{{0,40}},)?\s*\bstates\s+that\b",
        evidence,
        re.IGNORECASE,
    )
    return bool(match)


#: Suffixes and words that mark a concept as a process/event rather than a
#: thing that acts.
#: Purely morphological: a nominalisation suffix marks a process/event in any
#: subject ("translation", "erosion", "hydrolysis", "recursion", "colonialism").
#: A named-concept alternation was removed from here — "mitosis"/"meiosis" are
#: already covered by the "sis" suffix, so the list added nothing except a
#: biology dependency in a domain-neutral rule.
_EVENT_LIKE = re.compile(r"(?:tion|sion|ing|sis|ysis|ism)$", re.IGNORECASE)


def _is_event_concept(name: str, evidence: str) -> bool:
    """True when the concept is a process/event rather than an agent."""
    head = name.strip().split()[-1] if name.strip() else ""
    if _EVENT_LIKE.search(head):
        return True
    return bool(
        re.search(
            rf"\b{re.escape(name)}\b\s+(?:is|are)\s+(?:defined\s+as\s+)?(?:the\s+|a\s+|an\s+)?"
            r"(?:process|procedure|reaction|stage|phase|cycle|mechanism|method)\b",
            evidence,
            re.IGNORECASE,
        )
    )


def _stem(blueprint: QuestionBlueprint, partner_name: str, *, mcq: bool) -> str | None:
    """The question sentence, driven by the relational claim being tested."""
    concept = _display(blueprint.concept, blueprint.evidence)
    skill = blueprint.cognitive_skill

    # A facet-backed target asks about the relation the document states.
    if blueprint.facet_kind:
        if blueprint.facet_kind == "contrast" and partner_name:
            # The other side of a comparison must be a *name*, not a clause.
            # "How does friction differ from kinetic friction acts on objects
            # that are sliding?" is unreadable, so a clause-shaped partner
            # disqualifies the question rather than being asked badly.
            other = partner_name.strip()
            if len(other.split()) > 5 or _FINITE_VERB.search(other):
                return None
            # _FINITE_VERB is an inventory and misses verbs it has not seen
            # ("deposition adds it", "preserving the character's own idiom"),
            # which produced "How does Erosion differ from the deposition adds
            # it?". A concept name is a noun phrase, so reject a multi-word
            # partner carrying a verb or a participle. Morphological, so it
            # holds for any subject.
            if not _is_noun_phrase(other):
                return None
            # Whether the partner takes an article is a property of the term as
            # the *document* uses it, not of its capitalisation: the source
            # writes "the limit" but plain "Meiosis". _display reads that from
            # the evidence, so "differs from limit" becomes "differs from the
            # limit" while "differs from the meiosis" never appears.
            other = _display(other, blueprint.evidence)
            agree = _agreement(blueprint.concept)
            return (
                f"How {agree['do_es']} {concept} differ from {other}?"
                if mcq
                else f"Explain how {concept} {agree['differ_s']} from {other}."
            )
        if _is_principle_concept(blueprint.concept, blueprint.evidence):
            stems = _FACET_STEMS_PRINCIPLE
        elif _is_event_concept(blueprint.concept, blueprint.evidence):
            stems = _FACET_STEMS_EVENT
        else:
            stems = _FACET_STEMS_AGENT
        # A contrast facet whose partner could not be identified has no stem:
        # "How does X differ from what it is contrasted with?" is unanswerable,
        # so the target is dropped rather than asked badly.
        template = stems.get(blueprint.facet_kind)
        if template:
            return template.format(concept=concept, **_agreement(blueprint.concept))
        if blueprint.facet_kind == "contrast":
            return None

    if skill == "comparison":
        if not partner_name:
            # Nothing concrete to compare against; no honest question exists.
            return None
        other = _display(partner_name, blueprint.evidence)
        agree = _agreement(blueprint.concept)
        return (
            f"How {agree['do_es']} {concept} differ from {other}?"
            if mcq
            else f"Explain how {concept} {agree['differ_s']} from {other}."
        )
    if skill == "classification":
        return f"Into which categories is {concept} divided?"
    if skill == "misconception":
        return f"Which statement about {concept} is correct?" if mcq else None
    if skill == "factual_recall":
        # "Which statement correctly completes the meaning of X?" is a wording
        # game: it asks the reader to match a sentence fragment rather than to
        # know anything. Ask for the definition the document actually gives.
        return f"Which statement correctly defines {concept}?" if mcq else None
    # The understanding stem is answered by the document's own definition, so
    # it must ask for a description rather than an action: "what does X do?"
    # answered by "the smallest unit of all living organisms" is a mismatch.
    # Agreement follows the concept's number ("are ribosomes", "is the cell").
    # A question must stand on its own: referring to "the document" or "the
    # source" is both poor exam style and rejected by the prompt gate.
    agreement = _agreement(blueprint.concept)
    return (
        f"Which statement best describes {concept}?"
        if mcq
        else f"What {agreement['is_are']} {concept}?"
    )


#: A participle cannot head a concept name ("preserving the character's idiom").
_PARTICIPLE = re.compile(r"^\w+(?:ing|ed)$", re.IGNORECASE)


def _is_noun_phrase(text: str) -> bool:
    """True when a candidate partner reads as a name rather than a clause."""
    words = text.split()
    if not words:
        return False
    if len(words) == 1:
        return True
    # A leading -ed/-ing participle usually signals a reduced clause
    # ("preserving the character's own idiom"). But it is also how English
    # forms attributive adjectives ("Related rates problems", "Increasing the
    # pressure"), so it only disqualifies the phrase when no plain noun head
    # follows it -- position again, not shape.
    if _PARTICIPLE.match(words[0]) and not any(
        re.sub(r"[^\w]", "", w).isalpha()
        and not _PARTICIPLE.match(w)
        and not re.sub(r"[^\w]", "", w).lower() in _OBJECT_PRONOUNS
        for w in words[1:]
    ):
        return False
    # A non-initial token that inflects like a verb *may* be a predicate -- but
    # "-s" is also how English forms plurals, so shape alone cannot decide:
    # that reading rejected "covalent bonds" and silently destroyed a valid
    # comparison target. Use position instead. A predicate is followed by its
    # complement; a plural head noun ends the phrase or is followed by more
    # name. The suffix list stays only as a cheap pre-filter for tokens that
    # cannot be verbs at all.
    for index, word in enumerate(words[1:], start=1):
        bare = re.sub(r"[^\w]", "", word)
        if len(bare) < 4 or not bare.isascii() or not bare.islower():
            continue
        if bare.endswith("ed"):
            return False
        if bare.endswith("s") and not re.search(
            r"(?:ss|us|is|ics|ness|ies|sis|ses|nces|ments|tions|sions|ions)$", bare
        ):
            following = words[index + 1 :]
            # Nothing follows => the token is the phrase's head noun
            # ("covalent bonds", "related rates").
            if not following:
                continue
            nxt = re.sub(r"[^\w]", "", following[0]).lower()
            # A complement or an object pronoun after it means it governed one,
            # i.e. it is a verb ("deposition ADDS it", "erosion TRANSPORTS the
            # material").
            if _COMPLEMENT_AFTER_VERB.match(nxt) or nxt in _OBJECT_PRONOUNS:
                return False
            # A negated or stranded verb ends the clause: "most covalent
            # compounds DO NOT", "a symbol CAN carry".
            if nxt in _CLAUSE_TAIL_MARKERS:
                return False
    # A name does not end on a verb-phrase tail word. "most covalent compounds
    # DO NOT" and "preserving the character's own IDIOM" differ exactly here:
    # the first trails an auxiliary/negator, which can only close a clause.
    last = re.sub(r"[^\w]", "", words[-1]).lower()
    if last in _CLAUSE_TAIL_MARKERS or last in _AUXILIARIES:
        return False
    return True


#: Auxiliaries and copulas. A noun phrase never ends on one.
_AUXILIARIES = frozenset({"is", "are", "was", "were", "be", "been", "being", "do",
                          "does", "did", "has", "have", "had", "can", "could",
                          "will", "would", "may", "might", "must", "should"})


#: Pronouns that can only be a verb's object, never part of a name.
_OBJECT_PRONOUNS = frozenset({"it", "them", "him", "her", "us", "me", "you", "itself",
                              "themselves"})

#: Words that mark the tail of a verb phrase rather than the head of a name.
_CLAUSE_TAIL_MARKERS = frozenset({"not", "never", "also", "only", "already", "still",
                                  "always", "often", "usually", "then", "so"})

#: What a verb's complement starts with. A plural noun is not followed by one.
_COMPLEMENT_AFTER_VERB = re.compile(
    r"^(?:the|a|an|to|into|onto|with|by|for|in|on|at|as|from|than|that|this|"
    r"these|those|its|their|his|her|our|your)$",
    re.IGNORECASE,
)


def _partner_name(
    blueprint: QuestionBlueprint, understanding: DocumentUnderstanding
) -> str:
    # A contrast facet already carries the other side of the comparison in its
    # answer clause ("the difference between turnaround time and waiting
    # time"), so prefer it over relationship lookup.
    if blueprint.facet_kind == "contrast" and blueprint.answer_clause.strip():
        clause = blueprint.answer_clause.strip()
        # The clause is a normalised, lower-cased copy of the term. When it
        # names a concept the study map already knows, use that concept's own
        # name: only the original casing distinguishes a proper name that takes
        # no article ("Meiosis") from a common noun that needs one ("limit"),
        # and lower-casing has erased it.
        for concept in understanding.concepts:
            if concept.name.casefold() == clause.casefold():
                return concept.name
        return clause
    for supporting in blueprint.supporting_ids:
        concept = understanding.concept(supporting)
        if concept is not None:
            return concept.name
    for relationship in understanding.relationships:
        if relationship.kind != "contrast":
            continue
        if relationship.source_id == blueprint.concept_id:
            partner = understanding.concept(relationship.target_id)
            if partner:
                return partner.name
        if relationship.target_id == blueprint.concept_id:
            partner = understanding.concept(relationship.source_id)
            if partner:
                return partner.name
    return ""


def _draws_contrast(clause: str) -> bool:
    """True when a clause states a difference rather than a bare property."""
    return bool(
        clause
        and re.search(
            r"\bdiffers?\s+from\b|\bunlike\b|\bwhereas\b|\brather\s+than\b|"
            r"\bin\s+contrast\b|\bcompared\s+(?:to|with)\b",
            clause,
            re.IGNORECASE,
        )
    )


def _two_sided_claim(evidence: str, concept_name: str) -> str:
    """Both halves of a stated contrast, or "" when only one side is present.

    A comparison answer has to name the difference. Keeping just the first
    clause of "X bound A, while Y linked B" yields a membership list that
    answers no comparison question at all.
    """
    text = re.sub(r"\s+", " ", evidence or "").strip()
    if not text:
        return ""
    match = re.search(
        rf"\b{re.escape(concept_name)}\b", text, re.IGNORECASE
    ) or re.search(re.escape(concept_name), text, re.IGNORECASE)
    if not match:
        return ""
    tail = text[match.end() :].strip(" ,;:")
    contrast = _CONTRAST_TAIL.search(tail)
    if not contrast:
        return ""
    other = tail[contrast.end() :].strip(" ,;:.")
    # Both sides must carry real content for the answer to be a contrast.
    if len(tail[: contrast.start()].split()) < 2 or len(other.split()) < 2:
        return ""
    joined = f"{tail[: contrast.start()].strip(' ,;:.')}, whereas {other}"
    return joined.rstrip(".")


def _candidate_for(
    blueprint: QuestionBlueprint,
    *,
    understanding: DocumentUnderstanding,
    pool: list[tuple[str, str, str]],
) -> dict[str, Any] | None:
    if blueprint.cognitive_skill not in SUPPORTED_SKILLS:
        # Application/transfer questions need a scenario the source does not
        # state. Inventing one would be exactly the failure mode this rewrite
        # exists to remove, so nothing is written.
        return None

    partner_name = _partner_name(blueprint, understanding)
    # A concise answer is preferred, but some definitions are a single
    # unbreakable clause a little over the concise budget ("the value that a
    # function f(x) approaches as the input x approaches some particular
    # value, without necessarily ever reaching it"). There is no internal
    # boundary to cut at, so insisting on the short form returns nothing and
    # the concept disappears from the exam without ever being rejected. Fall
    # back to the full statement: longer, but complete, true and answerable.
    answer = _claim(blueprint.evidence, blueprint.concept)
    if not answer and _is_sole_opportunity(blueprint, understanding):
        answer = _claim(
            blueprint.evidence, blueprint.concept, max_words=_MAX_STATEMENT_WORDS
        )
    base: dict[str, Any] = {
        "id": f"det-{blueprint.id}",
        "blueprint_id": blueprint.id,
        "type": blueprint.question_type,
        "difficulty": blueprint.difficulty,
        "source_pages": list(blueprint.pages),
        "source_quote": blueprint.evidence,
    }

    if blueprint.question_type == "fill-blank":
        built = _fill_blank(blueprint)
        if built is None:
            return None
        prompt, term = built
        return {
            **base,
            "prompt": prompt,
            "correct_answer": term,
            "explanation": _explanation(blueprint, term),
        }

    if blueprint.question_type == "true-false":
        if blueprint.cognitive_skill == "misconception":
            built = _false_statement(blueprint, understanding)
            if built is None:
                return None
            statement, basis, decoy = built
            return {
                **base,
                "prompt": statement,
                "options": ["True", "False"],
                "correct_answer": "False",
                "explanation": _misconception_explanation(blueprint, decoy),
                "false_statement_basis": basis,
            }
        statement = _true_statement(blueprint)
        if statement is None:
            return None
        return {
            **base,
            "prompt": statement,
            "options": ["True", "False"],
            "correct_answer": "True",
            "explanation": _explanation(blueprint, "this statement"),
        }

    if blueprint.facet_kind == "contrast":
        # For a contrast the answer clause holds the *other* concept's name,
        # not an answer. "How does waiting time differ from turnaround time?"
        # is answered by what this concept is defined as, so the distinction
        # can actually be stated. Without that definition there is nothing
        # substantive to compare and the target is dropped.
        #
        # When the evidence states BOTH sides ("The Triple Alliance bound
        # Germany ..., while the Triple Entente linked France ..."), _claim
        # stops at the contrast tail and returns one side only -- an answer
        # that lists members without distinguishing anything. Keep both sides
        # so the answer actually contrasts them.
        # Prefer the concise one-sided claim when it already draws the
        # distinction itself ("differs from covalent bonds in that ..."):
        # appending the mirror clause only lengthens it and hands MCQ options a
        # length giveaway. Fall back to both sides when the first clause alone
        # states no contrast ("bound Germany, Austria-Hungary, and Italy").
        answer = _shorten(_claim(blueprint.evidence, blueprint.concept))
        if not _draws_contrast(answer):
            both = _shorten(_two_sided_claim(blueprint.evidence, blueprint.concept))
            answer = both or answer
        if not answer:
            own = understanding.concept(blueprint.concept_id)
            if own is not None:
                answer = _shorten(_claim(own.primary_evidence, own.name))
        if not answer:
            return None
    elif blueprint.facet_kind:
        # A reasoning question is answered by the relation the document
        # states, not by the concept's definition. The facet already isolated
        # that clause during understanding.
        # Same reasoning as the true/false path: prefer a concise answer, but
        # accept the full claim rather than drop an important concept when no
        # shorter form can be stated without changing its meaning.
        answer = (
            _shorten(blueprint.answer_clause)
            or _shorten(_effect_clause(blueprint.evidence))
            or _shorten(blueprint.answer_clause, _MAX_STATEMENT_WORDS)
            # Last resort: the whole predicate the evidence states. Long, but
            # true and complete — preferable to omitting a central concept.
            or _claim(blueprint.evidence, blueprint.concept, max_words=_MAX_STATEMENT_WORDS)
        )
        if not answer:
            return None
    elif blueprint.cognitive_skill == "cause_effect":
        effect = _effect_clause(blueprint.evidence)
        if not effect:
            return None
        answer = effect

    if not answer:
        return None

    stem = _stem(blueprint, partner_name, mcq=blueprint.question_type == "mcq")
    if stem is None:
        return None

    if blueprint.question_type == "short-answer":
        return {
            **base,
            "prompt": stem,
            "correct_answer": answer,
            "explanation": _explanation(blueprint, answer),
        }

    if blueprint.question_type == "mcq":
        distractors = _distractors(blueprint, answer, pool)
        if len(distractors) < 3:
            return None
        return {
            **base,
            "prompt": stem,
            "options": [answer, *distractors],
            "correct_answer": answer,
            "explanation": _explanation(blueprint, answer),
            "distractor_rationales": [
                f"This states what a different concept in the chapter does: {value}."
                for value in distractors
            ],
        }

    return None


def target_writable_types(target: Any, allowed_types: list[str]) -> list[str]:
    """Which of ``allowed_types`` this writer can actually deliver for a target.

    The planner uses this so it never commits a slot to a question the writer
    will silently drop. Without it, a target whose clause resists (say)
    true/false consumes a slot and the quiz comes back short.
    """
    facet_kind = getattr(target, "facet_kind", "")
    clause = re.sub(r"\s+", " ", getattr(target, "answer_clause", "") or "").strip()
    writable: list[str] = []
    for question_type in allowed_types:
        if question_type == "true-false":
            # Mirrors _true_statement's requirements.
            if not facet_kind or not clause:
                continue
            shortened = _shorten(clause, 16)
            if not shortened or len(content_tokens(shortened)) < 2:
                continue
            if _is_unassertable(shortened):
                continue
            # Mirror _true_statement's rejection of a clause that cannot follow
            # the frame's preposition. Without this the planner commits a slot
            # the writer then declines, and the quiz comes back short.
            if _opens_with_bare_verb(shortened) and not _is_bare_predicate(shortened):
                continue
            table = (
                _FACET_ASSERTION_FINITE if _is_finite_clause(shortened) else _FACET_ASSERTION
            )
            if facet_kind not in table:
                continue
        elif question_type == "mcq":
            # An MCQ needs three distractors of comparable length. A very long
            # correct answer — a formula or a full statement of a law — has no
            # length-matched peers, so the options become obviously unbalanced
            # and the distractor gate rejects the question downstream. Vetoing
            # the type here lets the planner spend the slot on a form this
            # target can actually support instead of losing the concept.
            answer = getattr(target, "answer_clause", "") or ""
            if len(answer.split()) > _MAX_CLAIM_WORDS:
                continue
            # A formula answer cannot be hidden among prose distractors. The
            # pool holds one claim per concept, and few of them are notation,
            # so an equation sits beside three sentences and the answer is
            # visible without reading any of them. The document taught this as
            # a rule, so ask it in a form that does not need decoys.
            if _EQUATION.search(answer):
                continue
        elif question_type == "fill-blank":
            # Mirrors _fill_blank's requirements.
            if not clause or len(content_tokens(clause)) < 3:
                continue
        writable.append(question_type)
    return writable


def writable_question_types(
    question_types: list[str], understanding: DocumentUnderstanding
) -> list[str]:
    """Restrict planning to the types this writer can actually produce.

    A multiple-choice question needs three plausible same-domain distractors,
    which means the document must teach at least four distinct concepts. Asking
    the planner for MCQs a document cannot support would only produce blueprints
    that the writer must silently drop.
    """
    allowed = list(question_types)
    if len(_claim_pool(understanding)) < 4 and "mcq" in allowed and len(allowed) > 1:
        allowed = [value for value in allowed if value != "mcq"]
    # True/false asserts a *relation* the document states, and fill-blank
    # blanks a term inside that relation's clause, so both need an extracted
    # facet. A document of bare definitions has none, and planning these types
    # for it would only yield blueprints the writer silently drops.
    has_facets = any(concept.facets for concept in understanding.concepts)
    if not has_facets:
        relational = {"true-false", "fill-blank"}
        remaining = [value for value in allowed if value not in relational]
        if remaining:
            allowed = remaining
    return allowed


def deterministic_candidates(
    blueprints: list[QuestionBlueprint],
    *,
    language: str,
    understanding: DocumentUnderstanding,
) -> list[dict[str, Any]]:
    """Write one candidate per blueprint using only the study map.

    English-only by design: writing natural Arabic prose without a provider
    would produce awkward questions, so an Arabic quiz reports the unavailable
    state rather than shipping poor language.
    """
    if language != "en":
        return []
    pool = _claim_pool(understanding)
    candidates: list[dict[str, Any]] = []
    for blueprint in blueprints:
        candidate = _candidate_for(blueprint, understanding=understanding, pool=pool)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
