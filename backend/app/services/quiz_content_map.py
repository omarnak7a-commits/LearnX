"""Teacher-oriented important-content mapping for quiz generation.

The old quiz path ranked regex matches and repeated phrases directly.  That is
useful for finding evidence, but it is not a curriculum model: a repeated box
colour can outrank a mechanism.  This module adds the semantic stage that must
exist *before* any question is written.

The LLM proposes a classification and exact evidence quotations.  The backend
then verifies every quotation against the cleaned source, assigns category-
level importance independently of repetition, and marks which items may feed
question blueprints.  Invalid proposals are discarded.  A conservative,
provider-free fallback converts the existing extractors into the same model;
repeated terms and unclassified names are always minor details in that path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.quiz_boilerplate import is_boilerplate_text
from app.services.quiz_concepts import Concept, SourceUnit
from app.services.quiz_scoring import content_token_list, content_tokens, normalize_question_text

ContentCategory = Literal[
    "core_concept",
    "important_definition",
    "process_mechanism",
    "cause_effect",
    "comparison",
    "formula_rule",
    "important_example",
    "minor_detail",
    "metadata_boilerplate",
]

QUESTION_WORTHY_CATEGORIES: frozenset[str] = frozenset(
    {
        "core_concept",
        "important_definition",
        "process_mechanism",
        "cause_effect",
        "comparison",
        "formula_rule",
    }
)
EXAMPLE_CATEGORY = "important_example"
NEVER_QUESTION_CATEGORIES: frozenset[str] = frozenset(
    {"minor_detail", "metadata_boilerplate"}
)

_CATEGORY_LABELS: dict[str, str] = {
    "core_concept": "A — core concept or central principle",
    "important_definition": "B — important definition",
    "process_mechanism": "C — process or mechanism",
    "cause_effect": "D — cause/effect relationship",
    "comparison": "E — meaningful comparison or distinction",
    "formula_rule": "F — formula, rule, or constraint",
    "important_example": "G — example that explains an important idea",
    "minor_detail": "H — minor/supporting detail",
    "metadata_boilerplate": "I — metadata or boilerplate",
}

# The category is the primary importance signal.  Provider labels can make a
# small adjustment, but repetition, heading shape, and sentence length never
# determine whether an item is major content.
_CATEGORY_IMPORTANCE: dict[str, float] = {
    "core_concept": 0.94,
    "important_definition": 0.91,
    "process_mechanism": 0.90,
    "cause_effect": 0.89,
    "comparison": 0.88,
    "formula_rule": 0.91,
    "important_example": 0.58,
    "minor_detail": 0.22,
    "metadata_boilerplate": 0.0,
}

_CATEGORY_ALIASES: dict[str, str] = {
    "core": "core_concept",
    "core concept": "core_concept",
    "central principle": "core_concept",
    "definition": "important_definition",
    "important definition": "important_definition",
    "process": "process_mechanism",
    "mechanism": "process_mechanism",
    "process/mechanism": "process_mechanism",
    "cause effect": "cause_effect",
    "cause/effect": "cause_effect",
    "relationship": "cause_effect",
    "comparison distinction": "comparison",
    "distinction": "comparison",
    "formula": "formula_rule",
    "rule": "formula_rule",
    "formula/rule": "formula_rule",
    "example": "important_example",
    "important example": "important_example",
    "minor": "minor_detail",
    "detail": "minor_detail",
    "minor detail": "minor_detail",
    "metadata": "metadata_boilerplate",
    "boilerplate": "metadata_boilerplate",
    "metadata/boilerplate": "metadata_boilerplate",
}


@dataclass(frozen=True)
class ContentItem:
    """A backend-verified teaching target and its exact source evidence."""

    id: str
    concept: str
    category: ContentCategory
    importance: float
    knowledge_targets: tuple[str, ...]
    evidence: str
    pages: tuple[int, ...]
    rationale: str = ""
    source: str = "semantic_map"

    @property
    def eligible_for_questions(self) -> bool:
        return self.category in QUESTION_WORTHY_CATEGORIES or self.category == EXAMPLE_CATEGORY

    @property
    def primary(self) -> bool:
        return self.category in QUESTION_WORTHY_CATEGORIES


class _RawContentItem(BaseModel):
    """Lenient provider shape; authoritative checks happen after parsing."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    concept: str = ""
    category: str = ""
    importance: str = "medium"
    knowledge_targets: list[str] = Field(default_factory=list)
    source_quote: str = ""
    source_pages: list[Any] = Field(default_factory=list)
    rationale: str = ""


class _RawContentMap(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    items: list[_RawContentItem] = Field(default_factory=list)


def category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category)


def _category(raw: str) -> ContentCategory | None:
    key = (raw or "").strip().lower().replace("-", "_")
    key = re.sub(r"\s+", " ", key)
    canonical = key if key in _CATEGORY_IMPORTANCE else _CATEGORY_ALIASES.get(key.replace("_", " "))
    if canonical in _CATEGORY_IMPORTANCE:
        return canonical  # type: ignore[return-value]
    return None


def _evidence_normalize(text: str) -> str:
    # PDF extraction frequently inserts line breaks or spaced punctuation.
    # Comparing word streams keeps the check exact in substance without being
    # brittle to those layout artefacts.
    return " ".join(content_token_list(text))


def quote_is_grounded(
    quote: str,
    *,
    pages: list[int] | tuple[int, ...],
    page_text: dict[int, str],
    category: str | None = None,
) -> bool:
    """Require a proposed quote to occur contiguously on a claimed page."""
    quote_key = _evidence_normalize(quote)
    minimum_tokens = 2 if category == "formula_rule" else 4
    if len(quote_key) < 6 or len(quote_key.split()) < minimum_tokens:
        return False
    return any(quote_key in _evidence_normalize(page_text.get(page, "")) for page in pages)


def quotes_equivalent(left: str, right: str) -> bool:
    """True when two evidence spans are identical or one is an exact subspan."""
    a = _evidence_normalize(left)
    b = _evidence_normalize(right)
    if not a or not b:
        return False
    return a == b or (len(a.split()) >= 4 and a in b) or (len(b.split()) >= 4 and b in a)


_LAYOUT_DETAIL = re.compile(
    r"(?:\b(?:red|blue|green|yellow|orange|purple|black|white|grey|gray)\b.{0,80}"
    r"\b(?:box|font|ink|heading|caption|margin|layout|printed|highlighted)\b|"
    r"\b(?:box|font|ink|heading|caption|margin|layout|printed|highlighted)\b.{0,80}"
    r"\b(?:red|blue|green|yellow|orange|purple|black|white|grey|gray)\b)",
    re.IGNORECASE,
)


def _is_deterministic_minor_detail(concept: str, evidence: str) -> bool:
    """Catch obvious page-design trivia even when a provider promotes it."""
    return bool(_LAYOUT_DETAIL.search(f"{concept} {evidence}"))


def _coerce_pages(raw_pages: list[Any], included_pages: set[int]) -> list[int]:
    pages: list[int] = []
    for value in raw_pages:
        try:
            page = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if page in included_pages and page not in pages:
            pages.append(page)
    return pages[:10]


def _knowledge_targets(raw: list[str], concept: str, evidence: str, category: str) -> tuple[str, ...]:
    targets: list[str] = []
    evidence_tokens = content_tokens(f"{concept} {evidence}")
    for value in raw:
        target = re.sub(r"\s+", " ", (value or "").strip()).strip("-:;,. ")
        if not (4 <= len(target) <= 180) or is_boilerplate_text(target):
            continue
        # A target must substantially resolve to the verified evidence; one
        # shared topic word cannot license an outside fact as an objective.
        target_tokens = content_tokens(target)
        if not target_tokens or len(target_tokens & evidence_tokens) / len(target_tokens) < 0.60:
            continue
        target_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", target))
        evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence))
        if not target_numbers.issubset(evidence_numbers):
            continue
        key = normalize_question_text(target)
        if key and all(normalize_question_text(item) != key for item in targets):
            targets.append(target)
        if len(targets) == 4:
            break
    if targets:
        return tuple(targets)

    defaults = {
        "core_concept": f"meaning and role of {concept}",
        "important_definition": f"definition and distinguishing features of {concept}",
        "process_mechanism": f"steps and mechanism of {concept}",
        "cause_effect": f"cause and resulting effect involving {concept}",
        "comparison": f"distinction expressed by {concept}",
        "formula_rule": f"meaning and correct use of {concept}",
        "important_example": f"principle demonstrated by {concept}",
        "minor_detail": f"supporting detail about {concept}",
        "metadata_boilerplate": f"metadata about {concept}",
    }
    return (defaults[category],)


def _importance(category: str, label: str) -> float:
    adjustment = {"high": 0.04, "medium": 0.0, "low": -0.08}.get(label.strip().lower(), 0.0)
    # Categories H/I cannot be promoted by a provider's importance label.
    if category in NEVER_QUESTION_CATEGORIES:
        adjustment = min(0.0, adjustment)
    return round(max(0.0, min(1.0, _CATEGORY_IMPORTANCE[category] + adjustment)), 3)


def normalize_content_map(raw_map: _RawContentMap, units: list[SourceUnit]) -> list[ContentItem]:
    """Ground, classify, merge, and rank a provider-proposed content map."""
    page_text = {unit.page: unit.text for unit in units}
    included_pages = set(page_text)
    items: list[ContentItem] = []
    seen: dict[tuple[str, str], int] = {}

    for index, raw in enumerate(raw_map.items[:60]):
        category = _category(raw.category)
        concept = re.sub(r"\s+", " ", raw.concept.strip()).strip("-:;,. ")
        evidence = re.sub(r"\s+", " ", raw.source_quote.strip())
        pages = _coerce_pages(raw.source_pages, included_pages)
        if category is None or not (2 < len(concept) <= 160) or not pages:
            continue
        if category not in NEVER_QUESTION_CATEGORIES and _is_deterministic_minor_detail(concept, evidence):
            category = "minor_detail"
        # Metadata is retained in the map as an explicit excluded category so
        # the planner can distinguish "classified and forbidden" from
        # "overlooked". Boilerplate must never survive under any other label.
        if category != "metadata_boilerplate" and (
            is_boilerplate_text(concept) or is_boilerplate_text(evidence)
        ):
            continue
        if not quote_is_grounded(evidence, pages=pages, page_text=page_text, category=category):
            continue
        # A concept label must actually identify its evidence unless the item
        # is explicitly metadata (retained only so the map still classifies I).
        if category != "metadata_boilerplate" and not (
            content_tokens(concept) & content_tokens(evidence)
        ):
            continue

        targets = _knowledge_targets(raw.knowledge_targets, concept, evidence, category)
        key = (normalize_question_text(concept), category)
        item = ContentItem(
            id=(raw.id.strip()[:80] or f"content-{index + 1}"),
            concept=concept,
            category=category,
            importance=_importance(category, raw.importance),
            knowledge_targets=targets,
            evidence=evidence,
            pages=tuple(sorted(set(pages))),
            rationale=raw.rationale.strip()[:400],
        )
        existing_index = seen.get(key)
        if existing_index is None:
            seen[key] = len(items)
            items.append(item)
            continue

        existing = items[existing_index]
        merged_targets = tuple(dict.fromkeys((*existing.knowledge_targets, *item.knowledge_targets)))[:4]
        # Keep the richer exact evidence while retaining every valid page.
        richer = item if len(content_tokens(item.evidence)) > len(content_tokens(existing.evidence)) else existing
        items[existing_index] = ContentItem(
            id=existing.id,
            concept=existing.concept,
            category=existing.category,
            importance=max(existing.importance, item.importance),
            knowledge_targets=merged_targets,
            evidence=richer.evidence,
            pages=tuple(sorted(set((*existing.pages, *item.pages)))),
            rationale=existing.rationale or item.rationale,
            source=existing.source,
        )

    return sorted(
        items,
        key=lambda item: (
            item.category == "metadata_boilerplate",
            item.category == "minor_detail",
            item.category == "important_example",
            -item.importance,
            item.concept.casefold(),
        ),
    )


def build_content_map_prompt(*, source_block: str, suggested_concepts: list[Concept], max_items: int) -> str:
    """Prompt for semantic classification only—never final questions."""
    signals = []
    for concept in suggested_concepts[:18]:
        signals.append(
            f"- possible signal: {concept.name!r}; detector={concept.kind}; "
            f"pages={concept.pages}; evidence={concept.evidence[:240]!r}"
        )
    signal_block = "\n".join(signals) if signals else "- no deterministic signals; inspect the source directly"
    categories = "\n".join(f"- {label}" for label in _CATEGORY_LABELS.values())
    return f"""Act as a teacher planning an assessment. Build an IMPORTANT-CONTENT MAP before any questions are written.

Classify source ideas into exactly these categories:
{categories}

Semantic priority rules:
- Identify what a student must understand to explain the subject, not what words repeat most.
- A heading, repeated phrase, long sentence, page spread, or formatting emphasis is NOT by itself evidence of importance.
- Prefer central principles, indispensable definitions, mechanisms, causal relationships, comparisons, and rules.
- Examples are secondary and are important only when they illuminate one of those ideas.
- Explicitly label incidental colours, layout, names, isolated examples, and side facts as minor_detail.
- Explicitly label page furniture, title/author/publisher/legal text, URLs, ISBNs, and other document metadata as metadata_boilerplate.

Grounding rules enforced by the backend:
- For every item, copy one short source_quote VERBATIM from the claimed source_pages. Do not use ellipses.
- The concept and each concrete knowledge_target must be supported by that quote.
- Give 1-4 distinct knowledge targets (for example: definition, mechanism step, cause, effect, distinction, rule use).
- Do not write quiz questions, options, or scenarios yet.
- Return at most {max_items} items; include minor/metadata items only when they are plausible traps worth explicitly excluding.

Deterministic extraction signals are hints, not rankings. Correct or ignore them:
{signal_block}

CLEANED SOURCE:
{source_block}
"""


def _fallback_category(concept: Concept) -> ContentCategory:
    return {
        "definition": "important_definition",
        "process": "process_mechanism",
        "relationship": "cause_effect",
        "comparison": "comparison",
        "formula": "formula_rule",
        "numbered_heading": "core_concept",
        "heading": "core_concept",
        "objective": "core_concept",
        "source_section": "core_concept",
        # Frequency and capitalization are discovery signals only.  They never
        # promote an item into the teacher-worthy categories.
        "multiword_term": "minor_detail",
        "repeated_term": "minor_detail",
    }.get(concept.kind, "minor_detail")  # type: ignore[return-value]


def fallback_content_map(concepts: list[Concept], units: list[SourceUnit]) -> list[ContentItem]:
    """Conservative provider-free map used only when semantic planning yields nothing."""
    page_text = {unit.page: unit.text for unit in units}
    items: list[ContentItem] = []
    seen: set[tuple[str, str]] = set()
    for index, concept in enumerate(concepts):
        category = _fallback_category(concept)
        evidence = re.sub(r"\s+", " ", concept.evidence.strip())
        pages = [page for page in concept.pages if page in page_text]
        # Headings alone are not answer evidence.  Attach the first nearby
        # educational sentence so the fallback remains source-resolvable.
        if category == "core_concept" and len(content_tokens(evidence)) < 4 and pages:
            candidates = re.split(r"(?<=[.!?؟])\s+|\n+", page_text[pages[0]])
            nearby = next(
                (part.strip() for part in candidates if len(content_tokens(part)) >= 5),
                "",
            )
            evidence = nearby or evidence
        if not pages or not quote_is_grounded(evidence, pages=pages, page_text=page_text, category=category):
            continue
        key = (normalize_question_text(concept.name), category)
        if key in seen or is_boilerplate_text(concept.name) or is_boilerplate_text(evidence):
            continue
        seen.add(key)
        items.append(
            ContentItem(
                id=f"fallback-{index + 1}",
                concept=concept.name,
                category=category,
                importance=_CATEGORY_IMPORTANCE[category],
                knowledge_targets=_knowledge_targets([], concept.name, evidence, category),
                evidence=evidence,
                pages=tuple(sorted(set(pages))),
                rationale=f"Conservative fallback from {concept.kind}; category importance, not frequency.",
                source="deterministic_fallback",
            )
        )
    return sorted(items, key=lambda item: (not item.primary, -item.importance, item.concept.casefold()))[:32]


def content_map_block(items: list[ContentItem]) -> str:
    lines: list[str] = []
    for item in items:
        targets = " | ".join(item.knowledge_targets)
        lines.append(
            f"- [{item.id}] {item.concept} — {category_label(item.category)}; "
            f"importance={item.importance:.2f}; pages={list(item.pages)}; targets={targets}; "
            f"exact evidence={item.evidence!r}"
        )
    return "\n".join(lines) or "(no verified content items)"
