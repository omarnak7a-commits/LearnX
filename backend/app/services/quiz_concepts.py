"""Deterministic concept extraction and importance scoring for quiz generation.

This module is the "what is actually important here?" layer. It never calls
an LLM: it reads the extracted PDF text and, using transparent heuristics,
identifies the concepts that deserve to be tested and assigns each one an
explicit, explainable importance score. The LLM only ever sees the finished
concept map (see ``concept_map_block``), so it is steered toward high-value
content instead of being asked to guess what matters.

Heuristics (each backed by a test):
- Explicit definitions ("X is defined as ...", "X refers to ...", "X هو ...").
- Numbered / titled section headings (EN "3.1 Title" and AR "الفصل ...").
- Multi-word terms (runs of capitalized words).
- Repeated concepts (term-frequency of content words and bigrams).
- Processes, formulas, key relationships, cause/effect, comparisons, and
  explicit learning objectives.
- Metadata/trivial rejection (page numbers, ISBNs, headers/footers, word
  counts, formatting artifacts).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.services.quiz_scoring import (
    normalize_question_text,
    content_token_list,
    content_tokens,
)

_PAGE_MARKER = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)

# --------------------------------------------------------------------------- #
# Source splitting
# --------------------------------------------------------------------------- #


@dataclass
class SourceUnit:
    page: int
    text: str


def split_source_units(source_text: str) -> list[SourceUnit]:
    """Split ``source.text`` (which contains ``[Page N]`` markers) into units."""
    if not source_text:
        return []
    units: list[SourceUnit] = []
    positions = [(m.start(), int(m.group(1))) for m in _PAGE_MARKER.finditer(source_text)]
    if not positions:
        text = source_text.strip()
        if text:
            units.append(SourceUnit(page=1, text=text))
        return units
    for index, (start, page) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(source_text)
        text = source_text[start:end]
        text = _PAGE_MARKER.sub("", text, count=1).strip()
        if text:
            units.append(SourceUnit(page=page, text=text))
    return units


# --------------------------------------------------------------------------- #
# Concept model
# --------------------------------------------------------------------------- #


@dataclass
class Concept:
    name: str
    kind: str
    pages: list[int] = field(default_factory=list)
    evidence: str = ""
    frequency: int = 0
    depth: int = 0
    importance: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def key(self) -> str:
        return normalize_question_text(self.name)


# --------------------------------------------------------------------------- #
# Metadata / trivial rejection
# --------------------------------------------------------------------------- #

_GENERIC_PHRASES = {
    "table of contents", "all rights reserved", "copyright", "introduction",
    "conclusion", "summary", "references", "bibliography", "appendix",
    "glossary", "index", "preface", "acknowledgements", "figure", "chapter",
    "section", "unit", "lesson", "objective", "objectives", "word count",
    "printed", "published", "edition",
}

_METADATA_LINE = re.compile(
    r"^\s*(page\s*\d+|صفحة\s*\d+|\d{1,4})\s*$"
    r"|isbn[\s:]*[\d\-xX]+"
    r"|word count[\s:]*\d+"
    r"|عدد الكلمات[\s:]*\d+"
    r"|\bcopyright\b|all rights reserved"
    r"|http[s]?://\S+"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    re.IGNORECASE,
)


def is_metadata_line(line: str) -> bool:
    return bool(_METADATA_LINE.search(line))


def is_trivial_concept(name: str) -> bool:
    """True when a candidate concept is a page number, ISBN, or generic noise."""
    cleaned = normalize_question_text(name)
    if not cleaned:
        return True
    if re.fullmatch(r"\d{1,5}", cleaned):
        return True
    if re.search(r"^isbn[\s\d\-xX]+$", cleaned):
        return True
    if re.fullmatch(r"(page|صفحه)\s*\d+", cleaned):
        return True
    if cleaned in _GENERIC_PHRASES:
        return True
    if len(cleaned) < 3:
        return True
    # A concept that is only scaffolding/stopwords carries no content.
    if not content_tokens(cleaned):
        return True
    return False


# --------------------------------------------------------------------------- #
# Term frequency
# --------------------------------------------------------------------------- #


def _term_frequencies(units: list[SourceUnit]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for unit in units:
        counter.update(content_token_list(unit.text))
    return counter


def _bigram_frequencies(units: list[SourceUnit]) -> Counter[tuple[str, str]]:
    counter: Counter[tuple[str, str]] = Counter()
    for unit in units:
        tokens = content_token_list(unit.text)
        for pair in zip(tokens, tokens[1:]):
            if pair[0] != pair[1]:
                counter[pair] += 1
    return counter


# --------------------------------------------------------------------------- #
# Heading detection
# --------------------------------------------------------------------------- #

_NUMBERED_HEADING_LINE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,3}){1,3})[\s\-.–:]+(.{2,90})\s*$"
)
_NAMED_HEADING_LINE = re.compile(
    r"^\s*(chapter|section|part|lesson|unit|module|topic|الفصل|القسم|الجزء|الدرس|الوحدة|الباب|الموضوع)[\s\-.–:]+(.{2,90})\s*$",
    re.IGNORECASE,
)
_ALL_CAPS_HEADING_LINE = re.compile(r"^[A-Z][A-Z0-9&'’\-\s]{4,60}$")

# Inline numbered headings for PDFs whose text has no line breaks
# ("3.1 Introduction to Cell Structure" run directly into the next sentence).
_INLINE_NUMBERED_HEADING = re.compile(r"\d{1,3}(?:\.\d{1,3}){1,3}\s+([A-Z][A-Za-z&'’\-]+(?:\s+(?:and|of|to|in|for|the|a|an|or|and)\s+[A-Z][A-Za-z&'’\-]+){0,6})")


def extract_headings(units: list[SourceUnit]) -> list[Concept]:
    concepts: list[Concept] = []
    for unit in units:
        for line in unit.text.splitlines():
            line = line.strip()
            if not line or is_metadata_line(line):
                continue
            match = _NUMBERED_HEADING_LINE.match(line) or _NAMED_HEADING_LINE.match(line)
            if match:
                title = match.group(2).strip().rstrip(".:;")
                if not is_trivial_concept(title):
                    concepts.append(
                        Concept(
                            name=title,
                            kind="numbered_heading",
                            pages=[unit.page],
                            evidence=title,
                            depth=len(title),
                        )
                    )
                continue
            if _ALL_CAPS_HEADING_LINE.match(line) and len(line.split()) <= 10:
                title = line.title().strip()
                if not is_trivial_concept(title):
                    concepts.append(
                        Concept(name=title, kind="heading", pages=[unit.page], evidence=title, depth=len(title))
                    )
        for match in _INLINE_NUMBERED_HEADING.finditer(unit.text):
            title = match.group(1).strip()
            if not is_trivial_concept(title) and len(title.split()) >= 2:
                concepts.append(
                    Concept(name=title, kind="numbered_heading", pages=[unit.page], evidence=title, depth=len(title))
                )
    return concepts


# --------------------------------------------------------------------------- #
# Definition / formula / relationship / objective extraction
# --------------------------------------------------------------------------- #

_DEFINITION_PATTERNS = [
    re.compile(r"\b([A-Z][A-Za-z0-9&'’\- ]{2,60}?)\s+(?:is|are)\s+defined\s+as\s+([^.\n]{4,220})", re.IGNORECASE),
    re.compile(r"\b([A-Z][A-Za-z0-9&'’\- ]{2,60}?)\s+refers?\s+to\s+([^.\n]{4,220})", re.IGNORECASE),
    re.compile(r"\b([A-Z][A-Za-z0-9&'’\- ]{2,60}?)\s+is\s+(?:the|a|an)\s+([^.\n]{6,220})", re.IGNORECASE),
    re.compile(r"\b([A-Z][A-Za-z0-9&'’\- ]{2,60}?)\s+(?:means|is called|is known as|is termed)\s+([^.\n]{4,220})", re.IGNORECASE),
]

_AR_DEFINITION_PATTERNS = [
    re.compile(r"([\u0600-\u06FF][\u0600-\u06FF\s]{2,50}?)\s+(?:هو|هي)\s+([^.\n]{4,220})"),
    re.compile(r"(?:يُ?عر[ّف]?)\s+([\u0600-\u06FF][\u0600-\u06FF\s]{2,50}?)\s+بأن[ّ]?\s+([^.\n]{4,220})"),
    re.compile(r"([\u0600-\u06FF][\u0600-\u06FF\s]{2,50}?)\s+(?:تعني|يقصد بـ|يشير إلى)\s+([^.\n]{4,220})"),
]

_FORMULA_PATTERN = re.compile(r"\b([A-Za-z0-9_]+(?:\s*[-+*/^=]\s*[A-Za-z0-9_().]+)*\s*=\s*[^.;,]{2,60})")

_PROCESS_MARKERS = re.compile(
    r"\b(process|steps|stages|phases|mechanism|procedure|how it works|is converted|is produced|"
    r"first.{0,20}then|leads to|results in|produces|consists of|عمليه|خطوات|مراحل|اليه|كيفيه العمل|يتم انتاج|يتم تحويل)\b",
    re.IGNORECASE,
)

_RELATIONSHIP_MARKERS = re.compile(
    r"\b(causes|caused by|leads to|results in|because|therefore|due to|depends on|is determined by|"
    r"affects|increases|decreases|relationship between|يسبب|يودي الي|نتيجه|بسبب|لذلك|يعتمد علي|يتحدد بـ|ياثر|العلاقه بين)\b",
    re.IGNORECASE,
)

_COMPARISON_MARKERS = re.compile(
    r"\b(unlike|whereas|compared to|in contrast|similar to|differs from|more than|less than|"
    r"على عكس|بينما|مقارنه بـ|على النقيض|يشبه|يختلف عن|اكثر من|اقل من)\b",
    re.IGNORECASE,
)

_OBJECTIVE_MARKERS = re.compile(
    r"\b(learning objective|you will be able to|by the end of this|you will learn|after this (?:chapter|section|lesson)|"
    r"الهدف التعليمي|بعد هذا (?:الفصل|القسم|الدرس)|سوف تتعلم|في نهايه هذا)\b",
    re.IGNORECASE,
)


def extract_definitions(units: list[SourceUnit]) -> list[Concept]:
    concepts: list[Concept] = []
    for unit in units:
        for pattern in _DEFINITION_PATTERNS:
            for match in pattern.finditer(unit.text):
                term = re.sub(r"^(the|a|an)\s+", "", match.group(1), flags=re.IGNORECASE).strip()
                definition = match.group(2).strip()
                if 2 < len(term) < 70 and len(definition) > 8 and not is_trivial_concept(term):
                    concepts.append(
                        Concept(
                            name=term,
                            kind="definition",
                            pages=[unit.page],
                            evidence=f"{term} is defined as {definition}",
                            depth=len(definition),
                        )
                    )
        for pattern in _AR_DEFINITION_PATTERNS:
            for match in pattern.finditer(unit.text):
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if 2 < len(term) < 70 and len(definition) > 8 and not is_trivial_concept(term):
                    concepts.append(
                        Concept(
                            name=term,
                            kind="definition",
                            pages=[unit.page],
                            evidence=f"{term}: {definition}",
                            depth=len(definition),
                        )
                    )
    return concepts


def extract_formulas(units: list[SourceUnit]) -> list[Concept]:
    concepts: list[Concept] = []
    for unit in units:
        for match in _FORMULA_PATTERN.finditer(unit.text):
            formula = match.group(1).strip()
            if len(formula) < 70 and re.search(r"[0-9^*/+-]", formula):
                concepts.append(Concept(name=formula, kind="formula", pages=[unit.page], evidence=formula, depth=len(formula)))
    return concepts


def _sentences(unit: SourceUnit) -> list[str]:
    parts = re.split(r"(?<=[.!؟?])\s+", unit.text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def extract_relationships(units: list[SourceUnit]) -> list[Concept]:
    concepts: list[Concept] = []
    for unit in units:
        for sentence in _sentences(unit):
            if _PROCESS_MARKERS.search(sentence):
                concepts.append(_sentence_concept(sentence, "process", unit.page))
            elif _RELATIONSHIP_MARKERS.search(sentence):
                concepts.append(_sentence_concept(sentence, "relationship", unit.page))
            elif _COMPARISON_MARKERS.search(sentence):
                concepts.append(_sentence_concept(sentence, "comparison", unit.page))
            elif _OBJECTIVE_MARKERS.search(sentence):
                concepts.append(_sentence_concept(sentence, "objective", unit.page))
    return concepts


def _sentence_concept(sentence: str, kind: str, page: int) -> Concept:
    # Label the sentence with its most frequent content bigram (a meaningful,
    # content-anchored name rather than the raw sentence).
    tokens = content_token_list(sentence)
    bigrams = [" ".join(pair) for pair in zip(tokens, tokens[1:])]
    name = max(bigrams, key=bigrams.count) if bigrams else sentence[:80]
    name = name.title() if name.isascii() else name
    return Concept(name=name, kind=kind, pages=[page], evidence=sentence[:400], depth=len(sentence))


# --------------------------------------------------------------------------- #
# Repeated concepts and multi-word terms
# --------------------------------------------------------------------------- #

_MULTIWORD_TERM = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")


def extract_repeated_concepts(units: list[SourceUnit], bigrams: Counter[tuple[str, str]]) -> list[Concept]:
    concepts: list[Concept] = []
    for pair, count in bigrams.items():
        if count >= 2:
            name = " ".join(pair)
            if not is_trivial_concept(name) and len(name) > 3:
                pages = [u.page for u in units if normalize_question_text(name) in normalize_question_text(u.text)]
                concepts.append(
                    Concept(
                        name=name.title() if name.isascii() else name,
                        kind="repeated_term",
                        pages=pages or [units[0].page],
                        frequency=count,
                        evidence=name,
                        depth=count * len(name),
                    )
                )
    return concepts


def extract_multiword_terms(units: list[SourceUnit]) -> list[Concept]:
    concepts: list[Concept] = []
    for unit in units:
        for match in _MULTIWORD_TERM.finditer(unit.text):
            term = match.group(1).strip()
            if not is_trivial_concept(term):
                concepts.append(Concept(name=term, kind="multiword_term", pages=[unit.page], evidence=term, depth=len(term)))
    return concepts


# --------------------------------------------------------------------------- #
# Full extraction + importance scoring
# --------------------------------------------------------------------------- #


def extract_concepts(units: list[SourceUnit]) -> list[Concept]:
    """Run every detector and merge duplicate concepts into one concept map."""
    bigrams = _bigram_frequencies(units)
    raw: list[Concept] = []
    raw.extend(extract_headings(units))
    raw.extend(extract_definitions(units))
    raw.extend(extract_formulas(units))
    raw.extend(extract_relationships(units))
    raw.extend(extract_repeated_concepts(units, bigrams))
    raw.extend(extract_multiword_terms(units))

    merged: dict[str, Concept] = {}
    for concept in raw:
        key = concept.key()
        if key in merged:
            existing = merged[key]
            existing.pages = sorted(set(existing.pages + concept.pages))
            existing.frequency += concept.frequency
            existing.depth += concept.depth
            # Prefer the strongest evidence kind when merging.
            if _KIND_RANK[concept.kind] > _KIND_RANK[existing.kind]:
                existing.kind = concept.kind
                existing.evidence = concept.evidence
        else:
            merged[key] = concept
    return list(merged.values())


_KIND_RANK = {
    "definition": 5,
    "numbered_heading": 4,
    "objective": 4,
    "heading": 4,
    "formula": 3,
    "process": 3,
    "relationship": 2,
    "comparison": 2,
    "multiword_term": 2,
    "repeated_term": 1,
}


def score_importance(concepts: list[Concept]) -> list[Concept]:
    """Assign a transparent 0..1 importance score (and reasons) to each concept."""
    for concept in concepts:
        reasons: list[str] = []
        score = 0.0
        base = {
            "definition": 0.40,
            "numbered_heading": 0.35,
            "heading": 0.35,
            "objective": 0.30,
            "formula": 0.30,
            "process": 0.25,
            "relationship": 0.20,
            "comparison": 0.18,
            "multiword_term": 0.20,
            "repeated_term": 0.10,
        }.get(concept.kind, 0.10)
        if concept.kind != "repeated_term":
            score += base
            reasons.append(_KIND_LABEL[concept.kind])
        else:
            score += base

        if concept.frequency >= 2:
            bonus = min(0.20, concept.frequency * 0.05)
            score += bonus
            reasons.append(f"repeated {concept.frequency}x")

        spread = len(set(concept.pages))
        if spread > 1:
            bonus = min(0.10, (spread - 1) * 0.05)
            score += bonus
            reasons.append(f"spans {spread} pages")

        if concept.depth > 120:
            bonus = min(0.15, concept.depth / 4000)
            score += bonus
            reasons.append("explained in depth")

        concept.importance = round(min(1.0, score), 3)
        concept.reasons = reasons
    concepts.sort(key=lambda c: c.importance, reverse=True)
    return concepts


_KIND_LABEL = {
    "definition": "explicit definition",
    "numbered_heading": "numbered section heading",
    "heading": "section heading",
    "objective": "learning objective",
    "formula": "formula",
    "process": "process/mechanism",
    "relationship": "key relationship",
    "comparison": "comparison",
    "multiword_term": "multi-word term",
    "repeated_term": "repeated concept",
}


def build_concept_map(
    units: list[SourceUnit], *, min_concepts: int = 1, max_concepts: int = 12
) -> list[Concept]:
    """Extract + score concepts, guaranteeing at least one useful concept."""
    concepts = score_importance(extract_concepts(units))
    concepts = [c for c in concepts if c.importance >= 0.10]
    if not concepts and units:
        # Sparse source: fall back to a single "general comprehension" concept
        # anchored to the most frequent content terms.
        counter = _term_frequencies(units)
        top = [t for t, _ in counter.most_common(2)]
        name = " ".join(top).title() if top else units[0].text[:60]
        concepts = [
            Concept(
                name=name,
                kind="repeated_term",
                pages=[units[0].page],
                evidence=units[0].text[:400],
                importance=0.4,
                reasons=["general comprehension fallback"],
            )
        ]
    return concepts[:max_concepts]


def top_concepts(concepts: list[Concept], limit: int) -> list[Concept]:
    return sorted(concepts, key=lambda c: c.importance, reverse=True)[:limit]


def concept_map_block(concepts: list[Concept], limit: int = 12) -> str:
    """Render the concept map as a compact block for the LLM prompt."""
    lines: list[str] = []
    for index, concept in enumerate(top_concepts(concepts, limit), start=1):
        lines.append(
            f'{index}. importance={concept.importance:.2f} kind="{concept.kind}" '
            f'pages={concept.pages} — "{concept.name}"'
        )
        if concept.evidence:
            lines.append(f"   evidence: {concept.evidence[:260]}")
        if concept.reasons:
            lines.append(f"   why important: {', '.join(concept.reasons)}")
    return "\n".join(lines) if lines else "(no concepts detected)"
