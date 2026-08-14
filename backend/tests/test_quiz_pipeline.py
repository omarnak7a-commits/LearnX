"""End-to-end tests for the quiz generation pipeline (with a fake LLM)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.services.ai_documents import AIDocumentSource, source_from_text
from app.services.ai_service import AIUnavailableError, get_ai_service
from app.services.quiz_pipeline import (
    QuizGenerationResult,
    _RawCandidate,
    _RawQuizPool,
    build_candidate_prompt,
    generate_quiz,
    normalize_candidate,
    quiz_language_guidance,
)

BIOLOGY_SOURCE = source_from_text(
    """[Page 1]
1.1 Introduction to Photosynthesis
Photosynthesis is defined as the process by which green plants convert light energy into chemical energy. This process takes place in the chloroplasts of plant cells. Photosynthesis produces glucose and oxygen.

[Page 2]
2.1 The Light Reactions
The light reactions occur in the thylakoid membranes. Chlorophyll absorbs light energy and splits water molecules, producing oxygen as a byproduct. The light reactions produce ATP and NADPH.

[Page 3]
3.1 The Calvin Cycle
The Calvin cycle is the set of reactions that fix carbon dioxide into glucose. Unlike the light reactions, the Calvin cycle does not require light directly. The relationship between the light reactions and the Calvin cycle is that the products of one fuel the other.

[Page 4]
4.1 Factors Affecting Photosynthesis
Light intensity, carbon dioxide concentration, and temperature all affect the rate of photosynthesis. If light intensity increases, the rate of photosynthesis increases up to a saturation point.
""",
    title="Biology Chapter",
)

ARABIC_SOURCE = source_from_text(
    """[Page 1]
الفصل الأول: البناء الضوئي
البناء الضوئي هو العملية التي تحول بها النباتات الطاقة الضوئية إلى طاقة كيميائية.

[Page 2]
القسم الثاني: التنفس الخلوي
التنفس الخلوي هو العملية التي تطلق الطاقة من الجلوكوز.
""",
    title="مادة الأحياء",
)


class FakeCompletion:
    def __init__(self, value, provider="gemini", model="gemini-test", fallback_used=False):
        self.value = value
        self.provider = provider
        self.model = model
        self.fallback_used = fallback_used


class FakeQuizService:
    def __init__(self, pool: _RawQuizPool):
        self.pool = pool
        self.calls: list[dict] = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        return FakeCompletion(self.pool)


def raw(**kwargs) -> _RawCandidate:
    # Defaults are fully source-grounded so minimal overrides stay valid.
    defaults = dict(
        id="q",
        type="mcq",
        prompt="What is photosynthesis?",
        options=["Photosynthesis", "Glucose", "Oxygen", "Water"],
        correct_answer="Photosynthesis",
        explanation="The source defines photosynthesis as the conversion of light energy into chemical energy.",
        difficulty="medium",
        source_pages=[1],
    )
    defaults.update(kwargs)
    return _RawCandidate(**defaults)


def make_pool(candidates: list[dict]) -> _RawQuizPool:
    return _RawQuizPool(questions=[raw(**c) for c in candidates])


def default_kwargs(**overrides) -> dict:
    base = dict(
        count=4,
        question_types=["mcq", "true-false", "fill-blank", "short-answer"],
        difficulty="mixed",
        kind="practice",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="You are LearnX.",
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Candidate normalization
# --------------------------------------------------------------------------- #


def test_normalize_candidate_repairs_type_aliases() -> None:
    question = normalize_candidate(
        raw(type="multiple choice"),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is not None and question.type == "mcq"


def test_normalize_candidate_true_false_polarity() -> None:
    question = normalize_candidate(
        raw(type="true-false", prompt="Plants produce oxygen.", options=["True", "False"], correct_answer="False", source_pages=[2]),
        index=0, allowed_types={"true-false"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is not None
    assert question.type == "true-false"
    assert question.options == ["True", "False"]
    assert question.correct_answer == "False"


def test_normalize_candidate_appends_missing_correct_option() -> None:
    question = normalize_candidate(
        raw(options=["Glucose", "Oxygen", "Water"], correct_answer="Photosynthesis"),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is not None
    assert any(o.casefold() == "photosynthesis" for o in question.options or [])


def test_normalize_candidate_rejects_out_of_scope_pages() -> None:
    question = normalize_candidate(
        raw(source_pages=[99]),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_normalize_candidate_rejects_trivial_questions() -> None:
    question = normalize_candidate(
        raw(prompt="What page is the ISBN printed on?"),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #


def test_prompt_includes_concept_map_and_overgeneration() -> None:
    from app.services.quiz_concepts import build_concept_map, split_source_units
    concepts = build_concept_map(split_source_units(BIOLOGY_SOURCE.text))
    prompt = build_candidate_prompt(
        source=BIOLOGY_SOURCE, concepts=concepts, count=6, candidate_count=24,
        question_types=["mcq"], difficulty="medium", kind="practice", language="en",
        previous_questions=["What is the main purpose of photosynthesis?"],
    )
    assert "CONCEPT MAP" in prompt
    assert "Photosynthesis" in prompt or "photosynthesis" in prompt
    assert "Generate exactly 24" in prompt
    assert "PREVIOUS QUESTIONS" in prompt
    assert "What is the main purpose of photosynthesis?" in prompt


# --------------------------------------------------------------------------- #
# End-to-end generation
# --------------------------------------------------------------------------- #

def test_end_to_end_generation_selects_and_spreads_pages() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen from water", "To store water in the leaves", "To release carbon dioxide"], source_pages=[1], explanation="The source defines photosynthesis as the process that converts light energy into chemical energy."),
        dict(id="b", prompt="Which molecule do the light reactions produce as a byproduct?", correct_answer="Oxygen", options=["Oxygen", "Glucose", "Water", "Carbon dioxide"], source_pages=[2], explanation="The light reactions split water molecules and produce oxygen as a byproduct."),
        dict(id="c", prompt="Why does the Calvin cycle not require light directly?", correct_answer="It uses ATP and NADPH", options=["It uses ATP and NADPH", "It uses chlorophyll", "It produces oxygen", "It splits water"], source_pages=[3], explanation="The source states the Calvin cycle uses ATP and NADPH produced by the light reactions."),
        dict(id="d", prompt="How do the light reactions and the Calvin cycle relate?", correct_answer="The products of one fuel the other", options=["The products of one fuel the other", "They occur in the same place", "They both need light", "They both produce glucose"], source_pages=[3], explanation="The source says the products of one fuel the other."),
        dict(id="e", prompt="Which gas is produced during photosynthesis?", correct_answer="Oxygen", options=["Oxygen", "Carbon dioxide", "Water", "Glucose"], source_pages=[1], explanation="Photosynthesis produces glucose and oxygen according to the source."),
        dict(id="f", prompt="Which step occurs after the light reactions?", correct_answer="The Calvin cycle", options=["The Calvin cycle", "Water splitting", "Light absorption", "Oxygen release"], source_pages=[3], explanation="The Calvin cycle follows the light reactions."),
        dict(id="g", prompt="What would happen if light intensity increased?", correct_answer="The rate of photosynthesis would rise", options=["The rate of photosynthesis would rise", "Photosynthesis would stop", "Chlorophyll would disappear", "Plants would release carbon dioxide"], source_pages=[4], explanation="The source states the rate increases with light intensity up to a saturation point."),
        dict(id="h", prompt="Which statement about the Calvin cycle is incorrect?", correct_answer="It requires light directly", options=["It requires light directly", "It fixes carbon dioxide", "It uses ATP", "It produces glucose"], source_pages=[3], explanation="The Calvin cycle does not require light directly."),
    ])
    service = FakeQuizService(pool)
    result = generate_quiz(service, BIOLOGY_SOURCE, **default_kwargs(count=4))

    assert isinstance(result, QuizGenerationResult)
    assert 1 <= len(result.questions) <= 4
    ids = [q.id for q in result.questions]
    assert len(ids) == len(set(ids))
    for q in result.questions:
        assert q.type in {"mcq", "true-false", "fill-blank", "short-answer"}
        assert all(p in {1, 2, 3, 4} for p in q.source_pages)
        if q.options:
            assert any(o.casefold() == q.correct_answer.casefold() for o in q.options)
    pages = {p for q in result.questions for p in q.source_pages}
    assert len(pages) >= 2  # questions span more than one page


def test_pipeline_removes_paraphrase_duplicates() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen", "To store water", "To release carbon dioxide"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", prompt="What is the primary function of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen", "To store water", "To release carbon dioxide"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="c", prompt="Which environmental condition most directly affects photosynthesis?", correct_answer="Light intensity", options=["Light intensity", "Wind speed", "Soil color", "Humidity"], source_pages=[4], explanation="Light intensity directly affects the rate of photosynthesis."),
    ])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=3))
    prompts = [q.prompt.lower() for q in result.questions]
    assert "what is the main purpose of photosynthesis?" in prompts or "what is the primary function of photosynthesis?" in prompts
    assert not ("what is the main purpose of photosynthesis?" in prompts and "what is the primary function of photosynthesis?" in prompts)


def test_pipeline_filters_previous_questions() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen", "To store water", "To release carbon dioxide"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", prompt="Which environmental condition most directly affects photosynthesis?", correct_answer="Light intensity", options=["Light intensity", "Wind speed", "Soil color", "Humidity"], source_pages=[4], explanation="Light intensity directly affects the rate of photosynthesis."),
    ])
    result = generate_quiz(
        FakeQuizService(pool), BIOLOGY_SOURCE,
        **default_kwargs(count=2, previous_questions=["What is the primary function of photosynthesis?"]),
    )
    prompts = [q.prompt.lower() for q in result.questions]
    assert "what is the main purpose of photosynthesis?" not in prompts
    assert "which environmental condition most directly affects photosynthesis?" in prompts


def test_pipeline_seed_determinism() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light into chemical energy."),
        dict(id="b", prompt="Why does chlorophyll absorb light?", correct_answer="To drive electron transport", options=["To drive electron transport", "To cool the leaf", "To make sugar", "To store water"], source_pages=[2], explanation="Chlorophyll absorbs light energy to drive the light reactions."),
        dict(id="c", prompt="How do the light reactions and Calvin cycle relate?", correct_answer="Products of one fuel the other", options=["Products of one fuel the other", "They are identical", "They both split water", "They both fix carbon dioxide"], source_pages=[3], explanation="The products of one fuel the other."),
        dict(id="d", prompt="Which step occurs next after carbon fixation?", correct_answer="Reduction", options=["Reduction", "Light absorption", "Water splitting", "Oxygen release"], source_pages=[3], explanation="Reduction follows carbon fixation in the Calvin cycle."),
    ])
    a = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=3, seed=123))
    b = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=3, seed=123))
    assert [(q.id, q.options) for q in a.questions] == [(q.id, q.options) for q in b.questions]


def test_pipeline_different_seeds_vary_answer_order() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light into chemical energy."),
        dict(id="b", prompt="Why does chlorophyll absorb light?", correct_answer="To drive electron transport", options=["To drive electron transport", "To cool the leaf", "To make sugar", "To store water"], source_pages=[2], explanation="Chlorophyll absorbs light energy to drive the light reactions."),
        dict(id="c", prompt="How do the light reactions and Calvin cycle relate?", correct_answer="Products of one fuel the other", options=["Products of one fuel the other", "They are identical", "They both split water", "They both fix carbon dioxide"], source_pages=[3], explanation="The products of one fuel the other."),
    ])
    a = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=2, seed=11))
    b = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=2, seed=22))
    assert [(q.id, q.options) for q in a.questions] != [(q.id, q.options) for q in b.questions]


def test_insufficient_candidates_returns_best_subset() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", prompt="Which molecule do the light reactions produce as a byproduct?", correct_answer="Oxygen", options=["Oxygen", "Glucose", "Water", "Carbon dioxide"], source_pages=[2], explanation="The light reactions produce oxygen as a byproduct."),
    ])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=6))
    assert len(result.questions) == 2  # never padded with low-quality filler


def test_no_usable_candidates_raises() -> None:
    pool = make_pool([
        dict(id="a", prompt="What page is the ISBN on?", source_pages=[1]),
        dict(id="b", prompt="How many words?", source_pages=[1]),
    ])
    with pytest.raises(AIUnavailableError):
        generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs())


def test_empty_source_raises_gracefully() -> None:
    empty = AIDocumentSource(file_id=None, title="Empty", text="", page_count=0)
    with pytest.raises(AIUnavailableError):
        generate_quiz(FakeQuizService(make_pool([dict()])), empty, **default_kwargs())


# --------------------------------------------------------------------------- #
# Language behaviour
# --------------------------------------------------------------------------- #


def test_arabic_generation_and_language_guidance() -> None:
    pool = make_pool([
        dict(id="a", type="mcq", prompt="ما هي وظيفة البناء الضوئي؟", correct_answer="تحويل الطاقة الضوئية إلى طاقة كيميائية", options=["تحويل الطاقة الضوئية إلى طاقة كيميائية", "إطلاق الأكسجين فقط", "تخزين الماء", "إنتاج ثاني أكسيد الكربون"], explanation="البناء الضوئي يحول الطاقة الضوئية إلى طاقة كيميائية.", source_pages=[1]),
    ])
    service = FakeQuizService(pool)
    result = generate_quiz(service, ARABIC_SOURCE, **default_kwargs(count=1, language="ar"))
    assert len(result.questions) == 1
    assert any("\u0600" <= ch <= "\u06FF" for ch in result.questions[0].prompt)
    system_prompt = service.calls[0]["system_prompt"]
    assert "العربية" in system_prompt or "الأسئلة" in system_prompt


def test_english_generation() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
    ])
    service = FakeQuizService(pool)
    result = generate_quiz(service, BIOLOGY_SOURCE, **default_kwargs(count=1, language="en"))
    assert result.questions[0].prompt.isascii()
    assert "English" in service.calls[0]["system_prompt"]


def test_mixed_language_guidance_keeps_technical_terms() -> None:
    arabic = quiz_language_guidance("ar")
    assert "API" in arabic
    assert "Database" in arabic
    assert "Backend" in arabic
    english = quiz_language_guidance("en")
    assert "English" in english
    assert "API" in english


def test_allowed_pages_confine_citations() -> None:
    # The source text only contains pages 1 and 2 (allowed); a candidate
    # citing page 3 must be dropped.
    source = source_from_text(
        "[Page 1]\nPhotosynthesis converts light into chemical energy.\n\n"
        "[Page 2]\nThe light reactions produce ATP and NADPH.\n"
    )
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", prompt="Which reaction produces ATP?", correct_answer="The light reactions", options=["The light reactions", "The Calvin cycle", "Glycolysis", "The Krebs cycle"], source_pages=[3], explanation="The light reactions produce ATP."),
    ])
    result = generate_quiz(FakeQuizService(pool), source, **default_kwargs(count=2))
    assert all(q.id == "a" for q in result.questions)


def test_pipeline_returns_provider_metadata() -> None:
    pool = make_pool([dict(id="a", source_pages=[1])])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=1))
    assert result.provider == "gemini"
    assert result.model == "gemini-test"
    assert result.fallback_used is False


def test_quiz_endpoint_preserves_frontend_contract() -> None:
    """POST /api/v1/ai/quiz must keep returning the exact frontend shape."""
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis",
             options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1],
             explanation="Photosynthesis converts light energy into chemical energy."),
    ])

    class EndpointService:
        def complete_structured(self, **_kwargs):
            return FakeCompletion(pool)

    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_ai_service] = EndpointService
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        role="student",
        preferred_language="en",
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/quiz",
                json={
                    "sourceText": "Photosynthesis converts light energy into chemical energy.",
                    "count": 1,
                    "seed": 5,
                    "previousQuestions": ["What is the primary function of photosynthesis?"],
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["provider"] == "gemini"
            assert body["model"] == "gemini-test"
            assert body["fallbackUsed"] is False
            assert len(body["questions"]) == 1
            question = body["questions"][0]
            assert set(question) == {
                "id", "type", "prompt", "options", "correctAnswer",
                "explanation", "difficulty", "sourcePages",
            }
            assert question["correctAnswer"] == "Photosynthesis"
            assert "Photosynthesis" in question["options"]
    finally:
        app.dependency_overrides.clear()
