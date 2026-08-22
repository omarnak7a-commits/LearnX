"""Scoring, de-duplication, diversity selection, and randomization for quiz questions.

Everything in this module is deterministic and provider-free: given the same
question text and the same seed it always produces the same answer. It exists
so that the "intelligence" of the quiz pipeline is explainable and testable
rather than buried inside a single opaque LLM prompt.

The module is split into four concerns:

1. Text normalization + tokenization (Arabic & English, including
   Arabic diacritic/alef/teh-marbuta/yeh canonicalization so that
   "ما هي وظيفة" and "ما هو وظيفه" compare as the same text).
2. Semantic duplicate detection (exact + paraphrase), with the
   cognitive-skill guard so "What is X?" and "How does X work?" are not
   collapsed into one question even though their content tokens overlap.
3. Transparent per-candidate quality scoring.
4. Greedy diversity selection + seeded answer-position randomization.
"""

from __future__ import annotations

import hashlib

import re
import random
from dataclasses import dataclass, field
from collections.abc import Collection
from typing import Any

from app.schemas.ai import AIQuizQuestion
from app.services.quiz_boilerplate import question_boilerplate_fields

_DEFAULT_QUALITY_THRESHOLD = 0.55

# --------------------------------------------------------------------------- #
# Text normalization
# --------------------------------------------------------------------------- #

_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u0640]")


def normalize_arabic(text: str) -> str:
    """Canonicalize Arabic spelling so equivalent words compare as equal."""
    text = _ARABIC_DIACRITICS.sub("", text)
    for src, dst in (
        ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
        ("ى", "ي"), ("ئ", "ي"), ("ؤ", "و"), ("ء", ""),
        ("ة", "ه"),
    ):
        text = text.replace(src, dst)
    return text


def normalize_question_text(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace for comparisons."""
    if not text:
        return ""
    text = normalize_arabic(text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_WORD_RE = re.compile(r"[a-z0-9][a-z0-9']*|[\u0600-\u06FF\u0750-\u077F]{2,}")


def tokenize_words(text: str) -> list[str]:
    """Tokenize mixed Arabic/English text into normalized lower-case words."""
    if not text:
        return []
    return _WORD_RE.findall(normalize_question_text(text))


# --------------------------------------------------------------------------- #
# Vocabulary: stopwords, question scaffold words, and near-synonym groups
# --------------------------------------------------------------------------- #

_STOPWORDS = set(
    """a an the of to in and is are was were be been being for on with as at by
    from that this these those it its into or not no can may might will would
    should could shall must do does did has have had than then so such but if
    while when where which who whom whose what how why also because between
    within without about above below over under again further once here there
    all any both each few more most other some own same too very s t just don
    now i we you they he she him her his their our your my me us them one two
    three following best which except true false statement option answer
    question correct incorrect not except is""".split()
)

# Arabic function words (already normalized: alef/teh-marbuta/yeh forms).
_AR_STOPWORDS = set(
    """من عن في علي الي و او ان لم لن لا ليس ليست كان يكون تكون هي هو هم هما
    التي الذي الذين هذا هذه ذلك تلك كل بعض بين حيث عند قبل بعد اي اذا ثم كما
    مع منه منها فيه فيها عنه عنها هل فوق تحت داخل خارج نحو حتي لكن لان قد سوف
    انه انها منها""".split()
)

# Question scaffolding words carry no content of their own and are ignored
# when comparing the *substance* of two questions (so "What is X?" and
# "Define X." compare only on X).
_SCAFFOLD = set(
    """what which who whom whose how why when where is are was were be been
    being does do did has have had explain explains explained describe
    describes described define defines defined state states identify
    identifies name names list lists outline outlines summarize summarises
    summary give gives mention mentions true false statement option answer
    question following except correct incorrect best which""".split()
)

# Arabic question scaffolding (normalized). "ما/ماذا/لماذا/كيف/هل" and the
# imperative study verbs are treated like their English counterparts.
_AR_SCAFFOLD = set(
    """ما ماذا لماذا كيف هل عرف اذكر اشرح وضح قارن لخص عدد حدد صف صح خطا صحيح
    صحيحه مقارنه المقصود اشرحي""".split()
)

# Each group is canonicalized to its first member. This is what lets
# "main purpose" match "primary function".
_SYNONYM_GROUPS: list[list[str]] = [
    ["main", "primary", "principal", "chief", "key", "core"],
    ["purpose", "function", "role", "aim", "goal", "objective"],
    ["meaning", "definition", "defined", "defines", "define", "means", "term"],
    ["difference", "differ", "differs", "different", "distinguish", "compare", "comparison", "contrast"],
    ["produce", "produces", "produced", "generate", "generates", "create", "creates", "yield", "yields", "form", "forms"],
    ["cause", "causes", "reason", "reasons", "trigger"],
    ["effect", "effects", "outcome", "outcomes", "consequence", "result", "results"],
    ["process", "mechanism", "procedure", "method"],
    ["step", "steps", "stage", "stages", "phase", "phases", "sequence"],
    ["increase", "increases", "rise", "rises"],
    ["decrease", "decreases", "decline", "reduce", "reduces"],
    ["important", "significant", "essential", "crucial", "vital"],
    ["characteristic", "characteristics", "feature", "features", "property", "properties", "trait", "traits"],
    ["relationship", "relation", "connection", "link"],
    ["happen", "happens", "occur", "occurs"],
    ["affect", "affects", "influence", "influences", "impact"],
    ["environmental", "environment", "surrounding"],
    ["condition", "conditions", "factor", "factors"],
]

_AR_SYNONYM_GROUPS: list[list[str]] = [
    ["وظيفه", "دور", "هدف", "الهدف", "الغرض", "غايه"],
    ["معني", "تعريف", "يعرف", "يعني", "تعني", "مفهوم"],
    ["فرق", "الفرق", "اختلاف", "يختلف", "اختلف", "قارن", "مقارنه"],
    ["اشرح", "يشرح", "وضح", "صف", "اذكر", "عدد", "لخص"],
    ["سبب", "السبب", "يسبب", "تودي", "يودي", "نتيجه", "ينتج", "اثر", "يوثر"],
    ["عمليه", "اليه", "طريقه", "اجراء"],
    ["خطوه", "خطوات", "مرحله", "مراحل", "ترتيب", "تسلسل"],
    ["يزيد", "زياده", "يرتفع", "ارتفاع"],
    ["يقل", "انخفاض", "ينخفض", "تناقص"],
    ["مهم", "اهميه", "اساسي", "جوهري"],
    ["خاصيه", "خصايص", "صفه", "سمه", "ميزه"],
    ["علاقه", "العلاقه", "ارتباط", "صله"],
    ["خاطي", "خطا", "غير صحيح", "غير صحيحه"],
    ["صحيح", "صحيحه", "صح"],
    ["يحدث", "تحدث", "يقع"],
]

_CANONICAL: dict[str, str] = {}
for _group in _SYNONYM_GROUPS + _AR_SYNONYM_GROUPS:
    _canon = normalize_question_text(_group[0])
    for _word in _group:
        _CANONICAL[normalize_question_text(_word)] = _canon


def content_token_list(text: str) -> list[str]:
    """Ordered, canonicalized content tokens (scaffold/stopwords removed)."""
    out: list[str] = []
    for token in tokenize_words(text):
        if token in _SCAFFOLD or token in _AR_SCAFFOLD or token in _STOPWORDS or token in _AR_STOPWORDS:
            continue
        out.append(_CANONICAL.get(token, token))
    return out


def content_tokens(text: str) -> set[str]:
    """Unique, canonicalized content tokens."""
    return set(content_token_list(text))


def content_jaccard(a: str, b: str) -> float:
    """Jaccard similarity over canonicalized content tokens."""
    ca = content_tokens(a)
    cb = content_tokens(b)
    if not ca or not cb:
        return 0.0
    return len(ca & cb) / len(ca | cb)


# --------------------------------------------------------------------------- #
# Cognitive-skill and wording-pattern classification
# --------------------------------------------------------------------------- #

# Each entry is (skill, [english substring, arabic substring, ...]). ASCII
# phrases are matched on word boundaries; Arabic phrases are matched as
# substrings. Order is meaningful: the first match wins.
_SKILL_RULES: list[tuple[str, list[str]]] = [
    ("misconception", ["incorrect", "not true", "is wrong", "false", "except", "misconception", "does not", "cannot", "which statement is wrong", "غير صحيح", "خاطي", "ما عدا", "الخطا", "ليست", "ليس"]),
    ("comparison", ["differ", "difference", "different", "compare", "contrast", "versus", "similar", "unlike", "whereas", "distinguish", "الفرق", "قارن", "مقارنه", "يختلف", "اختلاف", "بينما", "على عكس", "تشابه"]),
    ("process_order", ["step", "stage", "phase", "sequence", "order", "first", "next", "then", "follows", "followed by", "which step", "occurs next", "process", "work", "works", "produce", "produced", "generate", "generated", "الخطوه", "خطوات", "مرحله", "ترتيب", "تسلسل", "التالي", "العمليه", "ينتج", "يتم انتاج"]),
    ("cause_effect", ["why", "because", "reason", "cause", "effect", "affect", "leads", "results in", "due to", "therefore", "consequence", "impact", "لماذا", "السبب", "بسبب", "نتيجه", "يودي", "يسبب", "تاثير", "اثر"]),
    ("application", ["what would happen", "scenario", "demonstrates", "demonstrate", "example", "apply", "predict", "suppose", "given", "ماذا يحدث لو", "سيناريو", "مثال", "لنفترض", "توقع", "يطبق"]),
    ("analysis", ["infer", "inference", "conclusion", "conclude", "best supported", "evidence supports", "analyze", "analysis", "relationship", "can be deduced", "استنتاج", "يستنتج", "حلل", "العلاقه"]),
    ("understanding", ["explain", "explains", "describe", "describes", "how", "main purpose", "primary function", "main idea", "main function", "purpose", "function", "role", "best explains", "best describes", "summarize", "relation", "why is", "اشرح", "وضح", "وظيفه", "لخص", "الفكره", "الغرض"]),
    ("factual_recall", ["what is", "define", "definition", "which of the following", "identify", "name", "list", "true or false", "who", "what", "when", "where", "ما هو", "ما هي", "عرف", "تعريف", "اذكر", "عدد", "ما المقصود", "حدد", "صح ام خطا", "ما"]),
]

_PATTERN_RULES: list[tuple[str, list[str]]] = [
    ("incorrect", ["incorrect", "except", "not true", "false", "which statement is wrong", "غير صحيح", "خاطي", "ما عدا", "الخطا"]),
    ("comparison", ["differ", "difference", "compare", "contrast", "versus", "unlike", "whereas", "الفرق", "قارن", "يختلف"]),
    ("hypothetical", ["what would happen", "scenario", "demonstrates", "suppose", "predict", "if", "ماذا يحدث لو", "سيناريو", "لنفترض"]),
    ("process_step", ["step", "stage", "order", "sequence", "next", "followed by", "occurs next", "الخطوه", "مرحله", "ترتيب", "التالي"]),
    ("purpose", ["purpose", "function", "role", "main idea", "main aim", "goal", "الغرض", "الوظيفه", "الهدف", "الفكره"]),
    ("conclusion", ["conclusion", "best supported", "infer", "implies", "suggests", "استنتاج", "يستنتج"]),
    ("relationship", ["relationship", "relation", "between", "العلاقه", "بين"]),
    ("why_reason", ["why", "because", "reason", "لماذا", "السبب"]),
    ("definition", ["what is", "define", "definition", "means", "refers to", "ما هو", "ما هي", "عرف", "تعريف", "معني"]),
    ("which_statement", ["which statement", "which of the following", "which option", "اي العبارات", "اي مما يلي"]),
]


def _matches(text: str, phrase: str) -> bool:
    if phrase.isascii():
        return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None
    return phrase in text


def _classify(text: str, rules: list[tuple[str, list[str]]]) -> str:
    normalized = normalize_question_text(text)
    for skill, phrases in rules:
        for phrase in phrases:
            if _matches(normalized, phrase):
                return skill
    return rules[-1][0]


def classify_cognitive_skill(text: str) -> str:
    """Map a question prompt to one cognitive-skill bucket."""
    return _classify(text, _SKILL_RULES)


def classify_pattern(text: str) -> str:
    """Map a question prompt to a wording-pattern bucket."""
    return _classify(text, _PATTERN_RULES)


# --------------------------------------------------------------------------- #
# Trivial / metadata rejection
# --------------------------------------------------------------------------- #

_TRIVIAL_PATTERNS = [
    r"\bpage\s*\d", r"\bpages\s*\d", r"what page", r"which page", r"how many pages",
    r"\bisbn\b", r"\bword count\b", r"how many words", r"\bnumber of words\b",
    r"\bcopyright\b", r"all rights reserved", r"\btable of contents\b",
    r"\bcontents\b", r"\bappendix\b", r"\breferences\b", r"\bbibliography\b",
    r"\bheader\b", r"\bfooter\b", r"\bpublished\b", r"\btitle of\b",
    r"\bauthor name\b", r"\bedition\b", r"\bprint(ed|ing)\b", r"\bpage size\b",
    r"\bصفحه\s*\d", r"\bرقم الصفحة\b", r"\bفهرس\b", r"\bالمراجع\b", r"\bترقيم\b",
    r"\bعدد الكلمات\b", r"\bعنوان الوثيقة\b", r"\bالناشر\b", r"\bحقوق النشر\b",
]


def is_trivial_question(prompt: str) -> bool:
    """Return True when a prompt tests metadata/formatting rather than content."""
    text = normalize_question_text(prompt)
    for pattern in _TRIVIAL_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


# --------------------------------------------------------------------------- #
# Duplicate detection
# --------------------------------------------------------------------------- #

def exact_duplicate_key(text: str) -> str:
    return normalize_question_text(text)


def semantic_similarity(a: str, b: str) -> float:
    """0..1 similarity between two question texts (1.0 == paraphrase)."""
    na = normalize_question_text(a)
    nb = normalize_question_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return content_jaccard(na, nb)


def is_semantic_duplicate(a: str, b: str, threshold: float = 0.6) -> bool:
    """Paraphrase-aware duplicate check.

    Two questions are duplicates when their canonicalized content tokens
    overlap enough. Stopwords and question scaffolding ("what", "is", "of",
    "ما", "هي", ...) are ignored, and near-synonyms are canonicalized
    (purpose≈function, main≈primary), so:

        "What is the main purpose of photosynthesis?"
        "What is the primary function of photosynthesis?"

    collapse together, while

        "What is the main purpose of photosynthesis?"
        "Which environmental condition most directly affects photosynthesis?"

    do not. Different cognitive intents that change the content words
    ("What is X?" vs "How does X work?") naturally fall below the overlap
    threshold because "work" is a distinct content token.
    """
    na = normalize_question_text(a)
    nb = normalize_question_text(b)
    if na == nb:
        return True
    return content_jaccard(na, nb) >= threshold


def duplicates_within(questions: list[AIQuizQuestion], threshold: float = 0.6) -> list[AIQuizQuestion]:
    """Return the unique subset of questions (first occurrence kept)."""
    kept: list[AIQuizQuestion] = []
    for question in questions:
        if any(is_semantic_duplicate(question.prompt, kept_q.prompt, threshold) for kept_q in kept):
            continue
        kept.append(question)
    return kept


def is_repeat_of_history(question: AIQuizQuestion, history: list[str], threshold: float = 0.6) -> bool:
    return any(is_semantic_duplicate(question.prompt, past, threshold) for past in history)


# --------------------------------------------------------------------------- #
# Quality scoring
# --------------------------------------------------------------------------- #

_DIFF_ORDER = {"easy": 0, "medium": 1, "hard": 2}


@dataclass
class CandidateScore:
    """The eight product quality dimensions and their exact weighted total."""

    total: float
    educational_importance: float = 0.0
    source_grounding: float = 0.0
    conceptual_understanding: float = 0.0
    clarity: float = 0.0
    distractor_quality: float = 0.0
    cognitive_value: float = 0.0
    novelty: float = 0.0
    difficulty_match: float = 0.0
    # Compatibility diagnostics retained for existing callers/tests.  They do
    # not add extra weight to the final score.
    relevance: float = 0.0
    educational_value: float = 0.0
    concept_importance: float = 0.0
    boilerplate: list[str] = field(default_factory=list)

    @property
    def breakdown(self) -> dict[str, float]:
        return {
            "educational_importance": self.educational_importance,
            "source_grounding": self.source_grounding,
            "conceptual_understanding": self.conceptual_understanding,
            "clarity": self.clarity,
            "distractor_quality": self.distractor_quality,
            "cognitive_value": self.cognitive_value,
            "novelty": self.novelty,
            "difficulty_match": self.difficulty_match,
        }


# These constants are intentionally public in the module: tests assert that
# implementation and product specification cannot silently drift apart.
QUALITY_WEIGHTS: dict[str, float] = {
    "educational_importance": 0.25,
    "source_grounding": 0.20,
    "conceptual_understanding": 0.15,
    "clarity": 0.10,
    "distractor_quality": 0.10,
    "cognitive_value": 0.10,
    "novelty": 0.05,
    "difficulty_match": 0.05,
}


def _difficulty_match(question_difficulty: str, requested: str) -> float:
    if requested == "mixed":
        return 1.0
    if question_difficulty == requested:
        return 1.0
    delta = abs(_DIFF_ORDER.get(question_difficulty, 1) - _DIFF_ORDER.get(requested, 1))
    return {0: 1.0, 1: 0.5, 2: 0.2}.get(delta, 0.0)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


_ABSURD_DISTRACTOR = re.compile(
    r"\b(banana|purple elephant|unicorn|magic|random answer|i don t know|none of the above|all of the above|zzzz)\b",
    re.IGNORECASE,
)


def distractor_quality_score(question: AIQuizQuestion, vocab: set[str]) -> float:
    """Category/shape/source checks for MCQ distractors (1.0 for non-MCQ)."""
    if question.type != "mcq":
        if question.type == "true-false":
            values = {normalize_question_text(value) for value in question.options or []}
            return 1.0 if values == {"true", "false"} or values == {"صح", "خطا"} else 0.0
        return 1.0
    if not question.options or len(question.options) != 4:
        return 0.0

    normalized = [normalize_question_text(value) for value in question.options]
    if any(not value for value in normalized) or len(set(normalized)) != 4:
        return 0.0
    correct_key = normalize_question_text(question.correct_answer)
    if normalized.count(correct_key) != 1:
        return 0.0
    correct = question.correct_answer.strip()
    distractors = [value.strip() for value in question.options if normalize_question_text(value) != correct_key]
    if len(distractors) != 3:
        return 0.0

    option_lengths = [max(1, len(content_token_list(value))) for value in question.options]
    shortest, longest = min(option_lengths), max(option_lengths)
    shape = 1.0 if longest <= max(5, shortest * 4) else 0.55
    correct_numeric = bool(re.search(r"\d|[=+*/^]", correct))
    if correct_numeric:
        numeric_count = sum(bool(re.search(r"\d|[=+*/^]", value)) for value in question.options)
        if numeric_count < 3:
            shape *= 0.4
    if correct.lower().startswith("to "):
        parallel = sum(value.lower().startswith("to ") for value in question.options)
        if parallel < 3:
            shape *= 0.65

    checks: list[float] = []
    for distractor in distractors:
        value = 1.0
        if len(distractor) < 2 or len(distractor) > 400:
            value *= 0.25
        if _ABSURD_DISTRACTOR.search(normalize_question_text(distractor)):
            value = 0.0
        tokens = content_tokens(distractor)
        # Plausible distractors should be drawn from the same source domain.
        if not (tokens & vocab):
            value *= 0.25
        length_ratio = max(len(distractor), len(correct)) / max(1, min(len(distractor), len(correct)))
        if length_ratio > 5:
            value *= 0.45
        checks.append(value)
    return _clamp(shape * (sum(checks) / max(1, len(checks))))


def _clarity_score(question: AIQuizQuestion) -> float:
    # Clarity is about readable question form, not the number of non-stopword
    # concepts. A concise prompt such as "What is mitosis?" is grammatically
    # complete even though its content-token set has only one item.
    prompt_words = re.findall(r"[^\W_]+", question.prompt, flags=re.UNICODE)
    if len(prompt_words) < 3 or len(question.prompt) < 8 or len(question.prompt) > 600:
        return 0.35
    value = 1.0
    if re.search(r"\b(thing|stuff|something|it above|the text above)\b", question.prompt, re.IGNORECASE):
        value *= 0.45
    if question.type in {"mcq", "true-false"} and not question.options:
        value *= 0.2
    if question.type == "fill-blank" and len(re.findall(r"_{3,}", question.prompt)) != 1:
        value *= 0.2
    return value


def _cognitive_score(skill: str) -> float:
    return {
        "factual_recall": 0.55,
        "understanding": 0.80,
        "process_order": 0.86,
        "misconception": 0.86,
        "cause_effect": 0.92,
        "comparison": 0.92,
        "application": 1.0,
        "analysis": 1.0,
    }.get(skill, 0.65)


def _novelty(question: AIQuizQuestion, history: list[str]) -> float:
    if not history:
        return 1.0
    return 1.0 - max(semantic_similarity(question.prompt, past) for past in history)


def _explanation_quality(question: AIQuizQuestion, evidence: str = "") -> float:
    explanation_tokens = content_tokens(question.explanation)
    if len(explanation_tokens) < 4:
        return 0.25
    specificity = _clamp(len(explanation_tokens) / 12)
    if evidence:
        overlap = len(explanation_tokens & content_tokens(evidence)) / max(1, len(explanation_tokens))
        specificity = 0.45 * specificity + 0.55 * _clamp(overlap * 2.5)
    return specificity


def _weighted_score(values: dict[str, float]) -> float:
    return sum(QUALITY_WEIGHTS[name] * values[name] for name in QUALITY_WEIGHTS)


def score_blueprinted_candidate(
    question: AIQuizQuestion,
    *,
    importance: float,
    cognitive_skill: str,
    evidence: str,
    source_quote: str,
    vocab: set[str],
    page_text: dict[int, str],
    included_pages: set[int],
    requested_difficulty: str,
    history: list[str],
) -> CandidateScore:
    """Authoritative score for a candidate tied to a verified blueprint."""
    boilerplate = question_boilerplate_fields(question)
    if boilerplate:
        return CandidateScore(total=0.0, boilerplate=boilerplate)

    prompt_tokens = content_tokens(question.prompt)
    answer_tokens = content_tokens(question.correct_answer)
    explanation_tokens = content_tokens(question.explanation)
    evidence_tokens = content_tokens(evidence)
    quote_key = " ".join(content_token_list(source_quote))
    evidence_key = " ".join(content_token_list(evidence))

    valid_pages = [page for page in question.source_pages if page in included_pages]

    def _page_contains(page: int) -> bool:
        if quote_key in " ".join(content_token_list(page_text.get(page, ""))):
            return True
        # A sentence broken by a page break is on neither page in full. The
        # sentence reader rejoins those halves, so check the join as well —
        # the quote must still occur contiguously in the document's text.
        for first, second in ((page, page + 1), (page - 1, page)):
            joined = " ".join(
                content_token_list(
                    f"{page_text.get(first, '')} {page_text.get(second, '')}"
                )
            )
            if joined and quote_key in joined:
                return True
        return False

    quote_on_page = bool(quote_key) and any(_page_contains(page) for page in valid_pages)
    quote_matches_evidence = bool(quote_key and evidence_key) and (
        quote_key == evidence_key or quote_key in evidence_key or evidence_key in quote_key
    )
    answer_support = 1.0 if question.type == "true-false" else _clamp(
        len(answer_tokens & evidence_tokens) / max(1, len(answer_tokens)) * 1.5
    )
    prompt_support = _clamp(len(prompt_tokens & evidence_tokens) / max(1, len(prompt_tokens)) * 2.0)
    explanation_support = _clamp(
        len(explanation_tokens & evidence_tokens) / max(1, len(explanation_tokens)) * 2.0
    )
    source_grounding = (
        0.35 * float(quote_on_page)
        + 0.25 * float(quote_matches_evidence)
        + 0.15 * answer_support
        + 0.10 * prompt_support
        + 0.15 * explanation_support
    )

    educational_importance = _clamp(importance)
    conceptual_understanding = 0.55 * _cognitive_score(cognitive_skill) + 0.45 * _explanation_quality(
        question, evidence
    )
    clarity = _clarity_score(question)
    distractors = distractor_quality_score(question, vocab)
    cognitive_value = _cognitive_score(cognitive_skill)
    novelty = _novelty(question, history)
    difficulty_match = _difficulty_match(question.difficulty, requested_difficulty)
    relevance = _clamp(
        len(content_tokens(f"{question.prompt} {question.correct_answer}") & vocab)
        / max(1, len(content_tokens(f"{question.prompt} {question.correct_answer}")))
    )
    values = {
        "educational_importance": educational_importance,
        "source_grounding": source_grounding,
        "conceptual_understanding": conceptual_understanding,
        "clarity": clarity,
        "distractor_quality": distractors,
        "cognitive_value": cognitive_value,
        "novelty": novelty,
        "difficulty_match": difficulty_match,
    }
    total = _weighted_score(values)
    rounded = {name: round(value, 4) for name, value in values.items()}
    return CandidateScore(
        total=round(total, 4),
        **rounded,
        relevance=round(relevance, 4),
        educational_value=round(_explanation_quality(question, evidence), 4),
        concept_importance=round(educational_importance, 4),
    )


# --------------------------------------------------------------------------- #
# Diversity selection and randomization
# --------------------------------------------------------------------------- #

@dataclass
class ScoredCandidate:
    question: AIQuizQuestion
    score: float
    concept: str
    skill: str
    pattern: str
    objective_key: str = ""
    blueprint_id: str = ""
    category: str = ""
    knowledge_target: str = ""


def _shuffle(rng: random.Random, items: list[Any]) -> list[Any]:
    copy = list(items)
    rng.shuffle(copy)
    return copy


def randomize_answer_positions(question: AIQuizQuestion, rng: random.Random) -> AIQuizQuestion:
    """Deterministically shuffle MCQ/TF option order; the correct answer stays
    a value (never an index), so shuffling options is safe for the frontend."""
    if question.type in {"mcq", "true-false"} and question.options:
        question.options = _shuffle(rng, question.options)
    return question


def _symmetric_pair_key(candidate) -> tuple[str, ...] | None:
    """An order-independent key for a comparison question.

    "How does waiting time differ from turnaround time?" and "How does
    turnaround time differ from waiting time?" test one distinction, so the
    exam must contain at most one of them. Sorting the two names makes both
    phrasings collapse to the same key.
    """
    match = re.search(
        r"how (?:does|do) (?P<left>.+?) differ from (?P<right>.+?)\?"
        r"|explain how (?P<left2>.+?) differs from (?P<right2>.+?)\.",
        candidate.question.prompt,
        re.IGNORECASE,
    )
    if not match:
        return None
    groups = match.groupdict()
    left = groups.get("left") or groups.get("left2") or ""
    right = groups.get("right") or groups.get("right2") or ""
    if not left or not right:
        return None
    pair = sorted(
        (normalize_question_text(left), normalize_question_text(right))
    )
    return ("comparison", *pair)


# Seed variation must choose among *comparable* candidates, never trade a
# relationship for a definition. Real quality gaps between a reasoning question
# and a recognition question are often only a few hundredths, so jitter wide
# enough to cross that gap silently promotes the weaker question. Keep the
# noise below the smallest gap that carries educational meaning.
_JITTER_RANGE = 0.008


def _stable_jitter(seed_token: int, candidate) -> float:
    """Seeded tie-breaking noise that does not depend on evaluation order.

    Derived from the candidate's identity rather than drawn in loop order, so
    the same seed yields the same quiz no matter how many candidates were
    skipped before it.
    """
    digest = hashlib.blake2b(
        f"{seed_token}:{candidate.question.id}".encode(), digest_size=8
    ).digest()
    return (int.from_bytes(digest, "big") / float(1 << 64)) * _JITTER_RANGE


def _claim_signature(candidate) -> frozenset[str] | None:
    """The asserted claim, ignoring which concept it is attributed to.

    Two true/false questions that assert the same relationship — one correctly,
    one with a swapped subject — test a single piece of knowledge. Dropping the
    concept tokens and keeping the predicate exposes that equivalence, which a
    concept+target+skill key cannot see because the skills differ.

    Compared by overlap rather than equality: the swapped-in concept leaves its
    own tokens behind, so the two signatures are near-identical but never equal.

    The claim carrier depends on the type. A true/false question states it in
    the prompt; a multiple-choice question states it in the correct option,
    with the prompt carrying only a stem. Reading the prompt for both would
    miss the case that matters most: an MCQ whose right answer *is* the claim
    another question asks the student to judge hands over that answer.
    """
    question = candidate.question
    if question.type == "true-false":
        claim = question.prompt
    elif question.type == "mcq":
        claim = question.correct_answer or ""
    else:
        return None
    tokens = content_tokens(claim) - content_tokens(candidate.concept)
    if len(tokens) < 4:
        return None
    return frozenset(tokens)


#: Redundancy gates that express a *preference* for a better-spread exam.
#: Each one removes a question that is already grounded, already validated and
#: already above the quality floor -- it is dropped only because something
#: similar was picked first. When enforcing them all would return a short quiz,
#: they are relaxed in the order below (least educational harm first) rather
#: than handing the student fewer questions than they asked for.
RELAXABLE_GATES: tuple[str, ...] = (
    "claim_similarity",
    "symmetric_pair",
    "concept_breadth",
)

#: Never relaxed, and therefore not listed above: the objective-key and
#: concept+target gates. Those identify the *same* learning objective asked
#: twice, which is a duplicate question rather than a near neighbour.


def select_diverse(
    candidates: list[ScoredCandidate],
    count: int,
    *,
    rng: random.Random,
    gates: Collection[str] = RELAXABLE_GATES,
) -> list[AIQuizQuestion]:
    """Select strong questions with hard objective deduplication and diversity.

    The same concept may legitimately recur only for a different knowledge
    target. The same semantic objective may not recur at all, even when its
    wording, cognitive verb, or question type differs.

    ``gates`` names which *relaxable* redundancy gates to enforce. Duplicate
    objectives are always rejected; the gates in :data:`RELAXABLE_GATES` are
    quality preferences, and :func:`select_quiz_questions` drops them one at a
    time when the alternative is returning fewer questions than requested.
    """
    enforced = set(gates)
    pool = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    selected: list[AIQuizQuestion] = []
    seen_objectives: set[str] = set()
    seen_concept_targets: set[tuple[str, str]] = set()
    seen_pairs: set[tuple[str, ...]] = set()
    seen_claims: set[frozenset[str]] = set()
    # One draw fixes this quiz's variation; per-candidate jitter is then derived
    # from it, so the result never depends on evaluation order.
    seed_token = rng.getrandbits(32)
    concept_counts: dict[str, int] = {}
    # Distinct concepts the candidate pool can cover; breadth is enforced only
    # until each has been used once.
    concepts_available = len({c.concept.casefold() for c in candidates if c.concept})
    category_counts: dict[str, int] = {}
    page_counts: dict[int, int] = {}
    skill_counts: dict[str, int] = {}
    pattern_counts: dict[str, int] = {}
    true_count = 0
    false_count = 0

    while pool and len(selected) < count:
        best_index = -1
        best_score = float("-inf")
        for index, candidate in enumerate(pool):
            concept_target = (
                normalize_question_text(candidate.concept),
                normalize_question_text(candidate.knowledge_target),
            )
            if candidate.objective_key and candidate.objective_key in seen_objectives:
                continue
            if all(concept_target) and concept_target in seen_concept_targets:
                continue
            # A comparison is symmetric: asking it from each side is one
            # knowledge target wearing two prompts.
            pair_key = _symmetric_pair_key(candidate)
            if "symmetric_pair" in enforced and pair_key and pair_key in seen_pairs:
                continue
            # A misconception question restates a relationship with the wrong
            # concept attached, so it carries almost the same words as the
            # true version of that same claim. Asking both ("Friction opposes
            # relative motion" / "Inertial mass opposes relative motion")
            # tests one fact twice and hands the student the answer to the
            # other. Compare the *claim*, independent of the concept named.
            claim_key = _claim_signature(candidate)
            if (
                "claim_similarity" in enforced
                and claim_key
                and any(
                    len(claim_key & seen) / max(1, len(claim_key | seen)) >= 0.70
                    for seen in seen_claims
                )
            ):
                continue
            penalty = 0.0
            penalty += 0.18 * skill_counts.get(candidate.skill, 0)
            penalty += 0.08 * pattern_counts.get(candidate.pattern, 0)
            # Concept breadth dominates. While untested concepts remain, a
            # repeat must lose outright: quality differences between two valid
            # questions are small compared with the educational cost of leaving
            # a whole concept unexamined, and a soft penalty lets a marginally
            # better duplicate crowd out an untouched concept. Once every
            # concept has been covered, repeats compete normally.
            repeats = concept_counts.get(candidate.concept.casefold(), 0)
            if repeats:
                if (
                    "concept_breadth" in enforced
                    and len(concept_counts) < concepts_available
                ):
                    continue
                penalty += 0.45 * repeats
            if candidate.category:
                penalty += 0.05 * category_counts.get(candidate.category, 0)
            for page in candidate.question.source_pages:
                penalty += 0.035 * page_counts.get(page, 0)
            if candidate.question.type == "true-false":
                # A quiz whose true/false answers are all "True" is answerable
                # without reading the questions. The penalty scales with the
                # imbalance so it cannot be out-competed by a marginally higher
                # quality score, which is what previously let an all-True set
                # through.
                answer = normalize_question_text(candidate.question.correct_answer)
                is_true = answer in {"true", "صح", "صحيح"}
                is_false = answer in {"false", "خطا"}
                skew = abs(true_count - false_count)
                # Once one polarity is present, the *other* polarity is what a
                # balanced quiz needs. Using ">" meant the penalty only fired
                # after an imbalance already existed, so a quiz with exactly two
                # true/false slots could take True twice: at the second slot
                # true_count(1) > false_count(0) was true only for the first
                # comparison, and the second True paid nothing. ">=" charges a
                # repeat of the polarity already on the page, which is the case
                # that produces a uniform set.
                if is_true and true_count >= max(1, false_count):
                    penalty += 0.16 + 0.30 * skew
                if is_false and false_count >= max(1, true_count):
                    penalty += 0.16 + 0.30 * skew
                # A fixed entry cost on the first "False" used to stand in for
                # the missing repeat penalty above. With the symmetric ">="
                # rule it is not only redundant but harmful: when a concept's
                # true and false candidates score equally, the surcharge hands
                # every first slot to True, which is exactly the uniform-
                # polarity defect it was meant to prevent, mirrored. Polarity
                # is now decided only by merit plus the repeat penalty.
            # Seeds vary only candidates that have already cleared every hard
            # gate and the quality floor; jitter can never rescue weak content.
            #
            # The jitter is derived from the seed and the candidate's identity
            # rather than drawn from the generator in loop order. Drawing in
            # order made the result depend on how many candidates were skipped
            # before it, and skip decisions consult sets whose iteration order
            # varies between runs — so the same seed could produce two
            # different quizzes. Deriving it per candidate keeps the same
            # seeded variation while making it reproducible.
            adjusted = candidate.score - penalty + _stable_jitter(seed_token, candidate)
            if adjusted > best_score:
                best_score = adjusted
                best_index = index

        if best_index < 0:
            break
        chosen = pool.pop(best_index)
        selected.append(chosen.question)
        if chosen.objective_key:
            seen_objectives.add(chosen.objective_key)
        chosen_concept_target = (
            normalize_question_text(chosen.concept),
            normalize_question_text(chosen.knowledge_target),
        )
        if all(chosen_concept_target):
            seen_concept_targets.add(chosen_concept_target)
        chosen_pair = _symmetric_pair_key(chosen)
        if chosen_pair:
            seen_pairs.add(chosen_pair)
        chosen_claim = _claim_signature(chosen)
        if chosen_claim:
            seen_claims.add(chosen_claim)
        concept_key = chosen.concept.casefold()
        concept_counts[concept_key] = concept_counts.get(concept_key, 0) + 1
        if chosen.category:
            category_counts[chosen.category] = category_counts.get(chosen.category, 0) + 1
        skill_counts[chosen.skill] = skill_counts.get(chosen.skill, 0) + 1
        pattern_counts[chosen.pattern] = pattern_counts.get(chosen.pattern, 0) + 1
        for page in chosen.question.source_pages:
            page_counts[page] = page_counts.get(page, 0) + 1
        if chosen.question.type == "true-false":
            answer = normalize_question_text(chosen.question.correct_answer)
            if answer in {"true", "صح", "صحيح"}:
                true_count += 1
            else:
                false_count += 1

    return selected


@dataclass
class SelectionOutcome:
    """The chosen questions plus how hard the selector had to work.

    ``relaxed_gates`` records which redundancy preferences had to be dropped to
    reach the requested count, so the pipeline can log honestly that a quiz is
    complete but slightly more repetitive than ideal.
    """

    questions: list[AIQuizQuestion]
    relaxed_gates: tuple[str, ...] = ()
    shortfall: int = 0


def select_quiz_questions(
    candidates: list[ScoredCandidate],
    count: int,
    *,
    rng: random.Random,
) -> SelectionOutcome:
    """Select ``count`` questions, relaxing soft redundancy gates if needed.

    The selector's redundancy gates are educational preferences: they discard
    questions that are individually valid and grounded, purely because a
    similar one was already picked. Enforcing them unconditionally is what
    turned a request for eight questions into a quiz of six -- the shortfall
    was never a lack of supported material, only an over-strict spread rule.

    So the gates are applied strongest-first and relaxed one at a time, and
    only while the quiz is short. Duplicate learning objectives are never
    admitted; the relaxed gates only ever allow *near* neighbours. If even the
    fully relaxed pass cannot fill the quiz, the pool genuinely lacks the
    material and the caller reports that rather than padding it.
    """
    if count <= 0:
        return SelectionOutcome(questions=[])

    attempts: list[tuple[str, ...]] = [RELAXABLE_GATES]
    for dropped in range(1, len(RELAXABLE_GATES) + 1):
        attempts.append(RELAXABLE_GATES[dropped:])

    best = SelectionOutcome(questions=[], shortfall=count)
    for gates in attempts:
        # Each attempt re-runs from the same seed, so relaxation never depends
        # on the previous pass and the result stays reproducible.
        selected = select_diverse(candidates, count, rng=random.Random(rng_seed(rng)), gates=gates)
        if len(selected) > len(best.questions):
            best = SelectionOutcome(
                questions=selected,
                relaxed_gates=tuple(g for g in RELAXABLE_GATES if g not in set(gates)),
                shortfall=max(0, count - len(selected)),
            )
        if len(selected) >= count:
            break
    return best


def rng_seed(rng: random.Random) -> int:
    """A stable per-call seed derived from ``rng`` without consuming its state.

    ``select_quiz_questions`` may run the selector several times; each pass
    must see the identical random stream so that relaxing a gate is the *only*
    difference between attempts.
    """
    state = rng.getstate()
    token = rng.getrandbits(64)
    rng.setstate(state)
    return token
