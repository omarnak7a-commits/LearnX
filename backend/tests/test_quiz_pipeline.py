"""End-to-end tests for the understanding-first quiz pipeline (with a fake LLM)."""

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
    build_candidate_prompt,
    generate_quiz,
    normalize_candidate,
    quiz_language_guidance,
)
from tests.quiz_fakes import (  # noqa: F401  (re-exported for other test modules)
    FakeCompletion,
    FakeQuizService,
    default_kwargs,
    make_pool,
    raw,
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


def test_writer_prompt_carries_the_study_map_not_raw_pages() -> None:
    from app.services.quiz_blueprints import build_question_blueprints
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import build_quiz_context
    from app.services.quiz_understanding import deterministic_understanding

    context = build_quiz_context(BIOLOGY_SOURCE)
    understanding = deterministic_understanding(context.units, title="Biology Chapter")
    targets = build_knowledge_targets(understanding)
    blueprints = build_question_blueprints(
        targets, count=6, question_types=["mcq"], difficulty="medium", seed=1
    )
    prompt = build_candidate_prompt(
        understanding=understanding,
        blueprints=blueprints,
        knowledge_targets=targets,
        count=6,
        candidate_count=24,
        kind="practice",
        difficulty="medium",
        previous_questions=["What is the main purpose of photosynthesis?"],
    )

    assert "DOCUMENT UNDERSTANDING" in prompt
    assert "KNOWLEDGE TARGETS" in prompt
    assert "QUIZ BLUEPRINT" in prompt
    assert "Write exactly 24" in prompt
    assert "photosynthesis" in prompt.lower()
    assert "PREVIOUS QUESTIONS" in prompt
    assert "What is the main purpose of photosynthesis?" in prompt


def test_prompt_forbids_metadata_and_sentence_copying() -> None:
    from app.services.quiz_blueprints import build_question_blueprints
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import build_quiz_context
    from app.services.quiz_understanding import deterministic_understanding

    context = build_quiz_context(BIOLOGY_SOURCE)
    understanding = deterministic_understanding(context.units, title="Biology Chapter")
    targets = build_knowledge_targets(understanding)
    prompt = build_candidate_prompt(
        understanding=understanding,
        blueprints=build_question_blueprints(
            targets, count=6, question_types=["mcq"], difficulty="medium", seed=1
        ),
        knowledge_targets=targets,
        count=6,
        candidate_count=24,
        kind="practice",
        difficulty="medium",
        previous_questions=[],
    )
    lowered = prompt.lower()
    assert "copyright" in lowered
    assert "isbn" in lowered
    assert "page furniture" in lowered
    assert "never simply restate a source sentence" in lowered


# --------------------------------------------------------------------------- #
# End-to-end generation
# --------------------------------------------------------------------------- #


def test_end_to_end_generation_selects_and_spreads_pages() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen from water", "To store water in the leaves", "To release carbon dioxide"], source_pages=[1], explanation="The source defines photosynthesis as the process that converts light energy into chemical energy."),
        dict(id="b", prompt="Which molecule do the light reactions produce as a byproduct?", correct_answer="Oxygen", options=["Oxygen", "Glucose", "Water", "Carbon dioxide"], source_pages=[2], explanation="The light reactions split water molecules and produce oxygen as a byproduct."),
        dict(id="c", prompt="Why does the Calvin cycle not require light directly?", correct_answer="It uses ATP and NADPH", options=["It uses ATP and NADPH", "It uses chlorophyll", "It produces oxygen", "It splits water"], source_pages=[3], explanation="The source states the Calvin cycle uses ATP and NADPH produced by the light reactions."),
        dict(id="e", prompt="Which gas is produced during photosynthesis?", correct_answer="Oxygen", options=["Oxygen", "Carbon dioxide", "Water", "Glucose"], source_pages=[1], explanation="Photosynthesis produces glucose and oxygen according to the source."),
        dict(id="g", prompt="What would happen if light intensity increased?", correct_answer="The rate of photosynthesis would rise", options=["The rate of photosynthesis would rise", "Photosynthesis would stop", "Chlorophyll would disappear", "Plants would release carbon dioxide"], source_pages=[4], explanation="The source states the rate increases with light intensity up to a saturation point."),
    ])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=4))

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
    ])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=3))
    prompts = [q.prompt.lower() for q in result.questions]
    assert not (
        "what is the main purpose of photosynthesis?" in prompts
        and "what is the primary function of photosynthesis?" in prompts
    )


def test_pipeline_filters_previous_questions() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy", options=["To convert light energy into chemical energy", "To produce oxygen", "To store water", "To release carbon dioxide"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
    ])
    result = generate_quiz(
        FakeQuizService(pool), BIOLOGY_SOURCE,
        **default_kwargs(count=2, previous_questions=["What is the primary function of photosynthesis?"]),
    )
    prompts = [q.prompt.lower() for q in result.questions]
    assert "what is the main purpose of photosynthesis?" not in prompts


def test_pipeline_seed_determinism() -> None:
    a = generate_quiz(FakeQuizService(), BIOLOGY_SOURCE, **default_kwargs(count=3, seed=123))
    b = generate_quiz(FakeQuizService(), BIOLOGY_SOURCE, **default_kwargs(count=3, seed=123))
    assert [(q.prompt, q.options) for q in a.questions] == [
        (q.prompt, q.options) for q in b.questions
    ]


def test_pipeline_different_seeds_produce_different_valid_quizzes() -> None:
    kwargs = default_kwargs(count=3, question_types=["mcq", "true-false", "short-answer"])
    a = generate_quiz(FakeQuizService(), BIOLOGY_SOURCE, **{**kwargs, "seed": 11})
    b = generate_quiz(FakeQuizService(), BIOLOGY_SOURCE, **{**kwargs, "seed": 22})
    assert [(q.prompt, q.options) for q in a.questions] != [
        (q.prompt, q.options) for q in b.questions
    ]
    # Both remain fully valid and source-grounded.
    for result in (a, b):
        assert result.questions
        for question in result.questions:
            assert question.source_pages


def test_insufficient_candidates_is_never_padded() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=["Photosynthesis", "Glucose", "Oxygen", "Water"], source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
    ])
    result = generate_quiz(
        FakeQuizService(pool),
        BIOLOGY_SOURCE,
        **default_kwargs(count=20, question_types=["mcq"]),
    )
    assert len(result.questions) < 20


def test_metadata_only_candidates_yield_the_unavailable_state() -> None:
    """Trivia prose is rejected, and no weak filler is substituted for it."""
    pool = make_pool([
        dict(id="a", prompt="What page is the ISBN on?", source_pages=[1]),
        dict(id="b", prompt="How many words?", source_pages=[1]),
    ])

    class MetadataOnlyService(FakeQuizService):
        """A provider that only ever returns trivia, with no writer fallback."""

        def _write_from_blueprints(self, plan):
            from app.services.quiz_pipeline import _RawQuizPool

            return _RawQuizPool(questions=[])

    service = MetadataOnlyService(pool)
    # The deterministic writer is the only remaining path; disable it to prove
    # the pipeline reports unavailability rather than degrading.
    import app.services.quiz_pipeline as pipeline

    original = pipeline.deterministic_candidates
    pipeline.deterministic_candidates = lambda *args, **kwargs: []
    try:
        with pytest.raises(AIUnavailableError):
            generate_quiz(service, BIOLOGY_SOURCE, **default_kwargs())
    finally:
        pipeline.deterministic_candidates = original


def test_empty_source_raises_gracefully() -> None:
    empty = AIDocumentSource(file_id=None, title="Empty", text="", page_count=0)
    with pytest.raises(AIUnavailableError):
        generate_quiz(FakeQuizService(make_pool([dict()])), empty, **default_kwargs())


# --------------------------------------------------------------------------- #
# Language behaviour
# --------------------------------------------------------------------------- #


def test_arabic_generation_and_language_guidance() -> None:
    # The source teaches two equally important concepts, one per page, so which
    # one the planner picks for a one-question quiz is a legitimate seed
    # choice. Offer a candidate for each rather than assuming a winner.
    pool = make_pool([
        dict(id="a", type="mcq", prompt="ما هي وظيفة البناء الضوئي؟", correct_answer="تحويل الطاقة الضوئية إلى طاقة كيميائية", options=["تحويل الطاقة الضوئية إلى طاقة كيميائية", "تحويل الطاقة الكيميائية إلى طاقة ضوئية", "تخزين الطاقة الضوئية في النباتات", "إطلاق الطاقة الكيميائية من النباتات"], explanation="البناء الضوئي يحول الطاقة الضوئية إلى طاقة كيميائية.", source_pages=[1]),
        dict(id="b", type="mcq", prompt="ما هي وظيفة التنفس الخلوي؟", correct_answer="إطلاق الطاقة من الجلوكوز", options=["إطلاق الطاقة من الجلوكوز", "تخزين الطاقة في الجلوكوز", "تحويل الطاقة الضوئية إلى جلوكوز", "نقل الجلوكوز داخل الخلية"], explanation="التنفس الخلوي هو العملية التي تطلق الطاقة من الجلوكوز.", source_pages=[2]),
    ])
    service = FakeQuizService(pool)
    result = generate_quiz(service, ARABIC_SOURCE, **default_kwargs(count=1, language="ar"))
    assert len(result.questions) == 1
    assert any("\u0600" <= ch <= "\u06FF" for ch in result.questions[0].prompt)
    system_prompt = service.calls[0]["system_prompt"]
    assert "العربية" in system_prompt or "الأسئلة" in system_prompt


def test_english_generation() -> None:
    service = FakeQuizService()
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
    source = source_from_text(
        "[Page 1]\nPhotosynthesis is defined as the process that converts light into chemical energy.\n\n"
        "[Page 2]\nThe light reactions produce ATP and NADPH for the Calvin cycle.\n"
    )
    result = generate_quiz(
        FakeQuizService(),
        source,
        **default_kwargs(count=4, question_types=["short-answer", "fill-blank", "true-false"]),
    )
    assert result.questions
    for question in result.questions:
        assert set(question.source_pages) <= {1, 2}


def test_pipeline_returns_provider_metadata() -> None:
    result = generate_quiz(FakeQuizService(), BIOLOGY_SOURCE, **default_kwargs(count=2))
    assert result.provider == "gemini"
    assert result.model == "gemini-test"
    assert result.fallback_used is False


def test_quiz_endpoint_preserves_frontend_contract() -> None:
    """POST /api/v1/ai/quiz must keep returning the exact frontend shape."""
    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_ai_service] = FakeQuizService
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
                    "sourceText": (
                        "Photosynthesis is defined as the process by which plants convert "
                        "light energy into chemical energy stored in glucose."
                    ),
                    "count": 1,
                    "questionTypes": ["mcq", "true-false", "fill-blank", "short-answer"],
                    "seed": 5,
                    "previousQuestions": ["How do roots absorb water?"],
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert set(body) == {"provider", "model", "fallbackUsed", "questions"}
            assert len(body["questions"]) == 1
            question = body["questions"][0]
            assert set(question) == {
                "id", "type", "prompt", "options", "correctAnswer",
                "explanation", "difficulty", "sourcePages",
            }
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Boilerplate regression: candidates and source must never carry PDF chrome
# --------------------------------------------------------------------------- #


def test_normalize_candidate_rejects_copyright_candidate() -> None:
    question = normalize_candidate(
        raw(
            type="fill-blank",
            prompt="Copyright © 2020, _____ and/or its affiliates.",
            correct_answer="Oracle",
            options=None,
            explanation="The footer of every page contains this notice.",
        ),
        index=0, allowed_types={"fill-blank"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_normalize_candidate_rejects_boilerplate_options() -> None:
    question = normalize_candidate(
        raw(
            prompt="What is photosynthesis?",
            options=["Photosynthesis", "Visit https://example.com for details", "Oxygen", "Water"],
            correct_answer="Photosynthesis",
        ),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_normalize_candidate_rejects_boilerplate_explanation() -> None:
    question = normalize_candidate(
        raw(
            prompt="What is photosynthesis?",
            explanation="See page 3 of 12 of the publisher's manual.",
        ),
        index=0, allowed_types={"mcq"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_normalize_candidate_requires_fill_blank_marker() -> None:
    question = normalize_candidate(
        raw(type="fill-blank", prompt="What is photosynthesis?", correct_answer="Photosynthesis", options=None),
        index=0, allowed_types={"fill-blank"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_normalize_candidate_rejects_boilerplate_fill_blank_answer() -> None:
    question = normalize_candidate(
        raw(type="fill-blank", prompt="The notice on every page reads _____.", correct_answer="All rights reserved", options=None),
        index=0, allowed_types={"fill-blank"}, page_count=4, included_pages={1, 2, 3, 4},
    )
    assert question is None


def test_understanding_never_sees_footer_text() -> None:
    source = AIDocumentSource(
        file_id=None,
        title="DB Notes",
        text=(
            "[Page 1]\n"
            "Oracle Database Documentation\n"
            "A database is defined as an organized collection of structured data.\n"
            "\n"
            "[Page 2]\n"
            "Oracle Database Documentation\n"
            "A table is defined as a set of rows that share the same columns.\n"
            "\n"
            "[Page 3]\n"
            "Oracle Database Documentation\n"
            "Copyright © 2020, Oracle and/or its affiliates. All rights reserved.\n"
        ),
        page_count=3,
    )
    service = FakeQuizService()
    generate_quiz(service, source, **default_kwargs(count=2, question_types=["mcq", "short-answer"]))
    understanding_prompt = service.calls[0]["user_prompt"]
    assert "database is defined" in understanding_prompt
    assert "Copyright © 2020" not in understanding_prompt
    assert "Oracle Database Documentation" not in understanding_prompt


def test_end_to_end_filters_boilerplate_candidates_from_pool() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy",
             options=["To convert light energy into chemical energy", "To produce oxygen only", "To store water", "To release carbon dioxide"],
             source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", type="fill-blank", prompt="Copyright © 2020, _____ and/or its affiliates.", correct_answer="Oracle",
             options=None, source_pages=[1], explanation="The footer of every page contains this notice."),
    ])
    result = generate_quiz(FakeQuizService(pool), BIOLOGY_SOURCE, **default_kwargs(count=4))
    prompts = " | ".join(q.prompt for q in result.questions)
    assert "Copyright" not in prompts
    assert "and/or its affiliates" not in prompts
    for q in result.questions:
        assert "©" not in q.prompt + q.correct_answer + q.explanation
        assert all("©" not in (o or "") for o in (q.options or []))


def test_all_boilerplate_source_raises_ai_unavailable() -> None:
    boilerplate = AIDocumentSource(
        file_id=None,
        title="Legal",
        text=(
            "[Page 1]\nCopyright © 2020, Oracle and/or its affiliates. All rights reserved.\n"
            "[Page 2]\nAll rights reserved.\nPrinted in the USA.\n"
        ),
        page_count=2,
    )
    with pytest.raises(AIUnavailableError):
        generate_quiz(FakeQuizService(make_pool([dict(id="a", source_pages=[1])])), boilerplate, **default_kwargs(count=1))
