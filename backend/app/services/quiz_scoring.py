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
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.schemas.ai import AIQuizQuestion

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
    ("understanding", ["explain", "explains", "describe", "describes", "how", "main purpose", "primary function", "main idea", "main function", "purpose", "function", "role", "best explains", "best describes", "summarize", "relationship", "relation", "conclusion", "why is", "اشرح", "وضح", "وظيفه", "لخص", "الفكره", "العلاقه", "استنتاج", "الغرض"]),
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
    total: float
    relevance: float = 0.0
    educational_value: float = 0.0
    concept_importance: float = 0.0
    difficulty_match: float = 0.0
    novelty: float = 0.0
    clarity: float = 0.0
    distractor_quality: float = 0.0
    source_grounding: float = 0.0

    @property
    def breakdown(self) -> dict[str, float]:
        return {
            "relevance": self.relevance,
            "educational_value": self.educational_value,
            "concept_importance": self.concept_importance,
            "difficulty_match": self.difficulty_match,
            "novelty": self.novelty,
            "clarity": self.clarity,
            "distractor_quality": self.distractor_quality,
            "source_grounding": self.source_grounding,
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
    """Transparent multi-factor score for one candidate question."""
    prompt = normalize_question_text(question.prompt)
    combined_tokens = content_tokens(
        f"{question.prompt} {question.correct_answer} {' '.join(question.options or [])}"
    )
    prompt_tokens = content_tokens(question.prompt)

    # --- relevance: how much of the question is drawn from the source ---
    relevance = _clamp(
        len(combined_tokens & vocab) / max(1, len(combined_tokens)) if combined_tokens else 0.0
    )

    # --- concept importance ---
    concept, concept_overlap = match_concept(question, concepts)
    concept_importance = concept.importance
    # A question that barely touches its assigned concept is less valuable.
    concept_importance *= _clamp(0.5 + concept_overlap)

    # --- educational value ---
    explanation_quality = _clamp(
        (len(question.explanation) - 20) / 120 if len(question.explanation) < 140 else 1.0
    )
    if len(prompt_tokens) >= 3:
        specificity = 1.0
    elif len(prompt_tokens) == 2:
        specificity = 0.85
    elif len(prompt_tokens) == 1:
        specificity = 0.7
    else:
        specificity = 0.3
    educational_value = 0.6 * explanation_quality + 0.4 * specificity

    # --- difficulty match ---
    difficulty_match = _difficulty_match(question.difficulty, requested_difficulty)
    # Hard questions must still be anchored to important content.
    if question.difficulty == "hard" and concept.importance < 0.4:
        difficulty_match *= 0.5

    # --- novelty against previous-question history ---
    novelty = 1.0
    if history:
        novelty = 1.0 - max(semantic_similarity(question.prompt, past) for past in history)

    # --- clarity ---
    clarity = 1.0
    if question.type in {"mcq", "true-false"}:
        if not question.options:
            clarity *= 0.3
        else:
            normalized = [o.strip().lower() for o in question.options]
            if len(set(normalized)) != len(normalized):
                clarity *= 0.4
            if len(question.prompt) < 10 or len(question.prompt) > 500:
                clarity *= 0.6
    if not prompt_tokens:
        clarity *= 0.3

    # --- distractor quality (MCQ only; T/F and text answers have none) ---
    distractor_quality = 1.0
    if question.type == "mcq" and question.options:
        options = question.options
        correct = question.correct_answer.strip()
        distractors = [o for o in options if o.strip().lower() != correct.lower()]
        if len(distractors) < 2:
            distractor_quality *= 0.2
        else:
            checks: list[float] = []
            for d in distractors:
                ok = 1.0
                if not d or not d.strip():
                    ok *= 0.0
                if len(d) < 3 or len(d) > 400:
                    ok *= 0.5
                length_ratio = abs(len(d) - len(correct)) / max(1, len(correct))
                if length_ratio > 1.5:
                    ok *= 0.6
                d_tokens = content_tokens(d)
                if not (d_tokens & vocab):
                    ok *= 0.5  # distractor unrelated to the source
                checks.append(ok)
            distractor_quality *= sum(checks) / len(checks)
    elif question.type == "true-false":
        options = [o.strip().lower() for o in (question.options or [])]
        if sorted(options) not in (["false", "true"], ["صح", "خطا"]):
            distractor_quality *= 0.6

    # --- source grounding: pages in scope + local page-text overlap ---
    source_grounding = 0.0
    valid_pages = [p for p in question.source_pages if p in included_pages]
    if valid_pages:
        source_grounding = 0.5
        local = max(
            (_jaccard(prompt_tokens, content_tokens(page_text.get(p, ""))) for p in valid_pages),
            default=0.0,
        )
        source_grounding += 0.5 * _clamp(local * 2)

    total = (
        0.15 * relevance
        + 0.15 * educational_value
        + 0.20 * concept_importance
        + 0.15 * difficulty_match
        + 0.05 * novelty
        + 0.10 * clarity
        + 0.10 * distractor_quality
        + 0.10 * source_grounding
    )
    return CandidateScore(
        total=round(total, 4),
        relevance=round(relevance, 4),
        educational_value=round(educational_value, 4),
        concept_importance=round(concept_importance, 4),
        difficulty_match=round(difficulty_match, 4),
        novelty=round(novelty, 4),
        clarity=round(clarity, 4),
        distractor_quality=round(distractor_quality, 4),
        source_grounding=round(source_grounding, 4),
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
    """Greedy highest-score selection with diversity penalties.

    Penalties discourage reusing the same concept, cognitive skill, wording
    pattern, page, or true/false polarity, so the final quiz stays varied
    while still favouring high-quality questions.
    """
    pool = list(candidates)
    pool.sort(key=lambda c: c.score, reverse=True)

    selected: list[AIQuizQuestion] = []
    seen_concepts: set[str] = set()
    seen_pages: dict[int, int] = {}
    skill_counts: dict[str, int] = {}
    pattern_counts: dict[str, int] = {}
    true_count = 0
    false_count = 0

    while pool and len(selected) < count:
        best_index = -1
        best_score = float("-inf")
        for i, candidate in enumerate(pool):
            penalty = 0.0
            penalty += 0.35 * skill_counts.get(candidate.skill, 0)
            penalty += 0.20 * pattern_counts.get(candidate.pattern, 0)
            if candidate.concept in seen_concepts:
                penalty += 0.45
            for page in candidate.question.source_pages:
                penalty += 0.06 * seen_pages.get(page, 0)
            if candidate.question.type == "true-false":
                answer = candidate.question.correct_answer.strip().lower()
                is_true = answer in {"true", "صح", "صحيح"}
                if is_true:
                    if true_count > false_count:
                        penalty += 0.35
                elif false_count >= true_count:
                    penalty += 0.35
            # Small deterministic jitter so equal scores don't always pick
            # the first candidate, but the same seed always picks the same set.
            jitter = rng.random() * 0.08
            adjusted = candidate.score - penalty + jitter
            if adjusted > best_score:
                best_score = adjusted
                best_index = i

        chosen = pool.pop(best_index)
        question = chosen.question
        selected.append(question)
        seen_concepts.add(chosen.concept)
        skill_counts[chosen.skill] = skill_counts.get(chosen.skill, 0) + 1
        pattern_counts[chosen.pattern] = pattern_counts.get(chosen.pattern, 0) + 1
        for page in question.source_pages:
            seen_pages[page] = seen_pages.get(page, 0) + 1
        if question.type == "true-false":
            answer = question.correct_answer.strip().lower()
            if answer in {"true", "صح", "صحيح"}:
                true_count += 1
            else:
                false_count += 1

    return selected
