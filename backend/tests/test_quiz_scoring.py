"""Tests for candidate scoring, de-duplication, and seeded selection."""

from __future__ import annotations

import random

from app.schemas.ai import AIQuizQuestion
from app.services.quiz_concepts import Concept
from app.services.quiz_scoring import (
    ScoredCandidate,
    classify_cognitive_skill,
    classify_pattern,
    content_jaccard,
    duplicates_within,
    is_repeat_of_history,
    is_semantic_duplicate,
    is_trivial_question,
    randomize_answer_positions,
    score_candidate,
    select_diverse,
    semantic_similarity,
)

VOCAB = {
    "photosynthesis", "light", "energy", "chemical", "glucose", "oxygen",
    "water", "chlorophyll", "calvin", "cycle", "atp", "nadph", "co2",
    "carbon", "dioxide", "plant", "plants", "reaction", "reactions",
}

PAGE_TEXT = {
    1: "Photosynthesis converts light energy into chemical energy stored in glucose.",
    2: "The light reactions produce ATP, NADPH, and oxygen from water and chlorophyll.",
    3: "The Calvin cycle fixes carbon dioxide into glucose using ATP and NADPH.",
}

CONCEPTS = [
    Concept(name="Photosynthesis", kind="definition", pages=[1], evidence="Photosynthesis converts light energy into chemical energy.", importance=0.85, reasons=["explicit definition"]),
    Concept(name="Light Reactions", kind="process", pages=[2, 3], evidence="The light reactions produce ATP and NADPH.", importance=0.70, reasons=["process/mechanism"]),
    Concept(name="Calvin Cycle", kind="process", pages=[3], evidence="The Calvin cycle fixes carbon dioxide into glucose.", importance=0.65, reasons=["process/mechanism"]),
    Concept(name="Cellular Respiration", kind="definition", pages=[1], evidence="Cellular respiration releases energy from glucose.", importance=0.60, reasons=["explicit definition"]),
]


def make_question(
    *,
    qtype: str = "mcq",
    prompt: str = "What is photosynthesis?",
    options: list[str] | None = None,
    correct: str = "Photosynthesis",
    explanation: str = "Photosynthesis is defined in the source as the conversion of light energy into chemical energy.",
    difficulty: str = "medium",
    pages: list[int] | None = None,
    id: str = "q1",
) -> AIQuizQuestion:
    if options is None:
        options = ["Photosynthesis", "Glycolysis", "Diffusion", "Osmosis"]
    return AIQuizQuestion(
        id=id,
        type=qtype,  # type: ignore[arg-type]
        prompt=prompt,
        options=options,
        correct_answer=correct,
        explanation=explanation,
        difficulty=difficulty,  # type: ignore[arg-type]
        source_pages=pages or [1],
    )


def scoring_kwargs(**overrides):
    base = dict(
        concepts=CONCEPTS,
        vocab=VOCAB,
        page_text=PAGE_TEXT,
        included_pages={1, 2, 3},
        requested_difficulty="mixed",
        history=[],
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Duplicate detection
# --------------------------------------------------------------------------- #


def test_exact_duplicate_detection() -> None:
    assert is_semantic_duplicate("What is photosynthesis?", "what is  photosynthesis ?")


def test_paraphrase_duplicate_purpose_vs_function() -> None:
    assert is_semantic_duplicate(
        "What is the main purpose of photosynthesis?",
        "What is the primary function of photosynthesis?",
    )
    assert semantic_similarity(
        "What is the main purpose of photosynthesis?",
        "What is the primary function of photosynthesis?",
    ) >= 0.6


def test_paraphrase_duplicate_does_not_collapse_different_questions() -> None:
    assert not is_semantic_duplicate(
        "What is the main purpose of photosynthesis?",
        "Which environmental condition most directly affects photosynthesis?",
    )


def test_definition_questions_are_paraphrases() -> None:
    assert is_semantic_duplicate("What is photosynthesis?", "Define photosynthesis.")


def test_different_cognitive_skills_are_not_duplicates() -> None:
    # Same content token, different cognitive intent — must NOT merge.
    assert not is_semantic_duplicate(
        "What is photosynthesis?", "How does photosynthesis work?"
    )


def test_arabic_paraphrase_detection() -> None:
    assert is_semantic_duplicate(
        "ما هي وظيفة البناء الضوئي؟", "ما هو دور البناء الضوئي؟"
    )


def test_duplicates_within_keeps_first_occurrence() -> None:
    q1 = make_question(prompt="What is the main purpose of photosynthesis?", correct="To convert light to chemical energy", options=["To convert light to chemical energy", "To produce glucose only", "To release oxygen", "To store ATP"], id="a")
    q2 = make_question(prompt="What is the primary function of photosynthesis?", correct="To convert light to chemical energy", options=["To convert light to chemical energy", "To produce glucose only", "To release oxygen", "To store ATP"], id="b")
    q3 = make_question(prompt="Which environmental condition most directly affects photosynthesis?", correct="Light intensity", options=["Light intensity", "Wind speed", "Soil color", "Air humidity"], id="c")
    kept = duplicates_within([q1, q2, q3])
    assert [q.id for q in kept] == ["a", "c"]


def test_previous_question_filtering() -> None:
    history = ["What is the main purpose of photosynthesis?"]
    assert is_repeat_of_history(
        make_question(prompt="What is the primary function of photosynthesis?"), history
    )
    assert not is_repeat_of_history(
        make_question(prompt="Which environmental condition most directly affects photosynthesis?"),
        history,
    )


# --------------------------------------------------------------------------- #
# Cognitive-skill and wording-pattern classification
# --------------------------------------------------------------------------- #


def test_cognitive_skill_classification() -> None:
    cases = {
        "What is photosynthesis?": "factual_recall",
        "Why does chlorophyll absorb light?": "cause_effect",
        "How does the Calvin cycle differ from the light reactions?": "comparison",
        "Which step occurs next after carbon fixation?": "process_order",
        "What would happen if light intensity increased?": "application",
        "What is the main purpose of photosynthesis?": "understanding",
        "Which statement about photosynthesis is incorrect?": "misconception",
        "Which scenario demonstrates the Calvin cycle?": "application",
    }
    for prompt, expected in cases.items():
        assert classify_cognitive_skill(prompt) == expected, f"{prompt!r} -> {classify_cognitive_skill(prompt)!r}"


def test_arabic_cognitive_skill_classification() -> None:
    assert classify_cognitive_skill("لماذا يمتص الكلوروفيل الضوء؟") == "cause_effect"
    assert classify_cognitive_skill("ما هي وظيفة البناء الضوئي؟") == "understanding"
    assert classify_cognitive_skill("قارن بين التنفس الخلوي والبناء الضوئي.") == "comparison"


def test_wording_pattern_classification() -> None:
    assert classify_pattern("What is photosynthesis?") == "definition"
    assert classify_pattern("Why does photosynthesis produce oxygen?") == "why_reason"
    assert classify_pattern("Which statement best explains photosynthesis?") == "which_statement"
    assert classify_pattern("Which statement is incorrect?") == "incorrect"
    assert classify_pattern("How does X differ from Y?") == "comparison"
    assert classify_pattern("What is the main purpose of X?") == "purpose"


# --------------------------------------------------------------------------- #
# Quality scoring
# --------------------------------------------------------------------------- #


def test_relevance_scoring_prefers_on_topic_questions() -> None:
    on_topic = make_question(prompt="What is photosynthesis?", correct="Photosynthesis", options=["Photosynthesis", "Glycolysis", "Diffusion", "Osmosis"])
    off_topic = make_question(prompt="What is the capital of France?", correct="Paris", options=["Paris", "Berlin", "Madrid", "Rome"])
    a = score_candidate(on_topic, **scoring_kwargs())
    b = score_candidate(off_topic, **scoring_kwargs())
    assert a.relevance > b.relevance


def test_educational_value_prefers_specific_explained_questions() -> None:
    good = make_question(
        explanation="Photosynthesis converts light energy into chemical energy using chlorophyll in the chloroplasts of plant cells.",
    )
    weak = make_question(explanation="Because it is important.")
    a = score_candidate(good, **scoring_kwargs())
    b = score_candidate(weak, **scoring_kwargs())
    assert a.educational_value > b.educational_value


def test_difficulty_scoring_match_and_mismatch() -> None:
    matched = score_candidate(make_question(difficulty="hard"), **scoring_kwargs(requested_difficulty="hard"))
    easy = score_candidate(make_question(difficulty="easy"), **scoring_kwargs(requested_difficulty="hard"))
    mixed = score_candidate(make_question(difficulty="hard"), **scoring_kwargs(requested_difficulty="mixed"))
    assert matched.difficulty_match == 1.0
    assert easy.difficulty_match < matched.difficulty_match
    assert mixed.difficulty_match == 1.0


def test_distractor_quality_prefers_plausible_grounded_distractors() -> None:
    plausible = make_question(
        prompt="Which molecule do the light reactions produce?",
        correct="Oxygen",
        options=["Oxygen", "Glucose", "Water", "ATP"],
    )
    absurd = make_question(
        prompt="Which molecule do the light reactions produce?",
        correct="Oxygen",
        options=["Oxygen", "banana", "purple elephant", "zzzz"],
    )
    a = score_candidate(plausible, **scoring_kwargs())
    b = score_candidate(absurd, **scoring_kwargs())
    assert a.distractor_quality > b.distractor_quality


def test_source_grounding_penalizes_out_of_scope_pages() -> None:
    in_scope = make_question(pages=[1])
    out_of_scope = make_question(pages=[99])
    a = score_candidate(in_scope, **scoring_kwargs())
    b = score_candidate(out_of_scope, **scoring_kwargs())
    assert a.source_grounding > b.source_grounding


def test_trivial_question_rejection() -> None:
    assert is_trivial_question("What page is the ISBN printed on?")
    assert is_trivial_question("How many words are in this document?")
    assert is_trivial_question("What is the copyright year of this book?")
    assert not is_trivial_question("What is photosynthesis?")


# --------------------------------------------------------------------------- #
# Selection, determinism, and randomization
# --------------------------------------------------------------------------- #


def _scored(q: AIQuizQuestion, score: float, skill: str | None = None, pattern: str | None = None) -> ScoredCandidate:
    return ScoredCandidate(
        question=q,
        score=score,
        concept="Photosynthesis",
        skill=skill or classify_cognitive_skill(q.prompt),
        pattern=pattern or classify_pattern(q.prompt),
    )


def test_select_diverse_is_deterministic_for_a_seed() -> None:
    candidates = [_scored(make_question(prompt=p, id=str(i)), score=0.7 - i * 0.01) for i, p in enumerate([
        "What is photosynthesis?",
        "Why does chlorophyll absorb light?",
        "How does the Calvin cycle differ from the light reactions?",
        "Which step occurs next after carbon fixation?",
        "What would happen if light intensity increased?",
    ])]
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    a = select_diverse(list(candidates), 3, rng=rng1)
    b = select_diverse(list(candidates), 3, rng=rng2)
    assert [q.id for q in a] == [q.id for q in b]


def test_select_diverse_spreads_cognitive_skills() -> None:
    candidates = []
    prompts = [
        "What is photosynthesis?",
        "Define chlorophyll.",
        "What is glucose?",
        "Which statement about photosynthesis is incorrect?",
        "Why does chlorophyll absorb light?",
        "How does the Calvin cycle differ from the light reactions?",
    ]
    for i, p in enumerate(prompts):
        candidates.append(_scored(make_question(prompt=p, id=str(i)), score=0.8))
    rng = random.Random(7)
    selected = select_diverse(candidates, 4, rng=rng)
    skills = {classify_cognitive_skill(q.prompt) for q in selected}
    assert len(selected) == 4
    assert len(skills) >= 3


def test_answer_position_randomization_is_seeded() -> None:
    question = make_question(options=["Alpha", "Beta", "Gamma", "Delta"], correct="Alpha")
    rng_a = random.Random(1)
    rng_b = random.Random(1)
    rng_c = random.Random(2)
    shuffled_a = randomize_answer_positions(question.model_copy(deep=True), rng_a)
    shuffled_b = randomize_answer_positions(question.model_copy(deep=True), rng_b)
    shuffled_c = randomize_answer_positions(question.model_copy(deep=True), rng_c)
    assert shuffled_a.options == shuffled_b.options  # same seed → same order
    assert shuffled_a.options != shuffled_c.options  # different seed → different order
    assert shuffled_a.correct_answer == "Alpha"  # correct answer value unchanged


def test_content_jaccard_bounds() -> None:
    assert content_jaccard("photosynthesis", "photosynthesis") == 1.0
    assert content_jaccard("photosynthesis", "mountain") == 0.0
