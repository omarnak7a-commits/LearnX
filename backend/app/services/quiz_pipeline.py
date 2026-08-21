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

import logging
import random
import re
from collections import Counter
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
#: Provenance label for questions written by the deterministic engine. Kept so
#: generated text is always attributable to its writer.
DETERMINISTIC_ORIGIN = "deterministic"
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
    select_quiz_questions,
)
from app.services.quiz_understanding import (
    DocumentUnderstanding,
    _RawUnderstanding,
    build_understanding_prompt,
    deterministic_understanding,
    normalize_understanding,
    understanding_block,
)

logger = logging.getLogger(__name__)

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
    #: Pages the candidate's evidence came from, for diagnostics.
    evidence_pages: tuple[int, ...] = ()
    #: Quality score, where the candidate got far enough to be scored.
    grounding_score: float | None = None
    #: The distinction that matters when a quiz comes back short:
    #:
    #:  ``unsupported_by_pdf``      -- the document genuinely does not back
    #:                                 this question; rejecting it is correct.
    #:  ``validator_false_negative``-- the question is derived from the
    #:                                 document but a validator rule could not
    #:                                 see it. These are bugs, and the count
    #:                                 of them is what tells us whether a
    #:                                 shortfall is honest.
    #:  ``not_selected``            -- valid, but the quiz had no room.
    grounding_result: str = "unsupported_by_pdf"

    @property
    def question_id(self) -> str:
        """Stable identifier for this rejection, for structured diagnostics."""
        return self.blueprint_id or "-"


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
    #: Redundancy preferences that had to be relaxed to fill the quiz.
    relaxed_gates: tuple[str, ...] = ()
    #: Stage-by-stage funnel, emitted to the log and kept for tests.
    telemetry: dict[str, Any] = field(default_factory=dict)


class QuizContentError(AIUnavailableError):
    """The material provided cannot support a quiz.

    Separate from a provider outage. Both used to surface as "AI is
    temporarily unavailable, please try again shortly", which is wrong twice
    over: retrying will not help, and it hides that the request may simply
    have been scoped to a title page. Subclasses AIUnavailableError so every
    existing handler keeps working.
    """


class QuizMaterialError(AIUnavailableError):
    """The source is real and readable but cannot support the requested count.

    Distinct from :class:`AIUnavailableError` so the API can explain that the
    *document* is the limit -- returning a short quiz silently would hide that
    from the student, and inventing the difference would break grounding.
    """

    def __init__(
        self,
        message: str,
        *,
        requested: int,
        available: int,
        telemetry: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.requested = requested
        self.available = available
        #: The funnel as it stood when the shortfall was declared. Carried on
        #: the exception because this is precisely the case where diagnostics
        #: are needed most, and the 422 path previously discarded them --
        #: leaving "could only verify 1" with nothing to explain it.
        self.telemetry = telemetry or {}


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
    trace: dict[str, Any] | None = None,
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
    if trace is not None:
        trace["understanding_calls"] = trace.get("understanding_calls", 0) + 1
    try:
        completion = service.complete_structured(
            response_model=_RawUnderstanding,
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=7000,
        )
    except AIServiceError:
        if trace is not None:
            trace["understanding_failed"] = 1
        return deterministic_understanding(context.units, title=source.title), None

    if trace is not None:
        trace["understanding_ok"] = 1

    drops: dict[str, Any] = {}
    understanding = normalize_understanding(
        completion.value, context.units, title=source.title, drops=drops
    )
    if trace is not None:
        trace["concept_drops"] = drops
    if not understanding.is_usable:
        # The provider answered, but nothing it proposed survived verification.
        # Falling back silently here is what makes a discarded study map
        # indistinguishable from a thin document, so record it.
        deterministic = deterministic_understanding(context.units, title=source.title)
        if trace is not None:
            trace["provider_map_discarded"] = 1
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


#: Linking verbs a paraphrase may add without asserting anything new. Each one
#: needs a subject and an object to carry meaning, and both of those must still
#: come from the document, so none of these can smuggle in an outside fact.
#: Deliberately closed and tiny -- it is a fix for connective grammar, not a
#: general tolerance for unsupported content.
_PARAPHRASE_CONNECTIVES = frozenset(
    {
        "needs",
        "need",
        "needed",
        "helps",
        "help",
        "allows",
        "allow",
        "makes",
        "make",
        "lets",
        "gives",
        "provides",
        "keeps",
        "takes",
        "happens",
        "occurs",
        "means",
    }
)


def _answer_is_supported(
    question: AIQuizQuestion,
    blueprint: QuestionBlueprint,
    *,
    document_vocab: set[str] | None = None,
) -> bool:
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
    # An answer may legitimately be phrased in the document's own words without
    # copying one sentence: naming the concept the evidence is *about*, or
    # linking it to a neighbouring concept the document also defines. Requiring
    # every token to sit inside the single planned quote rejected exactly those
    # paraphrases -- "it absorbs the light energy that photosynthesis needs" was
    # refused because "photosynthesis" appears on the page but not in the
    # chlorophyll sentence.
    #
    # So the token must come from somewhere the document actually says: the
    # planned evidence, the concept being tested, or (when the caller supplies
    # it) the document's own vocabulary. That is still a closed world -- an
    # outside fact such as a wavelength in nanometres has no source anywhere in
    # the text and is still refused.
    supported_tokens = set(evidence_tokens)
    supported_tokens |= content_tokens(blueprint.concept)
    supported_tokens |= content_tokens(blueprint.knowledge_target)
    if document_vocab:
        supported_tokens |= document_vocab
    unsupported = answer_tokens - supported_tokens
    # A paraphrase carries connective words the source never used ("needs",
    # "helps", "allows") purely to make the sentence read naturally. Demanding
    # zero such tokens is the literal matching that produced false rejections.
    #
    # Allowing *any* single stray token was too blunt: it also admitted answers
    # that tack a contrast clause about a different subject onto the end. So
    # the residue is restricted to a closed list of linking verbs, which cannot
    # by themselves introduce a fact -- they need a subject and an object, and
    # those must still come from the document.
    if unsupported and unsupported <= _PARAPHRASE_CONNECTIVES:
        unsupported = set()
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


#: Gate reasons that mean "the document does not back this", as opposed to
#: "a validator rule could not recognise a legitimate transformation".
#: Everything the writer produces is built *from* a planned knowledge target,
#: so a shape/quality veto is a validator limitation, not missing material.
_UNSUPPORTED_MARKERS = (
    "not part of this quiz plan",
    "outside the concept's",
    "does not match the planned evidence",
    "not verbatim in the cited page text",
    "shares no content",
    "not supported by the cited evidence",
    "is not supported by the evidence",
)


def classify_grounding_result(reason: str) -> str:
    """Separate genuine lack of support from a validator false negative.

    A short quiz is only honest when the rejections were genuine. Counting
    these separately is what makes that checkable instead of assumed.
    """
    lowered = reason.casefold()
    for marker in _UNSUPPORTED_MARKERS:
        if marker in lowered:
            return "unsupported_by_pdf"
    return "validator_false_negative"


def _note(reasons: list[str] | None, reason: str) -> None:
    """Record why a gate rejected a candidate, when the caller is collecting."""
    if reasons is not None:
        reasons.append(reason)


def normalize_blueprinted_candidate(
    raw: _RawCandidate,
    *,
    index: int,
    blueprints: dict[str, QuestionBlueprint],
    page_count: int,
    included_pages: set[int],
    page_text: dict[int, str],
    vocab: set[str],
    reasons: list[str] | None = None,
) -> CandidateRecord | None:
    """Authoritative backend gates: objective, evidence, shape, and type.

    ``reasons`` optionally collects the specific gate that rejected the
    candidate. Every gate here returns None, so without it a rejected question
    is only ever reported as "failed validation" -- which is exactly the kind
    of unexplained drop that made a short quiz impossible to debug.
    """
    blueprint = blueprints.get(raw.blueprint_id.strip())
    if blueprint is None:
        _note(reasons, f"blueprint {raw.blueprint_id.strip()!r} is not part of this quiz plan")
        return None
    question = normalize_candidate(
        raw,
        index=index,
        allowed_types={blueprint.question_type},
        page_count=page_count,
        included_pages=included_pages,
    )
    if question is None:
        _note(reasons, "malformed question (shape, options, or page refs invalid)")
        return None
    if question.type != blueprint.question_type:
        _note(
            reasons,
            f"type {question.type!r} does not match the planned {blueprint.question_type!r}",
        )
        return None
    if not set(question.source_pages).issubset(set(blueprint.pages)):
        _note(
            reasons,
            f"cites pages {list(question.source_pages)} outside the concept's "
            f"evidence pages {list(blueprint.pages)}",
        )
        return None
    quote = re.sub(r"\s+", " ", raw.source_quote.strip())
    if not quotes_equivalent(quote, blueprint.evidence):
        _note(reasons, "source quote does not match the planned evidence")
        return None
    if not quote_is_grounded(
        quote,
        pages=question.source_pages,
        page_text=page_text,
        category=blueprint.knowledge_type,
    ):
        _note(reasons, "source quote is not verbatim in the cited page text")
        return None

    # The backend—not an LLM assertion—checks that prompt, answer, and
    # explanation resolve to the planned evidence and concept.
    evidence_tokens = content_tokens(blueprint.evidence)
    prompt_tokens = content_tokens(question.prompt)
    explanation_tokens = content_tokens(question.explanation)
    if not (prompt_tokens & (evidence_tokens | content_tokens(blueprint.concept))):
        _note(reasons, "question text shares no content with the concept or its evidence")
        return None
    if (
        len(explanation_tokens & evidence_tokens) < min(2, len(evidence_tokens))
        or len(explanation_tokens & evidence_tokens) / max(1, len(explanation_tokens)) < 0.45
    ):
        _note(reasons, "explanation is not supported by the cited evidence")
        return None
    if not _answer_is_supported(question, blueprint, document_vocab=vocab):
        _note(reasons, "correct answer is not supported by the evidence")
        return None
    if not _matches_cognitive_shape(question, blueprint):
        _note(
            reasons,
            f"question does not have the shape of a {blueprint.cognitive_skill!r} question",
        )
        return None

    if question.type == "mcq":
        rationales = tuple(value.strip() for value in raw.distractor_rationales if value.strip())
        if len(rationales) != 3 or any(len(value) < 8 for value in rationales):
            _note(reasons, "MCQ is missing usable rationales for all three distractors")
            return None
        if distractor_quality_score(question, vocab) < _MIN_DISTRACTORS:
            _note(reasons, "MCQ distractors are too weak to be plausible")
            return None
    else:
        rationales = ()
    if question.type == "fill-blank" and not _meaningful_fill_blank(question, blueprint):
        _note(reasons, "fill-blank does not remove a meaningful term")
        return None
    if question.type == "true-false" and not _meaningful_true_false(raw, question, blueprint):
        _note(reasons, "true/false statement is not a checkable claim from the evidence")
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
                        evidence_pages=tuple(record.blueprint.pages),
                        grounding_score=result.total,
                        # It cleared grounding and was scored, so the document
                        # does support it; it simply scored too low.
                        grounding_result="validator_false_negative",
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
                evidence_pages=tuple(blueprint.pages) if blueprint else (),
                grounding_result=classify_grounding_result(reason),
            )
        )

    for index, raw in enumerate(candidates):
        gate_reasons: list[str] = []
        record = normalize_blueprinted_candidate(
            raw,
            index=index,
            blueprints=blueprint_by_id,
            page_count=source.page_count,
            included_pages=context.included_pages,
            page_text=context.page_text,
            vocab=context.vocab,
            reasons=gate_reasons,
        )
        if record is None:
            note(
                "validation",
                raw,
                gate_reasons[0] if gate_reasons else "failed grounding/shape/type validation",
            )
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


#: Question types whose answer must be one of the offered options.
_OPTION_TYPES = {"mcq", "true-false"}

#: How many extra planning rounds may run when the pool is short of the
#: requested count. Bounded so a thin document fails fast instead of looping.
_MAX_TOPUP_ROUNDS = 3


def _insufficient_material_message(
    requested: int, available: int, telemetry: dict[str, Any] | None = None
) -> str:
    """Explain a shortfall, and only blame the PDF when the PDF is to blame.

    Requirement: "this PDF does not contain enough material" must be reserved
    for a proven content shortage. When the shortfall is better explained by
    something the pipeline did -- pages that were extracted and then discarded
    during cleaning, scanned pages whose text was never recovered, or a
    provider that failed -- say that instead. Telling a student their textbook
    is empty when the extractor dropped half of it is both wrong and
    unactionable.
    """
    telemetry = telemetry or {}
    dropped = telemetry.get("pages_dropped_in_cleaning", 0)
    image_only = telemetry.get("image_only_pages", 0)
    provider_errors = telemetry.get("provider_errors", 0)

    # A provider outage only *explains* a shortfall when nothing else covered
    # it. The deterministic writer is a designed fallback, not a failure: while
    # it is still producing grounded questions, an unavailable provider is not
    # what limited the quiz, and saying so would mislead in the other
    # direction.
    if provider_errors and available == 0:
        return (
            f"LearnX could only build {available} of {requested} questions "
            "because the AI provider failed part-way through. This is a "
            "service problem, not a problem with your PDF -- please retry."
        )
    if dropped:
        return (
            f"LearnX could only verify {available} of {requested} questions. "
            f"{dropped} page(s) of this PDF were read but could not be used, "
            "which usually means repeated slide furniture or unusual layout "
            "rather than missing content. Try asking for fewer questions."
        )
    if image_only:
        return (
            f"LearnX could only verify {available} of {requested} questions. "
            f"{image_only} page(s) are images or scans with no extractable "
            "text, so their content could not be read. A text-based PDF, or a "
            f"request for {available} questions, will work better."
        )
    return (
        f"This PDF does not contain enough clearly explained material for "
        f"{requested} well-grounded questions -- LearnX could only verify "
        f"{available}. Try asking for {available} questions instead. "
        f"LearnX will not invent questions the document does not support."
    )


def _top_up_candidates(
    scored: list[ScoredCandidate],
    scores: dict[str, float],
    *,
    context: QuizContext,
    source: AIDocumentSource,
    understanding: DocumentUnderstanding,
    blueprint_by_id: dict[str, QuestionBlueprint],
    count: int,
    question_types: list[str],
    difficulty: str,
    language: str,
    seed: int,
    previous_questions: list[str],
    quality_threshold: float,
    rejections: list[RejectionNote],
) -> tuple[list[ScoredCandidate], dict[str, float]]:
    """Plan and write additional questions until the pool can fill the quiz.

    A question that fails validation must not shrink the quiz; it must be
    replaced. Each round re-plans over the knowledge targets whose concepts are
    still uncovered (falling back to all targets once every concept has one
    question), asks the deterministic writer for that material, and puts the
    results through the identical grounding and scoring gates. Nothing here
    weakens a gate -- the only thing that changes is how much material has been
    attempted.
    """
    important = {
        concept.concept_id for concept in understanding.important_concepts()
    }
    # Objectives already written and rejected. Re-planning one produces the
    # same question and the same rejection, wasting a bounded retry round.
    attempted_objectives: set[str] = set()
    for round_index in range(_MAX_TOPUP_ROUNDS):
        covered = {
            blueprint_by_id[candidate.blueprint_id].concept_id
            for candidate in scored
            if candidate.blueprint_id in blueprint_by_id
        }
        uncovered = [
            target
            for target in context.knowledge_targets
            if target.concept_id not in covered
        ]
        # Two reasons to plan more material. The obvious one is a pool too
        # small to fill the quiz. The subtler one is a pool that is big enough
        # but does not reach every important concept: selection then has to
        # choose between leaving a concept unexamined and repeating one it
        # already used. Widening the pool first means it rarely has to.
        missing_concepts = [
            target for target in uncovered if target.concept_id in important
        ]
        if len(scored) >= count and not missing_concepts:
            break
        # Plan over uncovered concepts *first* but never only over them. Once
        # every concept has one question, `uncovered` is empty -- and planning
        # over an empty set re-proposed the objectives already in the pool, so
        # the top-up added nothing and a 12-question request failed on a
        # document that could support far more. Keeping the full target list as
        # a tail lets later rounds plan a *second, different* knowledge target
        # for an already-covered concept, which is new material rather than a
        # repeat.
        seen_target_ids = {target.target_id for target in missing_concepts}
        targets = [
            *missing_concepts,
            *(
                target
                for target in context.knowledge_targets
                if target.target_id not in seen_target_ids
            ),
        ]
        if not targets:
            break
        # Ask for more than the shortfall: some plans will not survive the
        # writer or the gates, and an exhausted pool is what caused the
        # shortfall in the first place.
        #
        # `count`, not the shortfall, is what the planner is told. The planner
        # relaxes its own quality preferences once it cannot reach the count it
        # was given, so asking it for "2 more" made a tiny request that it
        # satisfied by relaxing straight into tier-3 recall -- weak questions
        # entered quizzes that were not even short. Asking for the full quiz
        # size keeps the strict pass in charge; `exclude_objectives` is what
        # actually makes the round return *new* material.
        wanted = max(count, len(missing_concepts) + 4)
        planned = build_question_blueprints(
            targets,
            count=wanted,
            question_types=writable_question_types(question_types, understanding),
            difficulty=difficulty,
            # A different seed per round explores different valid material
            # instead of re-planning the identical slots we already have.
            seed=seed + 7919 * (round_index + 1),
            allowed_skills=DETERMINISTIC_SKILLS,
            type_filter=target_writable_types,
            # Never re-plan an objective the pool already holds. Without this
            # the top-up spent every round rewriting questions it already had,
            # all of which were then dropped as duplicates -- so the quiz
            # stayed short while untouched knowledge targets went unused.
            # Exclude what the pool already holds AND what earlier rounds
            # already tried and lost: regenerating a candidate that has
            # already failed the gates burns a round and produces the
            # identical rejection.
            exclude_objectives={
                candidate.objective_key for candidate in scored
            }
            | attempted_objectives,
            # Only a genuinely short quiz may relax the quality preferences.
            # When this round is merely widening an already-sufficient pool for
            # coverage, relaxing would plan bare-recall slots that then compete
            # with the strong questions already selected.
            allow_relaxation=len(scored) < count,
        )
        if not planned:
            break
        renumbered: list[QuestionBlueprint] = []
        for index, blueprint in enumerate(planned, start=1):
            renamed = replace(blueprint, id=f"topup{round_index + 1}-bp-{index}")
            blueprint_by_id[renamed.id] = renamed
            renumbered.append(renamed)

        raw = deterministic_candidates(
            renumbered, language=language, understanding=understanding
        )
        for item in raw:
            item.setdefault("origin", DETERMINISTIC_ORIGIN)
        records = _collect_records(
            [_RawCandidate.model_validate(item) for item in raw],
            context=context,
            source=source,
            blueprint_by_id=blueprint_by_id,
            previous_questions=previous_questions,
            rejections=rejections,
        )
        extra, extra_scores = _score_and_filter(
            records,
            context=context,
            difficulty=difficulty,
            previous_questions=previous_questions,
            quality_threshold=quality_threshold,
            rejections=rejections,
        )
        for blueprint in renumbered:
            attempted_objectives.add(blueprint.objective_key)
        existing = {candidate.objective_key for candidate in scored}
        added = [
            candidate
            for candidate in extra
            if candidate.objective_key not in existing
        ]
        if not added:
            # Another round would re-plan the same exhausted material.
            break
        scored = _dedupe_scored([*scored, *added])
        scores.update(extra_scores)
        context.blueprints = [*context.blueprints, *renumbered]
    return scored, scores


def _quiz_telemetry(
    *,
    source: AIDocumentSource,
    context: QuizContext,
    understanding: DocumentUnderstanding,
    blueprints: list[QuestionBlueprint],
    requested: int,
    generated: int,
    validated: int,
    rejections: list[RejectionNote],
    relaxed_gates: tuple[str, ...],
    candidates_generated: int = 0,
    provider_errors: int = 0,
    provider_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The stage-by-stage funnel, as data so tests can assert on it."""
    pages_used = sorted(context.included_pages)
    # Selection leftovers are valid questions the quiz had no room for; they
    # are not failures and would make the rejected count misleading.
    real_rejections = [
        note for note in rejections if note.stage != "diversity_selection"
    ]
    return {
        # Report the pages we can actually build from. For a PDF this is the
        # extracted (and possibly reading-restricted) set; source.page_count
        # is only meaningful for real PDFs and reads 1 for pasted text.
        "pdf_pages_available": max(source.page_count, len(pages_used)),
        "pages_used": pages_used,
        "extracted_text": "available" if context.units else "missing",
        "concepts_found": len(list(understanding.important_concepts())),
        # Every concept the study map holds, and every verbatim span behind
        # them. A quiz that comes back short is only explainable next to these.
        "concepts_total": len(understanding.concepts),
        "evidence_items": sum(
            len(concept.evidence) for concept in understanding.concepts
        ),
        "relationships": len(understanding.relationships),
        # Extraction quality, so a shortfall can be attributed to the file
        # (scanned pages) rather than to the pipeline.
        "text_pages": sum(1 for page in source.pages if page.text_available),
        "image_only_pages": sum(
            1 for page in source.pages
            if not page.text_available and page.image_available
        ),
        "pages_dropped_in_cleaning": max(
            0,
            sum(1 for page in source.pages if page.text_available)
            - len(context.included_pages),
        ),
        "page_quality": [
            f"page {page.page}: text {page.text_length} chars"
            + (", image available" if page.image_available else "")
            for page in source.pages[:40]
        ],
        "candidates_generated": candidates_generated,
        "quiz_requested": requested,
        "quiz_plans_created": len(blueprints),
        "questions_generated": generated,
        "questions_validated": validated,
        "questions_rejected": len(real_rejections),
        "rejected_unsupported_by_pdf": sum(
            1 for note in real_rejections
            if note.grounding_result == "unsupported_by_pdf"
        ),
        # The number that matters when a quiz is short: questions the document
        # *does* support but a validator rule could not recognise.
        "rejected_validator_false_negative": sum(
            1 for note in real_rejections
            if note.grounding_result == "validator_false_negative"
        ),
        "relaxed_gates": list(relaxed_gates),
        "provider_errors": provider_errors,
        "rejections_by_stage": dict(
            Counter(note.stage for note in real_rejections)
        ),
        # Provider-call outcomes and the concept-filter funnel. Needed to tell
        # "the document is thin" apart from "the provider answered and we threw
        # the answer away".
        "provider_trace": dict(provider_trace or {}),
        "concepts_proposed_by_provider": (provider_trace or {}).get(
            "concept_drops", {}
        ).get("proposed", 0),
        "concepts_dropped_in_filtering": dict(
            (provider_trace or {}).get("concept_drops", {}).get("reasons", {})
        ),
        "understanding_source": getattr(understanding, "source", ""),
    }


def _log_quiz_generation(
    telemetry: dict[str, Any], rejections: list[RejectionNote]
) -> None:
    """Emit the funnel and every rejection reason.

    Without this, a short or off-topic quiz can only be guessed at. With it the
    exact stage that dropped each question is in the log.
    """
    pages = telemetry["pages_used"]
    pages_text = ",".join(str(page) for page in pages) if pages else "none"
    logger.info(
        "quiz generation funnel | PDF pages available: %s | Pages used: %s | "
        "Extracted text: %s | Concepts found: %s | Quiz requested: %s | "
        "Quiz plans created: %s | Questions generated: %s | Questions validated: %s | "
        "Questions rejected: %s (unsupported by PDF: %s, validator false negatives: %s)",
        telemetry["pdf_pages_available"],
        pages_text,
        telemetry["extracted_text"],
        telemetry["concepts_found"],
        telemetry["quiz_requested"],
        telemetry["quiz_plans_created"],
        telemetry["questions_generated"],
        telemetry["questions_validated"],
        telemetry["questions_rejected"],
        telemetry["rejected_unsupported_by_pdf"],
        telemetry["rejected_validator_false_negative"],
    )
    if telemetry["relaxed_gates"]:
        logger.info(
            "quiz generation relaxed redundancy gates to fill the quiz: %s",
            ", ".join(telemetry["relaxed_gates"]),
        )
    for note in rejections:
        if note.stage == "diversity_selection":
            continue
        logger.info(
            "quiz question rejected | question_id=%s | concept=%s | "
            "evidence_pages=%s | grounding_result=%s | grounding_score=%s | "
            "stage=%s | skill=%s | rejection_reason=%s | prompt=%s",
            note.question_id,
            note.concept_id or "-",
            list(note.evidence_pages) or "-",
            note.grounding_result,
            f"{note.grounding_score:.2f}" if note.grounding_score is not None else "-",
            note.stage,
            note.cognitive_skill or "-",
            note.reason,
            (note.prompt or "")[:120],
        )


def validate_final_quiz(
    questions: list[AIQuizQuestion],
    *,
    context: QuizContext,
    source: AIDocumentSource,
    understanding: DocumentUnderstanding,
    provenance_by_id: dict[str, QuestionProvenance],
    requested_types: list[str],
) -> tuple[list[AIQuizQuestion], list[RejectionNote]]:
    """Audit the assembled quiz one last time, independently of how it was built.

    Every earlier stage validates a candidate in isolation, at the moment it is
    written. This pass re-checks the finished set as a whole, so a question can
    never reach the student because an intermediate stage forgot to look: the
    concept must exist in the study map, the pages must exist in the source we
    actually extracted, the answer must be answerable from the offered options,
    and the shape must match the question type.

    It is deliberately cheap and purely structural -- it re-verifies decisions
    rather than re-deriving them, so it cannot itself introduce ungrounded
    content.
    """
    concept_ids = {concept.concept_id for concept in understanding.important_concepts()}
    concept_names = {
        normalize_question_text(concept.name)
        for concept in understanding.important_concepts()
        if concept.name
    }
    allowed_types = {_TYPE_ALIASES.get(t.strip().lower(), t.strip().lower()) for t in requested_types}
    valid: list[AIQuizQuestion] = []
    notes: list[RejectionNote] = []

    def reject(question: AIQuizQuestion, reason: str) -> None:
        record = provenance_by_id.get(question.id)
        notes.append(
            RejectionNote(
                stage="final_validation",
                blueprint_id=record.blueprint_id if record else "",
                concept_id=record.concept_id if record else "",
                cognitive_skill=record.cognitive_skill if record else "",
                prompt=question.prompt,
                reason=reason,
                evidence_pages=tuple(question.source_pages),
                grounding_score=record.quality_score if record else None,
                grounding_result=classify_grounding_result(reason),
            )
        )

    for question in questions:
        record = provenance_by_id.get(question.id)
        if record is None:
            reject(question, "no provenance: question is not traceable to a blueprint")
            continue
        # The concept must be one the document understanding actually found.
        if record.concept_id not in concept_ids and (
            normalize_question_text(record.concept) not in concept_names
        ):
            reject(question, f"concept {record.concept_id!r} is not in the document study map")
            continue
        if allowed_types and question.type not in allowed_types:
            reject(question, f"type {question.type!r} was not requested")
            continue
        # Pages must exist in the *extracted* source, not merely in the PDF.
        pages = list(question.source_pages)
        if not pages:
            reject(question, "no source page reference")
            continue
        # The authority on "which pages exist" is the text we actually
        # extracted, not source.page_count: a text-pasted source reports a
        # page_count of 1 while legitimately carrying [Page 2] markers, and a
        # page-restricted request extracts a subset of a longer PDF. Checking
        # the extracted set covers both, and is the stricter test -- it also
        # catches a citation to a real PDF page that was never read.
        not_extracted = [p for p in pages if p < 1 or p not in context.included_pages]
        if not_extracted:
            reject(
                question,
                f"cites page(s) {not_extracted} that are not in the extracted source pages "
                f"{sorted(context.included_pages)}",
            )
            continue
        answer = (question.correct_answer or "").strip()
        if not answer:
            reject(question, "empty correct answer")
            continue
        if question.type in _OPTION_TYPES:
            options = [o.strip() for o in (question.options or []) if o and o.strip()]
            if len(options) < 2:
                reject(question, f"{question.type} needs at least two options")
                continue
            if len(set(normalize_question_text(o) for o in options)) != len(options):
                reject(question, "duplicate options")
                continue
            if normalize_question_text(answer) not in {
                normalize_question_text(o) for o in options
            }:
                reject(question, "correct answer is not among the options")
                continue
        if question.type == "fill-blank" and not is_valid_fill_blank(
            question.prompt, question.correct_answer
        ):
            reject(question, "fill-blank prompt has no usable blank")
            continue
        valid.append(question)

    return valid, notes


def _scope_note(
    source: AIDocumentSource,
    context: QuizContext,
    *,
    requested_pages: list[int] | None = None,
) -> str:
    """Describe how much of the document was actually examined.

    A failure message must distinguish three different situations that used to
    look identical:

    * the caller restricted the request to some pages;
    * the whole document was read, but some pages carried no extractable text
      (a scanned cover, a full-page diagram);
    * the whole document was read and every page contributed.

    The old wording said "only page(s) 2, 3, 4 ... of 32 were used" in the
    second case too, which reads as though the exam had been silently narrowed
    to the pages the student had opened. That sent a user hunting for a
    page-scoping bug when the request had in fact covered the entire PDF.
    """
    used = len(context.included_pages)
    total = max(source.page_count, used)
    if not used or not total or used >= total:
        return ""
    pages = ", ".join(str(page) for page in sorted(context.included_pages)[:8])
    more = "..." if used > 8 else ""
    if requested_pages:
        # A genuine restriction: naming it is the actionable information.
        return f" (only page(s) {pages}{more} of {total} were used)"
    # No restriction was applied. The whole PDF was read; some pages simply had
    # nothing extractable, which is a property of the file, not of the request.
    skipped = total - used
    return (
        f" (the whole {total}-page document was analysed; {skipped} page(s) "
        "had no extractable text, e.g. scanned images or diagrams)"
    )


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
    require_exact_count: bool = True,
    requested_pages: list[int] | None = None,
) -> QuizGenerationResult:
    """Understand the document, plan the quiz, then write and validate it.

    ``require_exact_count`` enforces the product contract: a request for eight
    questions yields eight questions or an explicit :class:`QuizMaterialError`
    naming how many the document could actually support. It is a parameter only
    so unit tests can drive the pipeline with deliberately tiny fixtures while
    probing a different invariant; every caller in the application leaves it on.
    """
    context = build_quiz_context(source)
    # When the request was restricted to a handful of pages, say so. Blaming
    # "the PDF" for having no content is actively misleading if only its title
    # page was ever examined -- that was the reported bug, and the message sent
    # students looking for a fault in a perfectly good document.
    scope_note = _scope_note(source, context, requested_pages=requested_pages)
    if not has_educational_content(context.units):
        raise QuizContentError(
            "No teachable content was found in the material provided"
            f"{scope_note}. Scanned pages may contain only a title, contents "
            "list, or images."
        )

    shared_system_prompt = f"{system_prompt}\n\n{quiz_language_guidance(language)}"

    # --- Stage 1: DOCUMENT UNDERSTANDING (before any question exists) ------ #
    provider_trace: dict[str, Any] = {}
    understanding, map_completion = build_document_understanding(
        service, source, context, system_prompt=shared_system_prompt,
        trace=provider_trace,
    )
    context.understanding = understanding
    if not understanding.is_usable:
        raise QuizContentError(
            "Not enough explained content was found in the material provided"
            f"{scope_note} to build a meaningful quiz."
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
    provider_errors = 0 if map_completion is not None else 1
    provider_trace["writer_calls"] = provider_trace.get("writer_calls", 0) + 1
    try:
        completion = service.complete_structured(
            response_model=_RawQuizPool,
            system_prompt=shared_system_prompt,
            user_prompt=writer_prompt,
            temperature=0.45,
            max_tokens=14000,
        )
        raw_candidates = list(completion.value.questions)
        provider_trace["writer_ok"] = provider_trace.get("writer_ok", 0) + 1
        provider_trace["writer_questions_returned"] = (
            provider_trace.get("writer_questions_returned", 0) + len(raw_candidates)
        )
        if not raw_candidates:
            provider_trace["writer_empty"] = provider_trace.get("writer_empty", 0) + 1
    except AIServiceError:
        completion = None
        # A writer outage is a *service* failure. Recording it keeps the
        # shortfall message from blaming the document for a provider problem.
        provider_errors += 1
        provider_trace["writer_failed"] = provider_trace.get("writer_failed", 0) + 1

    blueprint_by_id = {blueprint.id: blueprint for blueprint in context.blueprints}
    rejections: list[RejectionNote] = []
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
            # Honest provenance: label the writer so deterministic text is
            # never reported as model output.
            item.setdefault("origin", DETERMINISTIC_ORIGIN)

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

    # --- Stage 4: top-up ---------------------------------------------------- #
    # If the surviving pool is smaller than the quiz, plan *more* material from
    # the study map before selecting, rather than discovering the shortfall
    # after selection when nothing can be done about it. This is the retry
    # required for a failed question: the slot is refilled from a different
    # knowledge target for the same document, never by relaxing grounding.
    scored, scores = _top_up_candidates(
        scored,
        scores,
        context=context,
        source=source,
        understanding=understanding,
        blueprint_by_id=blueprint_by_id,
        count=count,
        question_types=question_types,
        difficulty=difficulty,
        language=language,
        seed=seed,
        previous_questions=previous_questions,
        quality_threshold=quality_threshold,
        rejections=rejections,
    )

    rng = random.Random(seed)
    outcome = select_quiz_questions(scored, count, rng=rng)
    selected = outcome.questions
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
                    evidence_pages=tuple(candidate.question.source_pages),
                    grounding_score=candidate.score,
                    grounding_result="not_selected",
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

    # --- Stage 6: FINAL VALIDATION over the assembled quiz ------------------ #
    provenance_by_id = {record.question_id: record for record in provenance}
    questions, final_notes = validate_final_quiz(
        questions,
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id=provenance_by_id,
        requested_types=question_types,
    )
    rejections.extend(final_notes)
    if final_notes:
        kept = {question.id for question in questions}
        provenance = [record for record in provenance if record.question_id in kept]

    telemetry = _quiz_telemetry(
        source=source,
        context=context,
        understanding=understanding,
        blueprints=context.blueprints,
        requested=count,
        generated=len(selected),
        validated=len(questions),
        rejections=rejections,
        relaxed_gates=outcome.relaxed_gates,
        provider_errors=provider_errors,
        provider_trace=provider_trace,
        # Everything the writers produced across the initial pass and every
        # top-up round, so "generated" can be compared against "accepted".
        candidates_generated=len(scored) + len(
            [n for n in rejections if n.stage != "diversity_selection"]
        ),
    )
    _log_quiz_generation(telemetry, rejections)

    # The contract: exactly what was asked for, or an explicit explanation.
    # Returning 1 of 8 questions silently is the failure this pipeline exists
    # to prevent, and padding the difference would break grounding.
    if require_exact_count and len(questions) < count:
        raise QuizMaterialError(
            _insufficient_material_message(count, len(questions), telemetry)
            + scope_note,
            requested=count,
            available=len(questions),
            telemetry=telemetry,
        )

    # Honesty about who wrote the quiz: the top-up stage uses the deterministic
    # writer, so if any of its questions survived into the final set the result
    # is a mix and must not be reported as pure provider output.
    if completion is not None and not used_deterministic:
        selected_blueprints = {record.blueprint_id for record in provenance}
        if any(bp_id.startswith("topup") for bp_id in selected_blueprints):
            fallback_used_topup = True
        else:
            fallback_used_topup = False
    else:
        fallback_used_topup = False

    if completion is not None and not used_deterministic:
        provider = completion.provider
        model = completion.model
        fallback_used = bool(
            (map_completion.fallback_used if map_completion is not None else True)
            or completion.fallback_used
            or fallback_used_topup
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
        relaxed_gates=outcome.relaxed_gates,
        telemetry=telemetry,
    )
