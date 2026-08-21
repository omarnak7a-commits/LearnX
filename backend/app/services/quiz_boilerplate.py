"""Deterministic PDF-boilerplate detection and source cleaning for quiz generation.

Provider-free, human-readable heuristics used in two places:

1. **Source cleaning** — before concept extraction and prompt building, page
   text is stripped of boilerplate lines (copyright notices, legal/publisher
   text, ISBNs, DOIs, URLs, e-mail addresses, page folios, Arabic equivalents)
   and of repeated headers/footers that appear across multiple pages.

2. **Candidate rejection** — LLM-generated candidates whose prompt, answer,
   options, or explanation contain boilerplate are rejected before final
   selection, and the same detector zeroes their quality score as a second
   line of defence.

The LLM is *never* the only protection: every rule here runs deterministically
on every candidate and on every page of source text.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

from app.schemas.ai import AIQuizQuestion

if TYPE_CHECKING:  # pragma: no cover - only used for type hints
    from app.services.quiz_concepts import SourceUnit

# --------------------------------------------------------------------------- #
# Normalization (local copy so this module has no service dependencies and
# never participates in an import cycle).
# --------------------------------------------------------------------------- #


def _normalize(text: str) -> str:
    """Lower-case, canonicalize Arabic spelling, replace punctuation, collapse spaces."""
    text = text.lower()
    for src, dst in (
        ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
        ("ى", "ي"), ("ئ", "ي"), ("ؤ", "و"), ("ء", ""),
        ("ة", "ه"),
    ):
        text = text.replace(src, dst)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Raw-text patterns (symbols survive normalization, so they are checked on the
# original string).
# --------------------------------------------------------------------------- #

_SYMBOL_RE = re.compile(r"[©®™Ⓒⓒ]")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_ISBN_RE = re.compile(r"\bisbn[:\s]*[\d\-xX]{8,}\b", re.IGNORECASE)
_ISSN_RE = re.compile(r"\bissn[:\s]*\d{4}[- ]\d{3}[\dxX]\b", re.IGNORECASE)
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+\b")

# --------------------------------------------------------------------------- #
# Word-level patterns, matched against the normalized text (so Arabic patterns
# use canonicalized forms: ة -> ه, أ -> ا, ...).
# --------------------------------------------------------------------------- #

_WORD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("copyright", re.compile(r"\bcopyright\b")),
    ("all-rights-reserved", re.compile(r"all rights reserved")),
    ("trademark", re.compile(r"\btrademarks?\b|\bregistered marks?\b")),
    ("isbn", re.compile(r"\bisbn\b")),
    ("doi", re.compile(r"\bdoi\b|\bdigital object identifier\b")),
    ("issn", re.compile(r"\bissn\b")),
    ("publisher", re.compile(r"\bpublish(ed|er|ers|ing|es)?\b|\bpubli(shing|sher)\b")),
    ("licensing", re.compile(r"\blicen[cs]e(d|ing)?\b|\bpermission of\b")),
    (
        "legal",
        re.compile(
            r"\bterms of (use|service)\b|\bprivacy policy\b|\blegal notice\b|\bunauthorized\b|"
            r"\bproprietary\b|\bconfidential\b|\bdo not (copy|distribute|sell)\b|"
            r"\bmay not be (reproduced|copied|distributed)\b|\bno part of this\b"
        ),
    ),
    (
        "page-folio",
        re.compile(r"\bpages?\s*\d+(\s*-\s*\d+)?\b|\bpage\s*\d+\s+of\s+\d+\b"),
    ),
    (
        "arabic-legal",
        re.compile(
            r"حقوق النشر|حقوق الطبع|جميع الحقوق محفوظه|كل الحقوق محفوظه|الطبع والنشر|"
            r"دار النشر|الناشر|رقم الايداع|ترخيص|علامه تجاريه"
        ),
    ),
]


def boilerplate_hits(text: str) -> list[str]:
    """Return the boilerplate categories matched in ``text`` ([] when clean)."""
    hits: list[str] = []
    raw = text or ""
    if _SYMBOL_RE.search(raw):
        hits.append("copyright-symbol")
    if _URL_RE.search(raw):
        hits.append("url")
    if _EMAIL_RE.search(raw):
        hits.append("email")
    if _ISBN_RE.search(raw):
        hits.append("isbn")
    if _ISSN_RE.search(raw):
        hits.append("issn")
    if _DOI_RE.search(raw):
        hits.append("doi")
    normalized = _normalize(raw)
    for label, pattern in _WORD_PATTERNS:
        if pattern.search(normalized):
            hits.append(label)
    return sorted(set(hits))


def is_boilerplate_text(text: str) -> bool:
    """True when the text contains deterministic PDF-boilerplate markers."""
    return bool(boilerplate_hits(text))


# --------------------------------------------------------------------------- #
# Candidate (question) inspection
# --------------------------------------------------------------------------- #


def question_boilerplate_fields(question: AIQuizQuestion) -> list[str]:
    """Names of the question fields (prompt/answer/options/explanation) that hit boilerplate."""
    fields: list[str] = []
    if is_boilerplate_text(question.prompt):
        fields.append("prompt")
    if is_boilerplate_text(question.correct_answer):
        fields.append("answer")
    if is_boilerplate_text(question.explanation):
        fields.append("explanation")
    if any(is_boilerplate_text(option) for option in question.options or []):
        fields.append("options")
    return fields


def is_boilerplate_question(question: AIQuizQuestion) -> bool:
    """True when ANY field of the question contains boilerplate."""
    return bool(question_boilerplate_fields(question))


# --------------------------------------------------------------------------- #
# Fill-in-the-blank validation
# --------------------------------------------------------------------------- #

_BLANK_RE = re.compile(r"_{3,}")


def is_valid_fill_blank(prompt: str, answer: str) -> bool:
    """A fill-in-the-blank candidate is usable only when it has a real blank
    and a non-boilerplate, content-bearing answer."""
    if not _BLANK_RE.search(prompt or ""):
        return False
    answer = (answer or "").strip()
    if not answer or answer in {"_", "__", "___", "_____"}:
        return False
    if not re.search(r"[\w]", answer, flags=re.UNICODE):
        return False
    if is_boilerplate_text(answer):
        return False
    return True


# --------------------------------------------------------------------------- #
# Source cleaning: per-line boilerplate removal + repeated header/footer
# detection across pages (digit-insensitive, so "Page 3 of 12" and
# "Page 4 of 12" are recognized as the same footer).
# --------------------------------------------------------------------------- #

_PUNCT_ONLY_RE = re.compile(r"^\W+$", re.UNICODE)
_PURE_NUMBER_LINE_RE = re.compile(r"^\d{1,5}\s*$")
_PAGE_FOLIO_LINE_RE = re.compile(r"^(page|صفحة|صفحه)\s*\d+(\s+(of|من)\s*\d+)?\s*$", re.IGNORECASE)

_STRONG_LINE_RE = re.compile(
    r"all rights reserved|may not be (reproduced|copied|distributed|transmitted|used)|"
    r"no part of this|unauthorized (use|reproduction|copying)|"
    r"do not (copy|distribute|sell)|registered trademarks?|trademarks? of|"
    r"جميع الحقوق محفوظه|حقوق النشر|حقوق الطبع",
    re.IGNORECASE,
)

_BOILERPLATE_START_RE = re.compile(
    r"^\s*(published by|publisher|printed (in|by)|printing|for more information|"
    r"visit us|visit our|call us|terms of use|privacy policy|legal notice|"
    r"copyright|©|®|™|confidential|proprietary|internal use only|"
    r"دار النشر|الناشر|طبع|طبعه|رقم الايداع|ايداع)",
    re.IGNORECASE,
)

# Lines repeated on multiple pages are only removed as headers/footers when
# they are short enough to plausibly be one (a full repeated paragraph is
# more likely intentional educational repetition).
_MAX_HEADER_FOOTER_WORDS = 15


def is_boilerplate_line(line: str) -> bool:
    """True when an individual source line is PDF boilerplate (or empty/noise)."""
    s = line.strip()
    if not s or _PUNCT_ONLY_RE.match(s):
        return True
    if _SYMBOL_RE.search(s) or _URL_RE.search(s) or _EMAIL_RE.search(s):
        return True
    if _ISBN_RE.search(s) or _ISSN_RE.search(s) or _DOI_RE.search(s):
        return True
    if _PURE_NUMBER_LINE_RE.match(s) or _PAGE_FOLIO_LINE_RE.match(s):
        return True
    normalized = _normalize(s)
    if not normalized:
        return True
    if _STRONG_LINE_RE.search(s) or _STRONG_LINE_RE.search(normalized):
        return True
    if _BOILERPLATE_START_RE.match(s) or _BOILERPLATE_START_RE.match(normalized):
        return True
    # Standalone publisher/edition rows often omit an explicit "published
    # by" prefix. Keep this anchored to the whole row so educational uses of
    # words such as "pressure" or "edition" are unaffected.
    if re.fullmatch(
        r"(?:(?:[\w&'’\-]+\s+){0,5}(?:university\s+)?press(?:,?\s+\w+)*|"
        r"(?:first|second|third|fourth|fifth|revised|international)\s+edition)",
        s,
        re.IGNORECASE,
    ):
        return True
    return False


_COMPOSITE_BOUNDARY_RE = re.compile(
    r"(?<=[.!?؟])\s+|"
    r"(?=\b(?:copyright|all rights reserved|isbn|issn|doi|published by|printed by|"
    r"page\s+\d+\s+of\s+\d+)\b)|(?=[©®™])",
    re.IGNORECASE,
)


#: Leading list glyphs used by slide decks and lecture handouts. A bullet is
#: typography, not content: the sentence "- A primary key uniquely identifies
#: each row" is the same teaching sentence as its unbulleted twin. Left in
#: place the glyph becomes the sentence's first token, which stops it reading
#: as a definition and silently costs the document every bulleted concept.
#:
#: Only a glyph followed by whitespace is a bullet. That proviso keeps
#: "-5 degrees", "--verbose" and hyphenated fragments intact.
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[\u2022\u2023\u25AA\u25CF\u25E6\u2043\u2219*\u00B7]|[-\u2010-\u2015](?=\s))\s*")


def strip_bullet_prefix(line: str) -> str:
    """Remove a leading list glyph, preserving the text after it.

    Applied repeatedly so nested markers ("- - item") collapse, but never so
    far that the line is emptied of content.
    """
    text = line
    for _ in range(3):
        stripped = _BULLET_PREFIX_RE.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return text if text.strip() else line


def clean_source_line(line: str) -> str:
    """Remove metadata fragments while preserving adjacent educational text.

    Some PDF extractors flatten a complete page into one physical line.  A
    line-level copyright match must not therefore discard all preceding
    paragraphs. Suspicious composite lines are split at sentence/metadata
    boundaries and only fragments that are independently boilerplate are
    removed. Metadata-only lines still clean to an empty string.
    """
    source = strip_bullet_prefix(line.strip()).strip()
    if not source:
        return ""
    if not is_boilerplate_line(source):
        return source
    fragments = [part.strip() for part in _COMPOSITE_BOUNDARY_RE.split(source) if part.strip()]
    return " ".join(part for part in fragments if not is_boilerplate_line(part)).strip()


def line_key(line: str) -> str:
    """Digit-insensitive, whitespace-collapsed key for comparing lines across pages."""
    key = re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip().lower()))
    return key.strip()


def repeated_line_keys(units: Iterable["SourceUnit"]) -> set[str]:
    """Keys of lines that appear on two or more distinct pages."""
    pages_by_key: dict[str, set[int]] = {}
    for unit in units:
        seen: set[str] = set()
        for line in unit.text.splitlines():
            key = line_key(line)
            if len(key) < 2 or key in seen:
                continue
            seen.add(key)
            pages_by_key.setdefault(key, set()).add(unit.page)
    return {key for key, pages in pages_by_key.items() if len(pages) >= 2}


def _word_count(line: str) -> int:
    return len(line.split())


def clean_source_units(units: list["SourceUnit"]) -> list["SourceUnit"]:
    """Return the units with boilerplate lines and repeated headers/footers removed."""
    if not units:
        return []
    repeated = repeated_line_keys(units)
    cleaned: list["SourceUnit"] = []
    for unit in units:
        kept: list[str] = []
        for raw_line in unit.text.splitlines():
            line = clean_source_line(raw_line)
            if not line:
                continue
            key = line_key(line)
            if len(key) < 2:
                continue
            if key in repeated and _word_count(line) <= _MAX_HEADER_FOOTER_WORDS:
                continue
            kept.append(line)
        text = "\n".join(kept).strip()
        if text:
            cleaned.append(type(unit)(page=unit.page, text=text))
    return cleaned


def cleaned_source_block(
    units: list["SourceUnit"], *, title: str, page_count: int
) -> str:
    """Render cleaned units in the same ``<source ...>`` shape as ``AIDocumentSource.prompt_block``."""
    body = "\n\n".join(f"[Page {unit.page}]\n{unit.text}" for unit in units if unit.text)
    return f"<source title={title!r} pages={page_count}>\n{body}\n</source>"
