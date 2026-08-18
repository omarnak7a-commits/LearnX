"""Source-unit utilities and the educational-content sufficiency check.

This module used to host a frequency/heading-based concept extractor.  That
approach is gone: repetition, capitalization, and heading shape are not
evidence of educational importance, and ranking them produced exactly the
shallow questions this pipeline exists to prevent.  Understanding the document
is now :mod:`app.services.quiz_understanding`'s job.

What remains here is the plumbing every stage still needs:

* :class:`SourceUnit` and :func:`split_source_units` — turn ``[Page N]``
  marked text into page-attributed units.
* :func:`has_educational_content` — is there enough real teaching material to
  attempt a quiz at all?
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.quiz_scoring import content_token_list

_PAGE_MARKER = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)


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

_GENERIC_PHRASES = {
    "table of contents", "all rights reserved", "copyright", "introduction",
    "conclusion", "summary", "references", "bibliography", "appendix",
    "glossary", "index", "preface", "acknowledgements", "figure", "chapter",
    "section", "unit", "lesson", "objective", "objectives", "word count",
    "printed", "published", "edition",
}


def is_metadata_line(line: str) -> bool:
    """True when a line is page furniture rather than teaching text."""
    return bool(_METADATA_LINE.search(line))


def educational_content_tokens(units: list[SourceUnit]) -> list[str]:
    """Content-bearing tokens used by the sufficiency check.

    Measures semantic material after source cleaning, rather than page count,
    line count, or whether a particular regex happened to match.
    """
    tokens: list[str] = []
    for unit in units:
        tokens.extend(
            token
            for token in content_token_list(unit.text)
            if token not in _GENERIC_PHRASES and not token.isdigit()
        )
    return tokens


def has_educational_content(units: list[SourceUnit]) -> bool:
    """Whether cleaned units contain enough meaningful material for a quiz."""
    if not units:
        return False
    tokens = educational_content_tokens(units)
    unique = set(tokens)
    # A concise definition/explanation can be educational despite occupying one
    # PDF row. Formula-only notes are meaningful when they identify variables.
    if len(tokens) >= 5 and len(unique) >= 4:
        return True
    combined = " ".join(unit.text for unit in units)
    return bool(
        len(unique) >= 2
        and re.search(r"[A-Za-z\u0600-\u06FF]", combined)
        and re.search(r"[=+*/^]", combined)
    )
