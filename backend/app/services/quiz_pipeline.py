"""High-quality AI quiz generation pipeline.

Flow (mirrors the product spec):

    source PDF  ->  split by page/section  ->  deterministic concept map
    ->  importance scoring  ->  LLM candidate pool (MORE than needed)
    ->  per-candidate validation  ->  exact de-dup  ->  paraphrase de-dup
    ->  previous-question filtering  ->  multi-factor quality scoring
    ->  quality threshold  ->  diverse final selection  ->  seeded
    answer-position randomization  ->  existing AIQuizResponse contract.

The LLM is never asked to "just generate N questions". It receives the
high-value concept map, explicit difficulty/cognitive-skill/wording-pattern
instructions, the relevant source excerpts, and is asked for an over-sized
candidate pool that the deterministic layer then scores and trims.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import AIQuizQuestion
from app.services.ai_documents import AIDocumentSource
from app.services.ai_service import AIService, AIUnavailableError
from app.services.quiz_boilerplate import (
    clean_source_units,
    cleaned_source_block,
    is_boilerplate_text,
    is_valid_fill_blank,
)
from app.services.quiz_concepts import (
    Concept,
    build_concept_map,
    concept_map_block,
    split_source_units,
    top_concepts,
)
from app.services.quiz_scoring import (
    ScoredCandidate,
    duplicates_within,
    is_repeat_of_history,
    is_trivial_question,
    randomize_answer_positions,
    score_candidate,
    select_diverse,
    classify_cognitive_skill,
    classify_pattern,
    match_concept,
    content_tokens,
)

_DEFAULT_THRESHOLD = 0.55

# --------------------------------------------------------------------------- #
# Lenient LLM candidate schema
#
# The LLM is asked for ~20-32 candidates; a single malformed question must
# not invalidate the whole pool. We therefore validate leniently here and
# normalize/repair each candidate individually before scoring.
# --------------------------------------------------------------------------- #


class _RawCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    type: str = ""
    prompt: str = ""
    options: list[str] | None = None
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    source_pages: list[Any] = Field(default_factory=list)


class _RawQuizPool(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    questions: list[_RawCandidate] = Field(default_factory=list)


_TYPE_ALIASES = {
    "mcq": "mcq", "multiple-choice": "mcq", "multiple choice": "mcq", "multiple_choice": "mcq",
    "true-false": "true-false", "true_false": "true-false", "truefalse": "true-false",
    "true or false": "true-false", "trueorfalse": "true-false",
    "fill-blank": "fill-blank", "fill_blank": "fill-blank", "fillblank": "fill-blank",
    "fill in the blank": "fill-blank", "fill-in-the-blank": "fill-blank",
    "short-answer": "short-answer", "short_answer": "short-answer", "shortanswer": "short-answer",
    "short answer": "short-answer",
}

_TRUE_WORDS = {"true", "t", "yes", "correct", "right", "صح", "صحيح", "نعم"}
_FALSE_WORDS = {"false", "f", "no", "incorrect", "wrong", "خطا", "خطأ", "لا"}


@dataclass
class QuizContext:
    units: list[Any] = field(default_factory=list)
    concepts: list[Concept] = field(default_factory=list)
    vocab: set[str] = field(default_factory=set)
    page_text: dict[int, str] = field(default_factory=dict)
    included_pages: set[int] = field(default_factory=set)


@dataclass
class QuizGenerationResult:
    questions: list[AIQuizQuestion]
    provider: str
    model: str
    fallback_used: bool


# --------------------------------------------------------------------------- #
# Language & difficulty guidance
# --------------------------------------------------------------------------- #


def quiz_language_guidance(language: str) -> str:
    if language == "ar":
        return (
            "اكتب كل سؤال وكل خيار وكل تفسير بالعربية المصرية الطبيعية السهلة الواضحة للطلاب، "
            "مع الإبقاء على المصطلحات التقنية والعلمية القياسية كما هي بالإنجليزية "
            "(مثل API و Database و Backend). أبقِ الأرقام والمعادلات والرموز دون أي تغيير."
        )
    return (
        "Write every question, option, and explanation in clear study-ready English. "
        "Keep standard technical terms (e.g., API, Database, Backend) in English, and "
        "keep numbers, formulas, and symbols unchanged."
    )


_DIFFICULTY_GUIDANCE = {
    "easy": (
        "EASY: direct understanding/recall of an important concept — ask what something "
        "is, or its single most important fact."
    ),
    "medium": (
        "MEDIUM: requires connecting two concepts or interpreting information — ask how "
        "or why things relate."
    ),
    "hard": (
        "HARD: reasoning, application, comparison, cause/effect, or multi-step "
        "understanding of IMPORTANT concepts. Hard must NEVER mean obscure or trivial details."
    ),
    "mixed": "MIXED: produce a balanced spread of easy, medium, and hard questions.",
}

_COGNITIVE_SKILLS = (
    "understanding, application, cause/effect, comparison, process/order, "
    "factual recall, and misconception detection"
)

_WORDING_PATTERNS = (
    '"Why does X happen?", "Which statement best explains X?", '
    '"What would happen if X changed?", "Which step occurs next?", '
    '"How does X differ from Y?", "Which scenario demonstrates X?", '
    '"What is the main purpose of X?", "Which conclusion is best supported?", '
    '"Which statement is incorrect?", "What relationship exists between X and Y?"'
)


# --------------------------------------------------------------------------- #
# Context building
# --------------------------------------------------------------------------- #


def build_quiz_context(source: AIDocumentSource) -> QuizContext:
    # Source cleaning runs FIRST: boilerplate lines (copyright notices, legal
    # text, ISBNs/DOIs/URLs, page folios) and repeated headers/footers are
    # removed before any concept extraction or scoring sees the text.
    units = clean_source_units(split_source_units(source.text))
    concepts = build_concept_map(units)
    vocab: set[str] = set()
    for unit in units:
        vocab |= content_tokens(unit.text)
    page_text = {unit.page: unit.text for unit in units}
    included_pages = {unit.page for unit in units}
    return QuizContext(units=units, concepts=concepts, vocab=vocab, page_text=page_text, included_pages=included_pages)


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #


def build_candidate_prompt(
    *,
    source: AIDocumentSource,
    concepts: list[Concept],
    count: int,
    candidate_count: int,
    question_types: list[str],
    difficulty: str,
    kind: str,
    language: str,
    previous_questions: list[str],
    source_block: str | None = None,
) -> str:
    lines: list[str] = []
    lines.append(
        f"Generate exactly {candidate_count} candidate quiz questions for this study document "
        f"({kind} quiz). {candidate_count} is MORE than the {count} questions that will finally be "
        "selected, so produce a rich, varied candidate pool."
    )
    lines.append("")
    lines.append(
        "CONCEPT MAP — test ONLY these high-value concepts (or closely related sub-concepts "
        "visible in their evidence). Do not test unimportant details."
    )
    lines.append(concept_map_block(top_concepts(concepts, 12)))
    lines.append("")
    lines.append("DIFFICULTY RULE: " + _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["mixed"]))
    lines.append("")
    lines.append("QUESTION TYPES: " + ", ".join(question_types) + ".")
    lines.append("")
    lines.append("COGNITIVE DIVERSITY — mix these skills (only when the source supports them): " + _COGNITIVE_SKILLS + ".")
    lines.append("")
    lines.append(
        "WORDING DIVERSITY — do NOT write 'What is X?' for every question. Use varied patterns, "
        "for example: " + _WORDING_PATTERNS + ". Only use a pattern when the source supports it."
    )
    lines.append("")
    lines.append("RULES:")
    lines.append("- Use ONLY the supplied source; never invent facts, names, dates, or numbers.")
    lines.append("- Distribute questions across the important sections/pages — do not concentrate on one page.")
    lines.append("- MCQ: exactly 4 plausible options and exactly ONE correct answer. Distractors must be "
                 "plausible, similar in length, and related to the source — never absurd.")
    lines.append("- true-false: one clear statement whose truth value is unambiguous in the source; "
                 "vary True and False correct answers.")
    lines.append("- Every question needs: a unique id, a prompt, an explanation citing the source, "
                 "a difficulty (easy/medium/hard), and sourcePages (1-based page numbers where the answer is found).")
    lines.append("- NEVER ask about page numbers, ISBNs, headers, footers, metadata, word counts, or formatting.")
    lines.append("- NEVER write questions about copyright notices, publisher/legal/licensing text, "
                 "trademarks, DOIs, URLs, e-mail addresses, or any boilerplate repeated across pages. "
                 "The source below has already been cleaned of such material — do not reintroduce it. "
                 "If a page contains only such material, ignore that page entirely.")
    if previous_questions:
        lines.append("")
        lines.append("PREVIOUS QUESTIONS — do NOT repeat or paraphrase any of these:")
        for past in previous_questions[:30]:
            lines.append(f"- {past}")
    lines.append("")
    lines.append("SOURCE:")
    lines.append(source_block if source_block is not None else source.prompt_block())
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Candidate normalization
# --------------------------------------------------------------------------- #


def _coerce_pages(raw_pages: list[Any], page_count: int) -> list[int]:
    pages: list[int] = []
    for raw in raw_pages:
        try:
            page = int(str(raw).strip())
        except (ValueError, TypeError):
            continue
        if 1 <= page <= page_count and page not in pages:
            pages.append(page)
        if len(pages) >= 10:
            break
    return pages


def _normalize_true_false(options: list[str] | None, correct: str) -> tuple[list[str], str] | None:
    correct_polarity: bool | None = None
    key = correct.strip().lower()
    if key in _TRUE_WORDS:
        correct_polarity = True
    elif key in _FALSE_WORDS:
        correct_polarity = False
    else:
        # Fall back to the option list to infer polarity.
        for option in options or []:
            k = option.strip().lower()
            if k in _TRUE_WORDS:
                correct_polarity = True
                break
            if k in _FALSE_WORDS:
                correct_polarity = False
                break
    if correct_polarity is None:
        return None
    return (["True", "False"], "True" if correct_polarity else "False")


def _dedupe_options(options: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for option in options:
        option = option.strip()
        if not option:
            continue
        key = option.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(option)
    return out


def normalize_candidate(
    raw: _RawCandidate,
    *,
    index: int,
    allowed_types: set[str],
    page_count: int,
    included_pages: set[int],
) -> AIQuizQuestion | None:
    """Repair + validate one raw LLM candidate; return None when unusable."""
    qtype = _TYPE_ALIASES.get(raw.type.strip().lower().replace("_", " ").replace(" ", "-").replace("--", "-"))
    if qtype is None:
        qtype = _TYPE_ALIASES.get(raw.type.strip().lower())
    if qtype is None or (allowed_types and qtype not in allowed_types):
        return None

    prompt = (raw.prompt or "").strip()
    correct = (raw.correct_answer or "").strip()
    explanation = (raw.explanation or "").strip()
    if not prompt or not correct or not explanation:
        return None
    if len(prompt) > 700 or len(explanation) < 10:
        return None
    if is_trivial_question(prompt):
        return None
    # Deterministic boilerplate rejection: a candidate built on copyright,
    # legal, publisher, ISBN/DOI/URL, or page-folio text is unusable no matter
    # what the LLM (or the scoring layer) would say about it.
    if (
        is_boilerplate_text(prompt)
        or is_boilerplate_text(correct)
        or is_boilerplate_text(explanation)
    ):
        return None
    if qtype == "fill-blank" and not is_valid_fill_blank(prompt, correct):
        return None

    difficulty = (raw.difficulty or "").strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    # Pages are validated against the pages actually present in the extracted
    # text (which may be an allowed subset of the whole PDF), not the total
    # PDF page count.
    upper_page = max(included_pages) if included_pages else page_count
    pages = _coerce_pages(raw.source_pages, upper_page)
    if not pages:
        return None
    if included_pages and not (set(pages) & included_pages):
        return None

    options: list[str] | None = None
    if qtype == "true-false":
        tf = _normalize_true_false(raw.options, correct)
        if tf is None:
            return None
        options, correct = tf
    elif qtype == "mcq":
        cleaned = _dedupe_options(raw.options or [])
        if len(cleaned) < 2:
            return None
        if not any(option.casefold() == correct.casefold() for option in cleaned):
            cleaned.append(correct)
        if any(is_boilerplate_text(option) for option in cleaned):
            return None
        options = cleaned[:6]

    qid = (raw.id or "").strip()[:100] or f"q{index}"
    try:
        return AIQuizQuestion(
            id=qid,
            type=qtype,  # type: ignore[arg-type]
            prompt=prompt,
            options=options,
            correct_answer=correct,
            explanation=explanation,
            difficulty=difficulty,  # type: ignore[arg-type]
            source_pages=pages,
        )
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Pipeline entry point
# --------------------------------------------------------------------------- #


def generate_quiz(
    service: AIService,
    source: AIDocumentSource,
    *,
    count: int,
    question_types: list[str],
    difficulty: str,
    kind: str,
    language: str,
    seed: int,
    previous_questions: list[str],
    system_prompt: str,
    quality_threshold: float = _DEFAULT_THRESHOLD,
) -> QuizGenerationResult:
    context = build_quiz_context(source)
    allowed_types = set(question_types)

    # A source whose text is ENTIRELY boilerplate (copyright pages, legal
    # notices, headers/footers) has no educational content to test.
    if not context.units:
        raise AIUnavailableError("The source contains no educational content to build questions from.")

    candidate_count = min(32, max(count * 4, 20))

    user_prompt = build_candidate_prompt(
        source=source,
        concepts=context.concepts,
        count=count,
        candidate_count=candidate_count,
        question_types=question_types,
        difficulty=difficulty,
        kind=kind,
        language=language,
        previous_questions=previous_questions,
        source_block=cleaned_source_block(
            context.units, title=source.title, page_count=source.page_count
        ),
    )
    system_prompt = f"{system_prompt}\n\n{quiz_language_guidance(language)}"

    completion = service.complete_structured(
        response_model=_RawQuizPool,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=12000,
    )

    candidates: list[AIQuizQuestion] = []
    used_ids: set[str] = set()
    for index, raw in enumerate(completion.value.questions):
        question = normalize_candidate(
            raw,
            index=index,
            allowed_types=allowed_types,
            page_count=source.page_count,
            included_pages=context.included_pages,
        )
        if question is None:
            continue
        # Ensure globally unique ids (the frontend keys QuizRunner by id).
        if question.id in used_ids:
            question = question.model_copy(update={"id": f"{question.id}-{index}"})
        used_ids.add(question.id)
        candidates.append(question)

    # Duplicate removal (exact + paraphrase) then previous-question filtering.
    candidates = duplicates_within(candidates)
    candidates = [
        q for q in candidates if not is_repeat_of_history(q, previous_questions)
    ]

    # Multi-factor quality scoring + threshold.
    scored: list[ScoredCandidate] = []
    for question in candidates:
        result = score_candidate(
            question,
            concepts=context.concepts,
            vocab=context.vocab,
            page_text=context.page_text,
            included_pages=context.included_pages,
            requested_difficulty=difficulty,
            history=previous_questions,
        )
        if result.total >= quality_threshold:
            scored.append(
                ScoredCandidate(
                    question=question,
                    score=result.total,
                    concept=match_concept(question, context.concepts)[0].name,
                    skill=classify_cognitive_skill(question.prompt),
                    pattern=classify_pattern(question.prompt),
                )
            )

    if not scored:
        raise AIUnavailableError("The provider did not return usable quiz questions.")

    rng = random.Random(seed)
    selected = select_diverse(scored, count, rng=rng)
    questions = [randomize_answer_positions(q, rng) for q in selected]
    return QuizGenerationResult(
        questions=questions,
        provider=completion.provider,
        model=completion.model,
        fallback_used=completion.fallback_used,
    )
