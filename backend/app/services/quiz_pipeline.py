"""Understanding-first AI quiz generation.

Production flow — the document is understood *before* a question exists:

    PDF text
      -> boilerplate cleaning                     (quiz_boilerplate)
      -> DOCUMENT UNDERSTANDING / semantic study map
                                                  (quiz_understanding)
      -> important concept selection              (educational importance)
      -> knowledge relationships + learning objectives
      -> KNOWLEDGE TARGETS                        (quiz_knowledge_targets)
      -> QUIZ BLUEPRINT                           (quiz_blueprints)
      -> large candidate pool                     (provider prose, or the
                                                   deterministic writer)
      -> validation against the study map         (hard gates below)
      -> semantic deduplication                   (knowledge-target identity)
      -> quality scoring                          (quiz_scoring)
      -> cognitive diversity selection
      -> final quiz

No stage reads sentences, headings, page numbers, or term frequency to decide
*what to ask*.  Those only ever serve as evidence for a concept the study map
already established.  The provider proposes understanding and prose; the
backend decides what survives.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.schemas.ai import AIQuizQuestion
from app.services.ai_documents import AIDocumentSource
from app.services.ai_service import AIServiceError, AIUnavailableError
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
    has_educational_content,
    split_source_units,
)
from app.services.quiz_deterministic import (
    SUPPORTED_SKILLS as DETERMINISTIC_SKILLS,
    deterministic_candidates,
    target_writable_types,
    writable_question_types,
)
from app.services.quiz_grounding import (
    SourceSentence,
    iter_sentences,
    quote_is_grounded,
    quotes_equivalent,
)
from app.services.quiz_knowledge_targets import (
    KnowledgeTarget,
    build_knowledge_targets,
    targets_block,
)
from app.services.quiz_msemax import (
    DETERMINISTIC_ORIGIN,
    MSEMAX_ORIGIN,
    MsemaxConfigurationError,
    MsemaxStats,
    msemax_candidates,
    resolve_backend,
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
from app.services.quiz_understanding import (
    DocumentUnderstanding,
    _RawUnderstanding,
    build_understanding_prompt,
    deterministic_understanding,
    normalize_understanding,
    understanding_block,
)

_DEFAULT_THRESHOLD = 0.68
_MIN_GROUNDING = 0.72
_MIN_DISTRACTORS = 0.55

#: Provider metadata reported when the deterministic writer produced the quiz.
DETERMINISTIC_PROVIDER = "deterministic"
DETERMINISTIC_MODEL = "learnx-study-map-v1"

UNAVAILABLE_MESSAGE = (
    "AI quiz generation is unavailable for this document right now. "
    "LearnX only builds a quiz from concepts it can verify in the source, and it will not "
    "fall back to low-quality questions."
)


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

#: Knowledge types where blanking a single term is a meaningful task.
_FILL_BLANK_TYPES = frozenset({"definition", "principle", "process", "classification"})


@dataclass
class QuizContext:
    """Everything derived from the source before questions are written."""

    units: list[Any] = field(default_factory=list)
    sentences: list[SourceSentence] = field(default_factory=list)
    understanding: DocumentUnderstanding | None = None
    knowledge_targets: list[KnowledgeTarget] = field(default_factory=list)
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


@dataclass(frozen=True)
class QuestionProvenance:
    """Per-question traceability back into the semantic study map."""

    question_id: str
    concept_id: str
    concept: str
    knowledge_target_id: str
    knowledge_target: str
    cognitive_skill: str
    knowledge_type: str
    source_pages: tuple[int, ...]
    quality_score: float
    blueprint_id: str


@dataclass
class RejectionNote:
    """Why one candidate did not reach the final quiz.

    Every drop in the pipeline records one of these. Without them a missing or
    weak question can only be guessed at; with them the exact gate that fired
    is visible, which is what makes the pipeline debuggable rather than
    mysterious.
    """

    stage: str
    blueprint_id: str
    concept_id: str
    cognitive_skill: str
    prompt: str
    reason: str


@dataclass
class QuizGenerationResult:
    questions: list[AIQuizQuestion]
    provider: str
    model: str
    fallback_used: bool
    understanding: DocumentUnderstanding | None = None
    blueprints: list[QuestionBlueprint] = field(default_factory=list)
    knowledge_targets: list[KnowledgeTarget] = field(default_factory=list)
    provenance: list[QuestionProvenance] = field(default_factory=list)
    rejections: list[RejectionNote] = field(default_factory=list)
    #: Per-run MSEMAX counters, or None when MSEMAX did not run. Benchmarks and
    #: diagnostics read candidate survival from here.
    msemax_stats: MsemaxStats | None = None


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
    """Clean the source and prepare the evidence index used by every stage."""
    units = clean_source_units(split_source_units(source.text))
    vocab: set[str] = set()
    for unit in units:
        vocab |= content_tokens(unit.text)
    return QuizContext(
        units=units,
        sentences=iter_sentences(units),
        vocab=vocab,
        page_text={unit.page: unit.text for unit in units},
        included_pages={unit.page for unit in units},
    )


# --------------------------------------------------------------------------- #
# Stage 1: document understanding
# --------------------------------------------------------------------------- #


def build_document_understanding(
    service: Any,
    source: AIDocumentSource,
    context: QuizContext,
    *,
    system_prompt: str,
) -> tuple[DocumentUnderstanding, Any | None]:
    """Understand the document first; fall back to a deterministic study map.

    The provider is asked to comprehend, not to write questions.  Whatever it
    proposes is verified against the cleaned source before it becomes part of
    the study map.  When the provider is unavailable the deterministic reader
    builds the same structure from explanatory sentences only.
    """
    cleaned_block = cleaned_source_block(
        context.units, title=source.title, page_count=source.page_count
    )
    prompt = build_understanding_prompt(source_block=cleaned_block, title=source.title)
    try:
        completion = service.complete_structured(
            response_model=_RawUnderstanding,
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=7000,
        )
    except AIServiceError:
        return deterministic_understanding(context.units, title=source.title), None

    understanding = normalize_understanding(
        completion.value, context.units, title=source.title
    )
    if not understanding.is_usable:
        deterministic = deterministic_understanding(context.units, title=source.title)
        if deterministic.is_usable:
            return deterministic, completion
    return understanding, completion


# --------------------------------------------------------------------------- #
# Stage 2: candidate prompt
# --------------------------------------------------------------------------- #


def build_candidate_prompt(
    *,
    understanding: DocumentUnderstanding,
    blueprints: list[QuestionBlueprint],
    knowledge_targets: list[KnowledgeTarget],
    count: int,
    candidate_count: int,
    kind: str,
    difficulty: str,
    previous_questions: list[str],
) -> str:
    """Writer prompt: only the study map and the blueprint, never raw pages."""
    lines = [
        f"Write exactly {candidate_count} candidate variants for a {kind} quiz; {count} will survive.",
        "The document has ALREADY been understood. Do not re-read raw pages and do not invent topics.",
        "Every question must come from a blueprint below — that is, from a knowledge target,",
        "never from a sentence, heading, page number, or repeated phrase.",
        "",
        "DOCUMENT UNDERSTANDING (semantic study map):",
        understanding_block(understanding),
        "",
        "KNOWLEDGE TARGETS:",
        targets_block(knowledge_targets),
        "",
        "QUIZ BLUEPRINT (write one variant per blueprint before writing a second for any):",
        blueprint_block(blueprints),
        "",
        "HARD RULES:",
        "- Use a blueprint_id exactly as written. Test that blueprint's knowledge target and nothing else.",
        "- Use only the blueprint's verbatim evidence. No outside facts, names, numbers, or examples.",
        "- Copy that evidence verbatim into source_quote and cite only its source pages.",
        "- Match the planned question type, cognitive skill, and difficulty.",
        "- APPLICATION means transfer: require a changed condition, prediction, outcome, or decision. "
        "Prefixing 'Suppose' or 'Given' to a recall question is not application.",
        "- Never ask what the source/document/page says, mentions, or shows; ask about the subject itself.",
        "- Never write a question about copyright, publishers, URLs, ISBNs, headings, formatting, or page furniture.",
        "- Never simply restate a source sentence as a question; test whether the learner understands it.",
        "- MCQ: exactly four unique, parallel options and one matching correct answer. Every distractor must be a "
        "plausible misconception drawn from the same document domain. Provide exactly three distractor_rationales.",
        "- True/false: test a meaningful relationship, mechanism, or distinction. A false statement must alter one "
        "source-resolvable relation and provide false_statement_basis.",
        "- Fill-blank: blank exactly one meaningful technical term that appears verbatim in the evidence.",
        "- Explanations must state why the answer follows from the evidence.",
        "DIFFICULTY RULE: " + _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["mixed"]),
    ]
    if previous_questions:
        lines.extend(["", "PREVIOUS QUESTIONS — do not repeat or paraphrase:"])
        lines.extend(f"- {past}" for past in previous_questions[:30])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Stage 3: normalization and hard gates
# --------------------------------------------------------------------------- #


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
    """Basic public-shape normalization; blueprint gates run afterwards."""
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
    # Every substantive answer token must be present in verified evidence. For
    # Arabic, permit only a close same-script stem, never an extra assertion.
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
    return blueprint.knowledge_type in _FILL_BLANK_TYPES


def _meaningful_true_false(raw: _RawCandidate, question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    prompt_tokens = content_tokens(question.prompt)
    evidence_tokens = content_tokens(blueprint.evidence)
    if len(prompt_tokens) < 4 or question.prompt.rstrip().endswith("?"):
        return False
    if normalize_question_text(question.prompt) == normalize_question_text(blueprint.evidence):
        return False
    correct = normalize_question_text(question.correct_answer)
    # A deliberately false statement swaps in a *different* concept, whose name
    # is by design absent from the evidence. Judging it by raw token overlap
    # would reject exactly the questions that make a quiz un-gameable, so the
    # swapped-in name is excused — while the rest of the claim must still be
    # grounded, and the basis check below proves the original relationship was
    # taken verbatim from the source.
    allowance = 2
    if correct == "false":
        swapped = content_tokens(question.prompt) - content_tokens(
            raw.false_statement_basis
        )
        allowance = max(2, len(swapped))
    unsupported = prompt_tokens - evidence_tokens
    overlap = len(prompt_tokens & evidence_tokens) / max(1, len(prompt_tokens))
    if overlap < (0.45 if correct == "false" else 0.65) or len(unsupported) > allowance:
        return False
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
    "no longer",
    "were unable",
    "ماذا يحدث لو",
    "كيف سيتغير",
    "توقع",
    "اي نتيجه",
    "النتيجه الاكثر احتمالا",
    "يطبق",
    "اي مثال",
)


def _is_substantive_application_prompt(prompt: str) -> bool:
    """Reject scenario labels that merely wrap an unchanged recall question."""
    normalized = normalize_question_text(prompt)
    return any(pattern in normalized for pattern in _APPLICATION_TASK_PATTERNS)


def _matches_cognitive_shape(question: AIQuizQuestion, blueprint: QuestionBlueprint) -> bool:
    """Check the question asks the *kind* of thing the blueprint planned.

    This guards against a writer labelling a recall question as analysis. It
    is deliberately NOT applied to facet-backed targets: there, the document
    itself states the relation (purpose/cause/effect/mechanism/contrast), the
    answer is that stated clause, and the backend has already verified both
    against the source. A keyword classifier second-guessing verified evidence
    only rejects good reasoning questions — for example "What is the direct
    result of X?" classifies as factual_recall on the word "what", even though
    its answer is the source's stated outcome.
    """
    if blueprint.facet_kind:
        return True

    classified = classify_cognitive_skill(question.prompt)
    if blueprint.cognitive_skill == "application":
        return _is_substantive_application_prompt(question.prompt)
    if blueprint.cognitive_skill in {"comparison", "cause_effect", "process_order", "analysis"}:
        return classified == blueprint.cognitive_skill
    if blueprint.cognitive_skill == "classification":
        return classified in {"classification", "comparison", "understanding", "factual_recall"}
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
    """Authoritative backend gates: objective, evidence, shape, and type."""
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
        category=blueprint.knowledge_type,
    ):
        return None

    # The backend—not an LLM assertion—checks that prompt, answer, and
    # explanation resolve to the planned evidence and concept.
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
            "longer",
            "unable",
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

    # Difficulty is planned from the study map, not trusted from prose.
    question = question.model_copy(update={"difficulty": blueprint.difficulty})
    return CandidateRecord(
        question=question,
        blueprint=blueprint,
        source_quote=quote,
        distractor_rationales=rationales,
    )


# --------------------------------------------------------------------------- #
# Stage 4: semantic deduplication
# --------------------------------------------------------------------------- #


def _records_are_duplicates(left: CandidateRecord, right: CandidateRecord) -> bool:
    """Two candidates are duplicates when they test the same knowledge."""
    if left.blueprint.objective_key == right.blueprint.objective_key:
        return True
    if left.blueprint.knowledge_target_id == right.blueprint.knowledge_target_id:
        return True
    if exact_duplicate_key(left.question.prompt) == exact_duplicate_key(right.question.prompt):
        return True
    # The same concept tested by the same cognitive skill is the same target,
    # however differently it is worded.
    if (
        left.blueprint.concept_id == right.blueprint.concept_id
        and left.blueprint.cognitive_skill == right.blueprint.cognitive_skill
    ):
        return True
    return (
        left.blueprint.cognitive_skill == right.blueprint.cognitive_skill
        and content_jaccard(left.question.prompt, right.question.prompt) >= 0.84
        and content_jaccard(left.question.correct_answer, right.question.correct_answer) >= 0.70
    )


def _dedupe_scored(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Keep the highest-quality candidate per knowledge target."""
    kept: list[ScoredCandidate] = []
    for candidate in sorted(candidates, key=lambda value: value.score, reverse=True):
        if candidate.objective_key and any(
            existing.objective_key == candidate.objective_key for existing in kept
        ):
            continue
        if candidate.knowledge_target and any(
            existing.knowledge_target == candidate.knowledge_target for existing in kept
        ):
            continue
        if candidate.concept and any(
            existing.concept == candidate.concept and existing.skill == candidate.skill
            for existing in kept
        ):
            continue
        if any(
            exact_duplicate_key(existing.question.prompt)
            == exact_duplicate_key(candidate.question.prompt)
            for existing in kept
        ):
            continue
        kept.append(candidate)
    return kept


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def _score_and_filter(
    records: list[CandidateRecord],
    *,
    context: QuizContext,
    difficulty: str,
    previous_questions: list[str],
    quality_threshold: float,
    rejections: list[RejectionNote] | None = None,
) -> tuple[list[ScoredCandidate], dict[str, float]]:
    scored: list[ScoredCandidate] = []
    scores: dict[str, float] = {}
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
        # Hard gates prevent a strong clarity/difficulty score from rescuing an
        # unimportant or ungrounded objective. Each gate reports *why* it fired
        # so a weak or missing question can be traced to one decision.
        failed: list[str] = []
        if result.educational_importance < 0.50:
            failed.append(f"importance {result.educational_importance:.2f}<0.50")
        if result.source_grounding < _MIN_GROUNDING:
            failed.append(f"grounding {result.source_grounding:.2f}<{_MIN_GROUNDING}")
        if result.clarity < 0.70:
            failed.append(f"clarity {result.clarity:.2f}<0.70")
        if result.conceptual_understanding < 0.58:
            failed.append(f"conceptual {result.conceptual_understanding:.2f}<0.58")
        if result.distractor_quality < _MIN_DISTRACTORS:
            failed.append(f"distractors {result.distractor_quality:.2f}<{_MIN_DISTRACTORS}")
        if result.total < quality_threshold:
            failed.append(f"total {result.total:.2f}<{quality_threshold:.2f}")
        if failed:
            if rejections is not None:
                rejections.append(
                    RejectionNote(
                        stage="quality_gate",
                        blueprint_id=record.blueprint.id,
                        concept_id=record.blueprint.concept_id,
                        cognitive_skill=record.blueprint.cognitive_skill,
                        prompt=record.question.prompt,
                        reason="; ".join(failed),
                    )
                )
            continue
        scores[record.question.id] = result.total
        scored.append(
            ScoredCandidate(
                question=record.question,
                score=result.total,
                concept=record.blueprint.concept_id,
                skill=record.blueprint.cognitive_skill,
                pattern=classify_pattern(record.question.prompt),
                objective_key=record.blueprint.objective_key,
                blueprint_id=record.blueprint.id,
                category=record.blueprint.knowledge_type,
                knowledge_target=record.blueprint.knowledge_target_id,
            )
        )
    return scored, scores


def _collect_records(
    candidates: list[_RawCandidate],
    *,
    context: QuizContext,
    source: AIDocumentSource,
    blueprint_by_id: dict[str, QuestionBlueprint],
    previous_questions: list[str],
    rejections: list[RejectionNote] | None = None,
) -> list[CandidateRecord]:
    records: list[CandidateRecord] = []
    used_ids: set[str] = set()

    def note(stage: str, raw: _RawCandidate, reason: str) -> None:
        if rejections is None:
            return
        blueprint = blueprint_by_id.get(raw.blueprint_id.strip())
        rejections.append(
            RejectionNote(
                stage=stage,
                blueprint_id=raw.blueprint_id,
                concept_id=blueprint.concept_id if blueprint else "",
                cognitive_skill=blueprint.cognitive_skill if blueprint else "",
                prompt=raw.prompt,
                reason=reason,
            )
        )

    for index, raw in enumerate(candidates):
        record = normalize_blueprinted_candidate(
            raw,
            index=index,
            blueprints=blueprint_by_id,
            page_count=source.page_count,
            included_pages=context.included_pages,
            page_text=context.page_text,
            vocab=context.vocab,
        )
        if record is None:
            note("validation", raw, "failed grounding/shape/type validation")
            continue
        if is_repeat_of_history(record.question, previous_questions):
            note("history", raw, "repeats a previously asked question")
            continue
        if record.question.id in used_ids:
            record.question = record.question.model_copy(
                update={"id": f"{record.question.id}-{index}"}
            )
        used_ids.add(record.question.id)
        # Variants that share an objective are kept until scoring; only
        # near-identical prose from a *different* objective is dropped here.
        if any(
            record.blueprint.objective_key != existing.blueprint.objective_key
            and _records_are_duplicates(record, existing)
            for existing in records
        ):
            note("near_duplicate", raw, "near-identical prose to another objective")
            continue
        records.append(record)
    return records


def generate_quiz(
    service: Any,
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
    msemax_enabled: bool | None = None,
    msemax_phrasings: dict[str, dict[str, Any]] | None = None,
    msemax_replayed_rejections: list[Any] | None = None,
    msemax_replayed_stats: Any | None = None,
) -> QuizGenerationResult:
    """Understand the document, plan the quiz, then write and validate it.

    ``msemax_phrasings`` supplies already-generated MSEMAX prose keyed by
    blueprint id. When present the layer replays it instead of calling a
    provider, which is what lets the batched benchmark spread phrasing over
    several short serverless invocations without changing the result.

    ``msemax_enabled`` opts the run into the constrained LLM phrasing layer.
    It defaults to the configured setting; passing it explicitly is what lets
    the A/B harness run both arms against one process without mutating global
    configuration.
    """
    context = build_quiz_context(source)
    if not has_educational_content(context.units):
        raise AIUnavailableError(
            "The source contains no educational content to build questions from."
        )

    shared_system_prompt = f"{system_prompt}\n\n{quiz_language_guidance(language)}"

    # --- Stage 1: DOCUMENT UNDERSTANDING (before any question exists) ------ #
    understanding, map_completion = build_document_understanding(
        service, source, context, system_prompt=shared_system_prompt
    )
    context.understanding = understanding
    if not understanding.is_usable:
        raise AIUnavailableError(
            "The document does not contain enough explained content to build a meaningful quiz."
        )

    # --- Stage 2: knowledge targets and the quiz blueprint ----------------- #
    context.knowledge_targets = build_knowledge_targets(understanding)
    context.blueprints = build_question_blueprints(
        context.knowledge_targets,
        count=count,
        question_types=question_types,
        difficulty=difficulty,
        seed=seed,
    )
    if not context.blueprints:
        raise AIUnavailableError(
            "The source has readable text, but not enough supported important content "
            "for these question types."
        )

    # --- Stage 3: candidate pool ------------------------------------------- #
    candidate_count = min(36, max(20, len(context.blueprints) * 2, count * 2))
    writer_prompt = build_candidate_prompt(
        understanding=understanding,
        blueprints=context.blueprints,
        knowledge_targets=context.knowledge_targets,
        count=count,
        candidate_count=candidate_count,
        kind=kind,
        difficulty=difficulty,
        previous_questions=previous_questions,
    )
    completion = None
    raw_candidates: list[_RawCandidate] = []
    try:
        completion = service.complete_structured(
            response_model=_RawQuizPool,
            system_prompt=shared_system_prompt,
            user_prompt=writer_prompt,
            temperature=0.45,
            max_tokens=14000,
        )
        raw_candidates = list(completion.value.questions)
    except AIServiceError:
        completion = None

    blueprint_by_id = {blueprint.id: blueprint for blueprint in context.blueprints}
    rejections: list[RejectionNote] = []
    #: Set only when the MSEMAX layer actually runs, so a None here means
    #: "MSEMAX did not participate" rather than "MSEMAX produced nothing".
    msemax_stats: MsemaxStats | None = None
    records = _collect_records(
        raw_candidates,
        context=context,
        source=source,
        blueprint_by_id=blueprint_by_id,
        previous_questions=previous_questions,
        rejections=rejections,
    )
    scored, scores = _score_and_filter(
        records,
        context=context,
        difficulty=difficulty,
        previous_questions=previous_questions,
        quality_threshold=quality_threshold,
        rejections=rejections,
    )

    used_deterministic = False
    if completion is None or len(_dedupe_scored(scored)) < count:
        # The provider is unavailable or produced too little. Rather than
        # silently degrading to sentence transformation, run the deterministic
        # writer over the SAME study map and the SAME gates. It plans its own
        # slots, restricted to the cognitive skills it can express honestly, so
        # it never has to fake a transfer scenario. If it cannot clear the gates
        # either, the caller gets a controlled unavailable state.
        # Concepts the surviving candidates already cover. The supplement is
        # planned over the *remaining* concepts first, so a concept whose
        # planned target the writer could not express (an application scenario,
        # say) is recovered through a different target rather than dropped from
        # the quiz entirely. Without this, breadth planned upstream is silently
        # lost at the writing stage.
        covered = {
            blueprint_by_id[candidate.blueprint_id].concept_id
            for candidate in _dedupe_scored(scored)
            if candidate.blueprint_id in blueprint_by_id
        }
        uncovered_targets = [
            target
            for target in context.knowledge_targets
            if target.concept_id not in covered
        ]
        supplement_targets = uncovered_targets or context.knowledge_targets
        deterministic_blueprints = build_question_blueprints(
            supplement_targets,
            count=count,
            question_types=writable_question_types(question_types, understanding),
            difficulty=difficulty,
            seed=seed,
            allowed_skills=DETERMINISTIC_SKILLS,
            # Let the writer veto types it cannot deliver for a given target,
            # so no planned slot is silently lost.
            type_filter=target_writable_types,
        )
        for blueprint in deterministic_blueprints:
            blueprint_by_id.setdefault(blueprint.id, blueprint)
        # Deterministic blueprint ids are re-planned, so give them their own
        # namespace to avoid colliding with the provider's plan.
        renumbered: list[QuestionBlueprint] = []
        for index, blueprint in enumerate(deterministic_blueprints, start=1):
            renamed = replace(blueprint, id=f"det-bp-{index}")
            blueprint_by_id[renamed.id] = renamed
            renumbered.append(renamed)
        deterministic_raw = deterministic_candidates(
            renumbered, language=language, understanding=understanding
        )
        for item in deterministic_raw:
            # Honest provenance: label the writer before any MSEMAX prose can
            # replace it, so deterministic text is never reported as model
            # output.
            item.setdefault("origin", DETERMINISTIC_ORIGIN)

        # --- Stage 3b: MSEMAX (optional constrained LLM phrasing) ---------- #
        # The planner has already fixed the concept, skill, evidence, facet,
        # question type and difficulty. MSEMAX only rewrites the natural
        # language for those same blueprints, and only where it succeeds: a
        # blueprint it declines keeps its deterministic candidate, so turning
        # MSEMAX on can never reduce coverage.
        use_msemax = (
            get_settings().msemax_enabled if msemax_enabled is None else msemax_enabled
        )
        if use_msemax and renumbered:
            if msemax_phrasings is not None:
                # Replay mode: phrasing already happened (across earlier
                # requests) and is supplied here, so this pass makes NO
                # provider call. Used by the batched benchmark, where a single
                # serverless invocation is too short to phrase a whole quiz.
                # The prose is byte-identical to what a one-shot run would use,
                # so the methodology is unchanged.
                phrased = dict(msemax_phrasings)
                msemax_rejections = list(msemax_replayed_rejections or [])
                msemax_stats = msemax_replayed_stats
            else:
                backend = resolve_backend(get_settings(), service)
                msemax_stats = MsemaxStats()
                phrased, msemax_rejections = msemax_candidates(
                    renumbered, backend=backend, stats=msemax_stats
                )
            for rejection in msemax_rejections:
                # Every declined generation is recorded. MSEMAX must never lose
                # a candidate quietly.
                rejections.append(
                    RejectionNote(
                        stage="msemax_generation",
                        blueprint_id=rejection.blueprint_id,
                        concept_id=rejection.concept_id,
                        cognitive_skill=rejection.cognitive_skill,
                        prompt=rejection.prompt,
                        reason=rejection.reason,
                    )
                )
            if phrased:
                deterministic_raw = [
                    phrased.get(item.get("blueprint_id", ""), item)
                    for item in deterministic_raw
                ]

        extra_records = _collect_records(
            [_RawCandidate.model_validate(item) for item in deterministic_raw],
            context=context,
            source=source,
            blueprint_by_id=blueprint_by_id,
            previous_questions=previous_questions,
            rejections=rejections,
        )
        extra_scored, extra_scores = _score_and_filter(
            extra_records,
            context=context,
            difficulty=difficulty,
            previous_questions=previous_questions,
            rejections=rejections,
            quality_threshold=quality_threshold,
        )
        if extra_scored:
            existing_objectives = {candidate.objective_key for candidate in scored}
            added = [
                candidate
                for candidate in extra_scored
                if candidate.objective_key not in existing_objectives
            ]
            if added:
                used_deterministic = completion is None or not scored
                scored.extend(added)
                scores.update(extra_scores)
                context.blueprints = [*context.blueprints, *renumbered]

    scored = _dedupe_scored(scored)
    if not scored:
        raise AIUnavailableError(UNAVAILABLE_MESSAGE)

    rng = random.Random(seed)
    selected = select_diverse(scored, count, rng=rng)
    chosen_ids = {question.id for question in selected}
    for candidate in scored:
        if candidate.question.id not in chosen_ids:
            rejections.append(
                RejectionNote(
                    stage="diversity_selection",
                    blueprint_id=candidate.blueprint_id,
                    concept_id=candidate.concept,
                    cognitive_skill=candidate.skill,
                    prompt=candidate.question.prompt,
                    reason=(
                        f"valid (score {candidate.score:.2f}) but not selected: "
                        "concept/skill already covered or quiz full"
                    ),
                )
            )
    by_id = {candidate.question.id: candidate for candidate in scored}
    blueprint_lookup = {blueprint.id: blueprint for blueprint in context.blueprints}

    provenance: list[QuestionProvenance] = []
    questions: list[AIQuizQuestion] = []
    for question in selected:
        candidate = by_id.get(question.id)
        blueprint = blueprint_lookup.get(candidate.blueprint_id) if candidate else None
        questions.append(randomize_answer_positions(question, rng))
        if blueprint is not None:
            provenance.append(
                QuestionProvenance(
                    question_id=question.id,
                    concept_id=blueprint.concept_id,
                    concept=blueprint.concept,
                    knowledge_target_id=blueprint.knowledge_target_id,
                    knowledge_target=blueprint.knowledge_target,
                    cognitive_skill=blueprint.cognitive_skill,
                    knowledge_type=blueprint.knowledge_type,
                    source_pages=tuple(question.source_pages),
                    quality_score=scores.get(question.id, 0.0),
                    blueprint_id=blueprint.id,
                )
            )

    if completion is not None and not used_deterministic:
        provider = completion.provider
        model = completion.model
        fallback_used = bool(
            (map_completion.fallback_used if map_completion is not None else True)
            or completion.fallback_used
        )
    else:
        provider = DETERMINISTIC_PROVIDER
        model = DETERMINISTIC_MODEL
        fallback_used = True

    return QuizGenerationResult(
        questions=questions,
        provider=provider,
        model=model,
        fallback_used=fallback_used,
        understanding=understanding,
        blueprints=context.blueprints,
        knowledge_targets=context.knowledge_targets,
        provenance=provenance,
        rejections=rejections,
        msemax_stats=msemax_stats,
    )
