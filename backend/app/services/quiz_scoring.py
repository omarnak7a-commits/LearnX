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

import re
import random
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.schemas.ai import AIQuizQuestion
from app.services.quiz_boilerplate import question_boilerplate_fields

if TYPE_CHECKING:  # pragma: no cover - only used for type hints
    from app.services.quiz_concepts import Concept

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
# Concept matching
# --------------------------------------------------------------------------- #

def match_concept(
    question: AIQuizQuestion,
    concepts: list["Concept"],
) -> tuple["Concept", float]:
    """Best-matching concept and the 0..1 overlap score for a question.

    The concept name is weighted more heavily than its (longer) evidence text
    so a question such as "What is X?" cleanly matches concept X rather than
    being diluted by unrelated evidence tokens.
    """
    if not concepts:
        fallback: Any = SimpleNamespace(name="General Overview", importance=0.3, evidence="")
        return fallback, 0.0
    q_tokens = content_tokens(f"{question.prompt} {question.correct_answer}")
    best: "Concept" | None = None
    best_overlap = 0.0
    for concept in concepts:
        name_tokens = content_tokens(concept.name)
        evidence_tokens = content_tokens(" ".join(concept.evidence.split()[:40]))
        overlap = 0.75 * _jaccard(q_tokens, name_tokens) + 0.25 * _jaccard(q_tokens, evidence_tokens)
        if overlap > best_overlap:
            best, best_overlap = concept, overlap
    # A question with no token overlap still maps to the most important concept
    # rather than nothing, keeping scoring well-defined.
    if best is None:
        best, best_overlap = concepts[0], 0.0
    return best, best_overlap


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


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
    quote_on_page = bool(quote_key) and any(
        quote_key in " ".join(content_token_list(page_text.get(page, ""))) for page in valid_pages
    )
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


def score_candidate(
    question: AIQuizQuestion,
    *,
    concepts: list["Concept"],
    vocab: set[str],
    page_text: dict[int, str],
    included_pages: set[int],
    requested_difficulty: str,
    history: list[str],
) -> CandidateScore:
    """Compatibility scorer for callers without blueprints.

    The production pipeline uses :func:`score_blueprinted_candidate`; this
    adapter keeps the deterministic utility useful in tests and older code
    while using the same eight weights.
    """
    boilerplate = question_boilerplate_fields(question)
    if boilerplate:
        return CandidateScore(total=0.0, boilerplate=boilerplate)
    concept, overlap = match_concept(question, concepts)
    skill = classify_cognitive_skill(question.prompt)
    # Legacy candidates have no exact quote, so use their matched evidence and
    # pages as a diagnostic estimate—not as production-grade grounding.
    score = score_blueprinted_candidate(
        question,
        importance=_clamp(concept.importance * (0.5 + overlap)),
        cognitive_skill=skill,
        evidence=concept.evidence,
        source_quote=concept.evidence,
        vocab=vocab,
        page_text=page_text,
        included_pages=included_pages,
        requested_difficulty=requested_difficulty,
        history=history,
    )
    return score


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


def select_diverse(
    candidates: list[ScoredCandidate],
    count: int,
    *,
    rng: random.Random,
) -> list[AIQuizQuestion]:
    """Select strong questions with hard objective deduplication and diversity.

    The same concept may legitimately recur only for a different knowledge
    target. The same semantic objective may not recur at all, even when its
    wording, cognitive verb, or question type differs.
    """
    pool = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    selected: list[AIQuizQuestion] = []
    seen_objectives: set[str] = set()
    seen_concept_targets: set[tuple[str, str]] = set()
    concept_counts: dict[str, int] = {}
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
            penalty = 0.0
            penalty += 0.18 * skill_counts.get(candidate.skill, 0)
            penalty += 0.08 * pattern_counts.get(candidate.pattern, 0)
            penalty += 0.12 * concept_counts.get(candidate.concept.casefold(), 0)
            if candidate.category:
                penalty += 0.05 * category_counts.get(candidate.category, 0)
            for page in candidate.question.source_pages:
                penalty += 0.035 * page_counts.get(page, 0)
            if candidate.question.type == "true-false":
                answer = normalize_question_text(candidate.question.correct_answer)
                if answer in {"true", "صح", "صحيح"} and true_count > false_count:
                    penalty += 0.16
                if answer in {"false", "خطا"} and false_count > true_count:
                    penalty += 0.16
            # Seeds vary only candidates that have already cleared every hard
            # gate and the quality floor; jitter can never rescue weak content.
            adjusted = candidate.score - penalty + rng.random() * 0.035
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
