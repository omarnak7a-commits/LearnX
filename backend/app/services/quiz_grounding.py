"""Evidence grounding primitives shared by the quiz understanding pipeline.

Nothing in this module knows about questions.  It answers three narrow
questions that every later stage depends on:

1. *Is this text actually present in the source?*  (``quote_is_grounded``)
2. *Are these two evidence spans the same span?*  (``quotes_equivalent``)
3. *Is this fragment real teaching prose, or is it page furniture, a heading,
   or layout trivia?*  (``is_heading_like``, ``is_layout_detail``)

Keeping them provider-free and side-effect-free means the semantic layers
above can never "believe" an LLM about what the document contains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING

from app.services.quiz_scoring import content_token_list, content_tokens

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.services.quiz_concepts import SourceUnit


# --------------------------------------------------------------------------- #
# Sentence-level view of the cleaned source
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceSentence:
    """One sentence of cleaned source text with its page and section."""

    text: str
    page: int
    order: int
    section: str = ""

    @property
    def tokens(self) -> set[str]:
        return content_tokens(self.text)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+")


def iter_sentences(units: Iterable["SourceUnit"]) -> list[SourceSentence]:
    """Split cleaned page units into page-attributed, section-aware sentences.

    PDF extraction hard-wraps sentences across physical lines, so continuation
    lines are re-joined.  Heading lines are *not* merged into the paragraph
    that follows them: gluing "3.2 The Nucleus and Genetic Material" onto the
    next sentence would smuggle a title into the evidence a question is later
    built from.  Instead the heading becomes the section label for the
    sentences beneath it.
    """
    sentences: list[SourceSentence] = []
    order = 0
    # A sentence interrupted by a page break: the page ends mid-clause and the
    # next page continues it. Flushing per page cut such sentences in half
    # ("Centripetal force is defined as the net force required to keep an
    # object moving in a circular path, and it"), leaving evidence that states
    # something the document never said and losing the rest of the claim.
    # The unfinished tail is carried forward and joined to the next page.
    carry: list[str] = []
    carry_page = 0

    for unit in units:
        section = ""
        buffer: list[str] = []
        if carry:
            buffer.extend(carry)
            carry = []

        def flush(section_name: str, *, last: bool = False) -> None:
            nonlocal order, buffer, carry, carry_page
            if not buffer:
                return
            joined = re.sub(r"\s+", " ", " ".join(buffer)).strip()
            buffer = []
            parts = _SENTENCE_SPLIT.split(joined)
            # Only the final fragment of the final flush on a page can run over
            # onto the next one, and only when it does not already end in
            # terminal punctuation.
            if last and parts and not re.search(r"[.!?:;]$", parts[-1].strip()):
                tail = parts.pop().strip()
                if tail:
                    carry = [tail]
                    carry_page = unit.page
            for raw in parts:
                text = strip_inline_heading(re.sub(r"\s+", " ", raw).strip())
                if len(text) < 3:
                    continue
                sentences.append(
                    SourceSentence(
                        text=text,
                        page=carry_page or unit.page,
                        order=order,
                        section=section_name,
                    )
                )
                order += 1
                carry_page = 0

        lines = unit.text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if is_heading_like(stripped):
                flush(section)
                section = stripped
                continue
            buffer.append(stripped)
        flush(section, last=True)

    # Anything still pending at the end of the document is a real sentence too.
    if carry:
        text = strip_inline_heading(re.sub(r"\s+", " ", " ".join(carry)).strip())
        if len(text) >= 3:
            sentences.append(
                SourceSentence(
                    text=text, page=carry_page or 1, order=order, section=""
                )
            )
    return sentences


def evidence_normalize(text: str) -> str:
    """Canonical word-stream form used for all evidence comparisons."""
    return " ".join(content_token_list(text))


def quote_is_grounded(
    quote: str,
    *,
    pages: list[int] | tuple[int, ...],
    page_text: dict[int, str],
    category: str | None = None,
) -> bool:
    """Require a proposed quote to occur contiguously on a claimed page."""
    quote_key = evidence_normalize(quote)
    minimum_tokens = 2 if category in {"principle_rule", "formula_rule"} else 4
    if len(quote_key) < 6 or len(quote_key.split()) < minimum_tokens:
        return False
    if any(quote_key in evidence_normalize(page_text.get(page, "")) for page in pages):
        return True
    # A sentence interrupted by a page break exists in full on neither page.
    # iter_sentences rejoins those halves, so the evidence is verbatim source
    # text that simply straddles the boundary. Concatenating the claimed page
    # with the one after it verifies the join without loosening the rule: the
    # quote must still appear contiguously in the document's own text.
    # The sentence may be attributed to either side of the break, so check the
    # join in both directions.
    for page in pages:
        for first, second in ((page, page + 1), (page - 1, page)):
            spanning = evidence_normalize(
                f"{page_text.get(first, '')} {page_text.get(second, '')}"
            )
            if spanning and quote_key in spanning:
                return True
    return False


def quotes_equivalent(left: str, right: str) -> bool:
    """True when two evidence spans are identical or one is an exact subspan."""
    a = evidence_normalize(left)
    b = evidence_normalize(right)
    if not a or not b:
        return False
    return a == b or (len(a.split()) >= 4 and a in b) or (len(b.split()) >= 4 and b in a)


# --------------------------------------------------------------------------- #
# Heading / layout detection
# --------------------------------------------------------------------------- #

_NUMBERED_HEADING = re.compile(r"^\s*\d{1,3}(?:\.\d{1,3})*\s*[-.–:)]?\s+\S")
_NAMED_HEADING = re.compile(
    r"^\s*(chapter|section|part|unit|module|lesson|topic|appendix|figure|table|"
    r"الفصل|القسم|الجزء|الوحدة|الدرس|الباب|الموضوع|شكل|جدول)\b",
    re.IGNORECASE,
)

# A very small predicate vocabulary is enough to separate "3.2 The Nucleus and
# Genetic Material" (a heading) from "The nucleus houses the genetic material."
# (a teaching sentence).  Headings do not assert anything.
_PREDICATE_WORDS = frozenset(
    """is are was were be been being has have had do does did can could may might must
    should would will shall uses use used using occurs occur occurred produces produce
    produced contains contain containing refers refer referred means mean meant states
    state stated requires require required causes cause caused leads lead led consists
    consist consisting includes include including defines define defined describes
    describe described generates generate generated equals equal becomes become forms
    form formed allows allow allowed regulates regulate regulated separates separate
    separated breaks break carries carry carried converts convert converted stores
    store stored provides provide provided results result resulting depends depend
    increases increase increased decreases decrease decreased happens happen happened
    proceeds proceed synthesizes synthesize synthesized reads read assembles assemble
    modifies modify modified packages package packaged houses house housed lacks lack
    lacked يعرف تعرف هو هي يتم يحدث ينتج تنتج يسبب تسبب يحتوي تحتوي يشير تشير يعني
    تعني يستخدم تستخدم يودي تودي يتكون تتكون""".split()
)


#: A word after one of these is a noun, so it cannot be the clause's verb.
_DETERMINERS_BEFORE_NOUN = frozenset(
    {"the", "a", "an", "this", "that", "these", "those", "its", "their", "his",
     "her", "our", "your", "some", "any", "all", "both", "each", "every", "no",
     "several", "many", "few", "more", "most", "other"}
)


def is_heading_like(text: str) -> bool:
    """True when a fragment is a title/heading rather than a teaching claim.

    Headings name a topic; they never teach it.  Questions built from a
    heading alone therefore have no answerable content, so headings are never
    accepted as concept evidence.
    """
    stripped = text.strip()
    if not stripped:
        return True
    words = stripped.split()
    if len(words) > 12:
        return False
    tokens = [re.sub(r"[^\w\u0600-\u06FF]", "", word).lower() for word in words]
    lowered = set(tokens)
    # A predicate word only proves this is a sentence when it is used AS a
    # predicate. In the title "World History: The Causes of the First World
    # War", "Causes" is a plural noun sitting under a determiner -- treating it
    # as a verb made the whole title look like a teaching claim, and the
    # document title then became a quiz concept.
    has_predicate = False
    for index, token in enumerate(tokens):
        if token not in _PREDICATE_WORDS:
            continue
        previous = tokens[index - 1] if index else ""
        if previous in _DETERMINERS_BEFORE_NOUN:
            continue
        has_predicate = True
        break
    if has_predicate:
        return False
    if _NUMBERED_HEADING.match(stripped) or _NAMED_HEADING.match(stripped):
        return True
    ends_open = not re.search(r"[.!?؟:;]$", stripped)
    if len(words) <= 9 and ends_open:
        return True
    return bool(re.fullmatch(r"[A-Z][A-Z0-9&'’\-\s]{3,60}", stripped))


_LAYOUT_DETAIL = re.compile(
    r"(?:\b(?:red|blue|green|yellow|orange|purple|black|white|grey|gray)\b.{0,80}"
    r"\b(?:box|font|ink|heading|caption|margin|layout|printed|highlighted|sidebar)\b|"
    r"\b(?:box|font|ink|heading|caption|margin|layout|printed|highlighted|sidebar)\b.{0,80}"
    r"\b(?:red|blue|green|yellow|orange|purple|black|white|grey|gray)\b|"
    r"\b(?:top|bottom|left|right)\s+(?:of\s+the\s+)?(?:page|margin|column)\b)",
    re.IGNORECASE,
)


def is_layout_detail(text: str) -> bool:
    """Catch page-design trivia even when a provider labels it as important."""
    return bool(_LAYOUT_DETAIL.search(text))


_GENERIC_LABELS = frozenset(
    {
        "introduction",
        "conclusion",
        "summary",
        "chapter summary",
        "overview",
        "review",
        "review question",
        "review questions",
        "chapter review",
        "exam tip",
        "key exam tip",
        "objectives",
        "learning objectives",
        "table of contents",
        "contents",
        "references",
        "bibliography",
        "appendix",
        "glossary",
        "index",
        "preface",
        "exercises",
        "key terms",
        "further reading",
        "مقدمه",
        "خلاصه",
        "ملخص",
        "مراجعه",
        "اهداف",
        "فهرس",
        "مراجع",
    }
)


_INLINE_HEADING_PREFIX = re.compile(
    r"^\s*\d{1,3}(?:\.\d{1,3})+\s+[^.?!]{3,80}?(?=\b[A-Z][a-z]+\s+(?:is|are|refers?|can|"
    r"consists?|contains?|occurs?|proceeds?|produces?|uses?)\b)"
)


def strip_inline_heading(text: str) -> str:
    """Remove a numbered heading fused onto the start of a sentence.

    Some PDF extractors emit ``"3.2 The Nucleus and Genetic Material The
    nucleus is defined as ..."`` as one run of text.  The heading part must
    not survive into evidence, because a question built from it would be a
    question about a title.
    """
    cleaned = _INLINE_HEADING_PREFIX.sub("", text, count=1).strip()
    return cleaned or text.strip()


def is_generic_label(name: str) -> bool:
    """True for document-scaffolding names that identify no subject content."""
    from app.services.quiz_scoring import normalize_question_text

    key = normalize_question_text(name)
    if not key or key in _GENERIC_LABELS:
        return True
    return not content_tokens(key)
