"""Source-grounded, teacher-planned AI quiz generation.

Production flow:

    PDF extraction -> boilerplate cleaning -> deterministic evidence signals
    -> semantic important-content map (A-I) -> backend grounding/classification
    -> teacher-style question blueprints -> LLM candidate variants
    -> blueprint/type/evidence hard gates -> objective + wording deduplication
    -> exact eight-factor quality score -> cognitive diversity selection
    -> seeded option ordering -> unchanged public response contract.

The provider proposes maps and question prose.  It never decides what survives.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import AIQuizQuestion
from app.services.ai_documents import AIDocumentSource
from app.services.ai_service import AIService, AIUnavailableError
from app.services.quiz_blueprints import (
    QuestionBlueprint,
    blueprint_block,
    build_question_blueprints,
)
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
    has_educational_content,
    split_source_units,
    top_concepts,
)
from app.services.quiz_content_map import (
    ContentItem,
    _RawContentMap,
    build_content_map_prompt,
    content_map_block,
    fallback_content_map,
    normalize_content_map,
    quote_is_grounded,
    quotes_equivalent,
)
from app.services.quiz_scoring import (
    ScoredCandidate,
    classify_cognitive_skill,
    classify_pattern,
    content_jaccard,
    content_tokens,
    distractor_quality_score,
    exact_duplicate_key,
    is_repeat_of_history,
    is_trivial_question,
    normalize_question_text,
    randomize_answer_positions,
    score_blueprinted_candidate,
    select_diverse,
)

_DEFAULT_THRESHOLD = 0.68
_MIN_GROUNDING = 0.72
_MIN_DISTRACTORS = 0.55


class _RawCandidate(BaseModel):
    """Lenient provider shape; malformed entries do not invalidate the pool."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    blueprint_id: str = ""
    type: str = ""
    prompt: str = ""
    options: list[str] | None = None
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    source_pages: list[Any] = Field(default_factory=list)
    source_quote: str = ""
    distractor_rationales: list[str] = Field(default_factory=list)
    false_statement_basis: str = ""


class _RawQuizPool(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    questions: list[_RawCandidate] = Field(default_factory=list)


_TYPE_ALIASES = {
    "mcq": "mcq",
    "multiple-choice": "mcq",
    "multiple choice": "mcq",
    "multiple_choice": "mcq",
    "true-false": "true-false",
    "true_false": "true-false",
    "truefalse": "true-false",
    "true or false": "true-false",
    "trueorfalse": "true-false",
    "fill-blank": "fill-blank",
    "fill_blank": "fill-blank",
    "fillblank": "fill-blank",
    "fill in the blank": "fill-blank",
    "fill-in-the-blank": "fill-blank",
    "short-answer": "short-answer",
    "short_answer": "short-answer",
    "shortanswer": "short-answer",
    "short answer": "short-answer",
}
_TRUE_WORDS = {"true", "t", "yes", "correct", "right", "صح", "صحيح", "نعم"}
_FALSE_WORDS = {"false", "f", "no", "incorrect", "wrong", "خطا", "خطأ", "لا"}
_GENERIC_BLANK_ANSWERS = {
    "thing",
    "things",
    "process",
    "system",
    "method",
    "concept",
    "information",
    "example",
    "result",
    "important",
    "document",
    "page",
    "section",
    "it",
    "they",
}
_SOURCE_REFERENCE = re.compile(
    r"\b(according to|in the source|the document|the text|the passage|the pdf|on page|mentioned|discussed)\b",
    re.IGNORECASE,
)


@dataclass
class QuizContext:
    units: list[Any] = field(default_factory=list)
    concepts: list[Concept] = field(default_factory=list)
    content_map: list[ContentItem] = field(default_factory=list)
    blueprints: list[QuestionBlueprint] = field(default_factory=list)
    vocab: set[str] = field(default_factory=set)
    page_text: dict[int, str] = field(default_factory=dict)
    included_pages: set[int] = field(default_factory=set)


@dataclass
class CandidateRecord:
    question: AIQuizQuestion
    blueprint: QuestionBlueprint
    source_quote: str
    distractor_rationales: tuple[str, ...] = ()


@dataclass
class QuizGenerationResult:
    questions: list[AIQuizQuestion]
    provider: str
    model: str
    fallback_used: bool


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
    "easy": "EASY: direct understanding or recall of an important concept.",
    "medium": "MEDIUM: connect or interpret supported ideas.",
    "hard": (
        "HARD: reason, apply, compare, or analyze IMPORTANT source ideas. "
        "Hard never means an obscure detail."
    ),
    "mixed": "MIXED: use each blueprint's planned easy/medium/hard level.",
}


def build_quiz_context(source: AIDocumentSource) -> QuizContext:
    # Existing boilerplate protection remains the first layer.  Neither the
    # semantic mapper nor the question writer sees removed headers/legal text.
    units = clean_source_units(split_source_units(source.text))
    concepts = build_concept_map(units)
    vocab: set[str] = set()
    for unit in units:
        vocab |= content_tokens(unit.text)
    return QuizContext(
        units=units,
        concepts=concepts,
        vocab=vocab,
        page_text={unit.page: unit.text for unit in units},
        included_pages={unit.page for unit in units},
    )


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
    blueprints: list[QuestionBlueprint] | None = None,
    content_items: list[ContentItem] | None = None,
) -> str:
    """Build the writer prompt.

    Production passes blueprints and therefore supplies only verified evidence
    packets—not raw PDF text.  The legacy branch keeps this utility backwards
    compatible for tests and callers that only render a prompt.
    """
    if not blueprints:
        return "\n".join(
            [
                f"Generate exactly {candidate_count} candidate quiz questions for this {kind} quiz.",
                "CONCEPT MAP — test ONLY high-value concepts:",
                concept_map_block(top_concepts(concepts, 12)),
                "QUESTION TYPES: " + ", ".join(question_types),
                "EXCLUDE BOILERPLATE: never ask about copyright, trademarks, publisher metadata, URLs, ISBNs, or repeated headers, footers, and page furniture.",
                "PREVIOUS QUESTIONS — do NOT repeat or paraphrase any of these:",
                *[f"- {past}" for past in previous_questions[:30]],
                "SOURCE:",
                source_block if source_block is not None else source.prompt_block(),
            ]
        )

    lines = [
        f"Write exactly {candidate_count} candidate variants for a {kind} quiz; {count} will survive.",
        "The backend has already classified source importance and designed the blueprints below.",
        "Use a blueprint_id exactly as written. Do not invent, merge, or reinterpret an objective.",
        "Cover every blueprint once before writing a second wording for any blueprint.",
        "",
        "VERIFIED IMPORTANT-CONTENT MAP (H/I are intentionally absent):",
        content_map_block(content_items or []),
        "",
        "TEACHER QUESTION BLUEPRINTS:",
        blueprint_block(blueprints),
        "",
        "HARD RULES:",
        "- Use only the blueprint's verbatim evidence. No outside facts, assumptions, examples, names, or numbers.",
        "- Copy that blueprint evidence verbatim into source_quote and cite only its source pages.",
        "- Match the planned question type, cognitive skill, knowledge target, and difficulty.",
        "- APPLICATION means transfer, not a label: require a changed condition, prediction, calculation, outcome, or decision. Never turn recall into application by merely prefixing 'Suppose', 'Given', or 'Scenario'.",
        "- Never ask what the source/document/page says; ask about the subject itself.",
        "- MCQ: exactly four unique, parallel options and one matching correct answer. Every distractor must be a plausible same-category misconception using source-domain terms. Provide exactly three distractor_rationales explaining why each wrong option is tempting but contradicted by the evidence.",
        "- True/false: test a meaningful relationship, mechanism, distinction, or constraint—not mere word swapping. A false statement must alter one source-resolvable relation and provide false_statement_basis.",
        "- Fill-blank: blank exactly one meaningful technical term, formula component, or concept. The answer must appear verbatim in the evidence; never blank a generic word.",
        "- Application: use a small scenario that applies only the relationship explicitly present in the evidence. Do not add real-world conditions that are absent.",
        "- Explanations must state why the answer follows from the quoted evidence; do not merely say that it is correct.",
        "- Never generate metadata, formatting, copyright, publisher, URL, ISBN, header, or footer questions.",
        "DIFFICULTY RULE: " + _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["mixed"]),
    ]
    if previous_questions:
        lines.extend(["", "PREVIOUS QUESTIONS — do not repeat or paraphrase:"])
        lines.extend(f"- {past}" for past in previous_questions[:30])
    return "\n".join(lines)


def _canonical_type(value: str) -> str | None:
    raw = (value or "").strip().lower()
    return _TYPE_ALIASES.get(raw) or _TYPE_ALIASES.get(raw.replace("_", " "))


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
    key = normalize_question_text(correct)
    if key in _TRUE_WORDS:
        return ["True", "False"], "True"
    if key in _FALSE_WORDS:
        return ["True", "False"], "False"
    return None


def _dedupe_options(options: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for option in options:
        value = option.strip()
        key = normalize_question_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def normalize_candidate(
    raw: _RawCandidate,
    *,
    index: int,
    allowed_types: set[str],
    page_count: int,
    included_pages: set[int],
) -> AIQuizQuestion | None:
    """Basic public-shape normalization; production applies blueprint gates next."""
    qtype = _canonical_type(raw.type)
    if qtype is None or (allowed_types and qtype not in allowed_types):
        return None
    prompt = raw.prompt.strip()
    correct = raw.correct_answer.strip()
    explanation = raw.explanation.strip()
    if not prompt or not correct or len(explanation) < 10 or len(prompt) > 700:
        return None
    if is_trivial_question(prompt) or _SOURCE_REFERENCE.search(prompt):
        return None
    if any(is_boilerplate_text(value) for value in (prompt, correct, explanation)):
        return None
    if qtype == "fill-blank" and not is_valid_fill_blank(prompt, correct):
        return None

    pages = _coerce_pages(raw.source_pages, max(included_pages) if included_pages else page_count)
    if not pages or (included_pages and not set(pages).issubset(included_pages)):
        return None

    options: list[str] | None = None
    if qtype == "true-false":
        normalized = _normalize_true_false(raw.options, correct)
        if normalized is None:
            return None
        options, correct = normalized
    elif qtype == "mcq":
        cleaned = _dedupe_options(raw.options or [])
        correct_key = normalize_question_text(correct)
        if correct_key not in {normalize_question_text(option) for option in cleaned} and len(cleaned) == 3:
            cleaned.append(correct)
        # Exactly four is a hard contract now; never truncate six arbitrary
        # options or silently return a two-choice "MCQ".
        if len(cleaned) != 4 or sum(normalize_question_text(option) == correct_key for option in cleaned) != 1:
            return None
        if any(is_boilerplate_text(option) for option in cleaned):
            return None
        options = cleaned

    difficulty = raw.difficulty.strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    try:
        return AIQuizQuestion(
            id=(raw.id.strip()[:100] or f"q{index}"),
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


def _answer_is_supported(question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    if question.type == "true-false":
        return True
    answer = normalize_question_text(question.correct_answer)
    evidence = normalize_question_text(blueprint.evidence)
    if answer and answer in evidence:
        return True
    answer_tokens = content_tokens(question.correct_answer)
    evidence_tokens = content_tokens(blueprint.evidence)
    if not answer_tokens:
        return False
    # Every substantive answer token—not merely a majority—must be present in
    # exact verified evidence. For Arabic, the lightweight tokenizer can emit
    # a different inflected form (for example تحويل / يحول); permit only a
    # close same-script character stem, never an arbitrary extra assertion.
    unsupported = answer_tokens - evidence_tokens
    for token in unsupported:
        if not re.search(r"[\u0600-\u06ff]", token):
            return False
        token_chars = set(token)
        if not any(
            re.search(r"[\u0600-\u06ff]", evidence_token)
            and len(token_chars & set(evidence_token)) / max(1, len(token_chars | set(evidence_token))) >= 0.70
            for evidence_token in evidence_tokens
        ):
            return False
    answer_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", question.correct_answer))
    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", blueprint.evidence))
    return answer_numbers.issubset(evidence_numbers)


def _meaningful_fill_blank(question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    blanks = re.findall(r"_{3,}", question.prompt)
    answer_key = normalize_question_text(question.correct_answer)
    if len(blanks) != 1 or not answer_key or answer_key in _GENERIC_BLANK_ANSWERS:
        return False
    if not (1 <= len(content_tokens(question.correct_answer)) <= 6):
        return False
    if answer_key not in normalize_question_text(blueprint.evidence):
        return False
    if len(content_tokens(question.prompt)) < 4:
        return False
    return blueprint.category in {
        "core_concept",
        "important_definition",
        "process_mechanism",
        "formula_rule",
    }


def _meaningful_true_false(raw: _RawCandidate, question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    prompt_tokens = content_tokens(question.prompt)
    evidence_tokens = content_tokens(blueprint.evidence)
    if len(prompt_tokens) < 4 or question.prompt.rstrip().endswith("?"):
        return False
    if normalize_question_text(question.prompt) == normalize_question_text(blueprint.evidence):
        return False
    # A true/false statement may paraphrase the source or alter one relation,
    # but cannot use a shared topic word to introduce an unrelated assertion.
    unsupported = prompt_tokens - evidence_tokens
    if len(prompt_tokens & evidence_tokens) / max(1, len(prompt_tokens)) < 0.65 or len(unsupported) > 2:
        return False
    correct = normalize_question_text(question.correct_answer)
    if correct == "false":
        basis = raw.false_statement_basis.strip()
        basis_tokens = content_tokens(basis)
        if (
            len(basis) < 8
            or not basis_tokens
            or len(basis_tokens & evidence_tokens) / len(basis_tokens) < 0.70
        ):
            return False
    return blueprint.cognitive_skill != "factual_recall"


_APPLICATION_TASK_PATTERNS = (
    "what would happen",
    "how would",
    "predict",
    "which outcome",
    "likely outcome",
    "most likely",
    "which result",
    "demonstrate",
    "demonstrates",
    "which example",
    "best illustrates",
    "calculate",
    "which action",
    "best course",
    "ماذا يحدث لو",
    "كيف سيتغير",
    "توقع",
    "اي نتيجه",
    "النتيجه الاكثر احتمالا",
    "يطبق",
    "اي مثال",
)


def _is_substantive_application_prompt(prompt: str) -> bool:
    """Reject scenario labels that merely wrap an unchanged recall question.

    Application requires an observable transfer task: predict a consequence,
    choose an outcome/action, use a process or rule under changed conditions,
    or calculate from stated conditions. A prefix such as ``Suppose`` or
    ``Given`` is context only and
    cannot, by itself, upgrade factual recall to application.
    """
    normalized = normalize_question_text(prompt)
    return any(pattern in normalized for pattern in _APPLICATION_TASK_PATTERNS)


def _matches_cognitive_shape(question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    classified = classify_cognitive_skill(question.prompt)
    if blueprint.cognitive_skill == "application":
        # Process vocabulary ("produce", "work", "generate") may win the
        # generic classifier's first-match rules. Inspect the task directly,
        # but never let a bare hypothetical marker bypass the application gate.
        return _is_substantive_application_prompt(question.prompt)
    if blueprint.cognitive_skill == "comparison":
        return classified == "comparison"
    if blueprint.cognitive_skill == "cause_effect":
        return classified == "cause_effect"
    if blueprint.cognitive_skill == "process_order":
        return classified == "process_order"
    if blueprint.cognitive_skill == "analysis":
        return classified == "analysis"
    if blueprint.cognitive_skill == "misconception":
        return question.type == "true-false" or classified == "misconception"
    return True


def normalize_blueprinted_candidate(
    raw: _RawCandidate,
    *,
    index: int,
    blueprints: dict[str, QuestionBlueprint],
    page_count: int,
    included_pages: set[int],
    page_text: dict[int, str],
    vocab: set[str],
) -> CandidateRecord | None:
    """Authoritative backend gates for objective, evidence, and question type."""
    blueprint = blueprints.get(raw.blueprint_id.strip())
    if blueprint is None:
        return None
    question = normalize_candidate(
        raw,
        index=index,
        allowed_types={blueprint.question_type},
        page_count=page_count,
        included_pages=included_pages,
    )
    if question is None or question.type != blueprint.question_type:
        return None
    if not set(question.source_pages).issubset(set(blueprint.pages)):
        return None
    quote = re.sub(r"\s+", " ", raw.source_quote.strip())
    if not quotes_equivalent(quote, blueprint.evidence):
        return None
    if not quote_is_grounded(
        quote,
        pages=question.source_pages,
        page_text=page_text,
        category=blueprint.category,
    ):
        return None

    # The backend—not an LLM assertion—checks that prompt, answer, and
    # explanation resolve to the planned evidence.
    evidence_tokens = content_tokens(blueprint.evidence)
    prompt_tokens = content_tokens(question.prompt)
    explanation_tokens = content_tokens(question.explanation)
    if not (prompt_tokens & (evidence_tokens | content_tokens(blueprint.concept))):
        return None
    if (
        len(explanation_tokens & evidence_tokens) < min(2, len(evidence_tokens))
        or len(explanation_tokens & evidence_tokens) / max(1, len(explanation_tokens)) < 0.45
    ):
        return None
    if not _answer_is_supported(question, blueprint):
        return None
    if not _matches_cognitive_shape(question, blueprint):
        return None

    if question.type == "mcq":
        rationales = tuple(value.strip() for value in raw.distractor_rationales if value.strip())
        if len(rationales) != 3 or any(len(value) < 8 for value in rationales):
            return None
        if distractor_quality_score(question, vocab) < _MIN_DISTRACTORS:
            return None
    else:
        rationales = ()
    if question.type == "fill-blank" and not _meaningful_fill_blank(question, blueprint):
        return None
    if question.type == "true-false" and not _meaningful_true_false(raw, question, blueprint):
        return None
    if blueprint.cognitive_skill == "application":
        # Transfer-task scaffolding may be novel, but the subject matter and
        # asserted condition must still come predominantly from exact evidence.
        substantive = prompt_tokens - {
            "scenario",
            "suppose",
            "predict",
            "given",
            "would",
            "happen",
            "outcome",
            "likely",
            "result",
            "action",
            "course",
            "calculate",
            "demonstrate",
            "example",
            "illustrates",
            "سيناريو",
            "لنفترض",
            "توقع",
            "نتيجه",
            "احتمالا",
            "احسب",
            "مثال",
        }
        unsupported = substantive - evidence_tokens
        if (
            len(substantive & evidence_tokens) / max(1, len(substantive)) < 0.65
            or len(unsupported) > 2
        ):
            return None

    # Difficulty is planned from source/cognitive level, not trusted from prose.
    question = question.model_copy(update={"difficulty": blueprint.difficulty})
    return CandidateRecord(
        question=question,
        blueprint=blueprint,
        source_quote=quote,
        distractor_rationales=rationales,
    )


def _records_are_duplicates(left: CandidateRecord, right: CandidateRecord) -> bool:
    if left.blueprint.objective_key == right.blueprint.objective_key:
        return True
    if (
        normalize_question_text(left.blueprint.concept)
        == normalize_question_text(right.blueprint.concept)
        and normalize_question_text(left.blueprint.knowledge_target)
        == normalize_question_text(right.blueprint.knowledge_target)
    ):
        return True
    if exact_duplicate_key(left.question.prompt) == exact_duplicate_key(right.question.prompt):
        return True
    # Different targets/skills remain legitimate even with shared concept
    # vocabulary.  Collapse only near-identical wording + answer + same skill.
    return (
        left.blueprint.cognitive_skill == right.blueprint.cognitive_skill
        and content_jaccard(left.question.prompt, right.question.prompt) >= 0.84
        and content_jaccard(left.question.correct_answer, right.question.correct_answer) >= 0.70
    )


def _dedupe_scored(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Keep the highest-quality candidate for each objective/prompt duplicate."""
    kept: list[ScoredCandidate] = []
    for candidate in sorted(candidates, key=lambda value: value.score, reverse=True):
        if candidate.objective_key and any(
            existing.objective_key == candidate.objective_key for existing in kept
        ):
            continue
        if candidate.concept and candidate.knowledge_target and any(
            normalize_question_text(existing.concept) == normalize_question_text(candidate.concept)
            and normalize_question_text(existing.knowledge_target)
            == normalize_question_text(candidate.knowledge_target)
            for existing in kept
        ):
            continue
        if any(
            exact_duplicate_key(existing.question.prompt) == exact_duplicate_key(candidate.question.prompt)
            for existing in kept
        ):
            continue
        kept.append(candidate)
    return kept


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
    if not has_educational_content(context.units):
        raise AIUnavailableError("The source contains no educational content to build questions from.")

    cleaned_block = cleaned_source_block(
        context.units, title=source.title, page_count=source.page_count
    )
    planner_prompt = build_content_map_prompt(
        source_block=cleaned_block,
        suggested_concepts=context.concepts,
        max_items=min(36, max(16, count * 2)),
    )
    shared_system_prompt = f"{system_prompt}\n\n{quiz_language_guidance(language)}"
    map_completion = service.complete_structured(
        response_model=_RawContentMap,
        system_prompt=shared_system_prompt,
        user_prompt=planner_prompt,
        temperature=0.1,
        max_tokens=6500,
    )
    context.content_map = normalize_content_map(map_completion.value, context.units)
    if not any(item.primary for item in context.content_map):
        context.content_map = fallback_content_map(context.concepts, context.units)

    context.blueprints = build_question_blueprints(
        context.content_map,
        count=count,
        question_types=question_types,
        difficulty=difficulty,
        seed=seed,
    )
    if not context.blueprints:
        raise AIUnavailableError(
            "The source has readable text, but not enough supported important content for these question types."
        )

    candidate_count = min(36, max(20, len(context.blueprints) * 2, count * 2))
    writer_prompt = build_candidate_prompt(
        source=source,
        concepts=context.concepts,
        count=count,
        candidate_count=candidate_count,
        question_types=question_types,
        difficulty=difficulty,
        kind=kind,
        language=language,
        previous_questions=previous_questions,
        blueprints=context.blueprints,
        content_items=[item for item in context.content_map if item.eligible_for_questions],
    )
    completion = service.complete_structured(
        response_model=_RawQuizPool,
        system_prompt=shared_system_prompt,
        user_prompt=writer_prompt,
        temperature=0.45,
        max_tokens=14000,
    )

    blueprint_by_id = {blueprint.id: blueprint for blueprint in context.blueprints}
    records: list[CandidateRecord] = []
    used_ids: set[str] = set()
    for index, raw in enumerate(completion.value.questions):
        record = normalize_blueprinted_candidate(
            raw,
            index=index,
            blueprints=blueprint_by_id,
            page_count=source.page_count,
            included_pages=context.included_pages,
            page_text=context.page_text,
            vocab=context.vocab,
        )
        if record is None or is_repeat_of_history(record.question, previous_questions):
            continue
        if record.question.id in used_ids:
            record.question = record.question.model_copy(
                update={"id": f"{record.question.id}-{index}"}
            )
        used_ids.add(record.question.id)
        if any(_records_are_duplicates(record, existing) for existing in records):
            # Keep variants until scoring when they share an objective; only
            # exact/near-exact duplicate prose is discarded here.
            if any(
                record.blueprint.objective_key != existing.blueprint.objective_key
                and _records_are_duplicates(record, existing)
                for existing in records
            ):
                continue
        records.append(record)

    scored: list[ScoredCandidate] = []
    for record in records:
        result = score_blueprinted_candidate(
            record.question,
            importance=record.blueprint.importance,
            cognitive_skill=record.blueprint.cognitive_skill,
            evidence=record.blueprint.evidence,
            source_quote=record.source_quote,
            vocab=context.vocab,
            page_text=context.page_text,
            included_pages=context.included_pages,
            requested_difficulty=difficulty,
            history=previous_questions,
        )
        # Hard gates prevent a high score in clarity/difficulty from rescuing a
        # weak or ungrounded objective.
        if (
            result.educational_importance < 0.50
            or result.source_grounding < _MIN_GROUNDING
            or result.clarity < 0.70
            or result.conceptual_understanding < 0.58
            or result.distractor_quality < _MIN_DISTRACTORS
            or result.total < quality_threshold
        ):
            continue
        scored.append(
            ScoredCandidate(
                question=record.question,
                score=result.total,
                concept=record.blueprint.concept,
                skill=record.blueprint.cognitive_skill,
                pattern=classify_pattern(record.question.prompt),
                objective_key=record.blueprint.objective_key,
                blueprint_id=record.blueprint.id,
                category=record.blueprint.category,
                knowledge_target=record.blueprint.knowledge_target,
            )
        )

    scored = _dedupe_scored(scored)
    if not scored:
        raise AIUnavailableError("The provider did not return usable source-grounded quiz questions.")

    rng = random.Random(seed)
    selected = select_diverse(scored, count, rng=rng)
    questions = [randomize_answer_positions(question, rng) for question in selected]
    return QuizGenerationResult(
        questions=questions,
        provider=completion.provider,
        model=completion.model,
        fallback_used=map_completion.fallback_used or completion.fallback_used,
    )
