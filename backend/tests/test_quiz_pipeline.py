"""End-to-end tests for the quiz generation pipeline (with a fake LLM)."""

from __future__ import annotations

import ast
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.services.ai_documents import AIDocumentSource, source_from_text
from app.services.ai_service import AIUnavailableError, get_ai_service
from app.services.quiz_content_map import _RawContentItem, _RawContentMap
from app.services.quiz_pipeline import (
    QuizGenerationResult,
    _RawCandidate,
    _RawQuizPool,
    build_candidate_prompt,
    generate_quiz,
    normalize_candidate,
    quiz_language_guidance,
)
from app.services.quiz_scoring import classify_cognitive_skill, content_tokens

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
    """Two-stage fake: semantic planner first, provided writer pool second.

    Existing end-to-end fixtures specify the prose candidates that each test is
    interested in. The fake supplies the internal map/blueprint annotations a
    real structured provider now returns, without weakening production gates.
    """

    _BLUEPRINT_RE = re.compile(
        r"^- \[(?P<id>[^]]+)] concept=(?P<concept>.*?); category=.*?; "
        r"target=(?P<target>.*?); skill=(?P<skill>[^;]+); type=(?P<type>[^;]+); "
        r"difficulty=(?P<difficulty>[^;]+); pages=(?P<pages>\[[^]]*]); "
        r"VERBATIM EVIDENCE=(?P<evidence>.*)$"
    )

    def __init__(self, pool: _RawQuizPool):
        self.pool = pool
        self.calls: list[dict] = []

    def _map_from_prompt(self, prompt: str) -> _RawContentMap:
        source = prompt.split("CLEANED SOURCE:\n", 1)[-1]
        matches = list(re.finditer(r"\[Page\s+(\d+)]\s*", source))
        statements: list[tuple[int, str]] = []
        for page_index, match in enumerate(matches):
            page = int(match.group(1))
            end = matches[page_index + 1].start() if page_index + 1 < len(matches) else len(source)
            page_text = source[match.end():end]
            parts = re.split(r"(?<=[.!?؟])\s+|\n+", page_text)
            for sentence in parts:
                evidence = re.sub(r"\s+", " ", sentence).strip()
                if len(content_tokens(evidence)) >= 4:
                    statements.append((page, evidence))

        # Keep the map focused on the source ideas exercised by the prose
        # fixtures. This gives every legacy candidate a planned objective while
        # still passing through the real planner, normalizer, and score gates.
        selected: list[tuple[int, str]] = []
        for candidate in self.pool.questions:
            candidate_pages = {int(page) for page in candidate.source_pages if str(page).isdigit()}
            relevant = [item for item in statements if not candidate_pages or item[0] in candidate_pages]
            if not relevant:
                continue
            candidate_terms = content_tokens(
                f"{candidate.prompt} {candidate.correct_answer} {candidate.explanation}"
            )
            best = max(
                relevant,
                key=lambda item: len(candidate_terms & content_tokens(item[1]))
                / max(1, len(candidate_terms | content_tokens(item[1]))),
            )
            if best not in selected:
                selected.append(best)
        if not selected and statements:
            selected.append(statements[0])

        items: list[_RawContentItem] = []
        for page, evidence in selected:
            # The first meaningful source words are sufficient as a test
            # concept label; provider importance is still category-based.
            concept = " ".join(evidence.split()[: min(6, len(evidence.split()))]).strip(".: ")
            items.append(
                _RawContentItem(
                    id=f"item-{len(items) + 1}",
                    concept=concept,
                    category="core_concept",
                    importance="high",
                    knowledge_targets=[evidence],
                    source_quote=evidence,
                    source_pages=[page],
                    rationale="Central source statement used by the test fixture.",
                )
            )
        return _RawContentMap(items=items)

    @classmethod
    def _blueprints_from_prompt(cls, prompt: str) -> list[dict]:
        blueprints: list[dict] = []
        for line in prompt.splitlines():
            match = cls._BLUEPRINT_RE.match(line)
            if not match:
                continue
            values = match.groupdict()
            try:
                values["concept"] = ast.literal_eval(values["concept"])
                values["target"] = ast.literal_eval(values["target"])
                values["pages"] = ast.literal_eval(values["pages"])
                values["evidence"] = ast.literal_eval(values["evidence"])
            except (SyntaxError, ValueError):
                continue
            blueprints.append(values)
        return blueprints

    @classmethod
    def _annotate_pool(cls, pool: _RawQuizPool, prompt: str) -> _RawQuizPool:
        blueprints = cls._blueprints_from_prompt(prompt)
        questions: list[_RawCandidate] = []
        for candidate in pool.questions:
            qtype = candidate.type.strip().lower().replace("_", "-")
            if qtype in {"multiple-choice", "multiple choice"}:
                qtype = "mcq"
            if qtype in {"true/false", "tf"}:
                qtype = "true-false"
            candidate_pages = set(candidate.source_pages)
            candidate_tokens = content_tokens(
                f"{candidate.prompt} {candidate.correct_answer} {candidate.explanation}"
            )
            classified = classify_cognitive_skill(candidate.prompt)

            compatible = [
                blueprint
                for blueprint in blueprints
                if blueprint["type"] == qtype and candidate_pages.intersection(blueprint["pages"])
            ]
            if not compatible:
                compatible = [blueprint for blueprint in blueprints if blueprint["type"] == qtype]
            if not compatible:
                questions.append(candidate)
                continue

            def fit(blueprint: dict) -> tuple[float, float, float]:
                evidence_tokens = content_tokens(blueprint["evidence"])
                overlap = len(candidate_tokens & evidence_tokens) / max(1, len(candidate_tokens | evidence_tokens))
                skill_match = float(blueprint["skill"] == classified)
                shape_bound = {"application", "analysis", "comparison", "cause_effect", "process_order"}
                shape_compatible = float(
                    blueprint["skill"] not in shape_bound or blueprint["skill"] == classified
                )
                return shape_compatible, skill_match, overlap

            blueprint = max(compatible, key=fit)
            update = {
                "blueprint_id": blueprint["id"],
                "source_pages": [page for page in candidate.source_pages if page in blueprint["pages"]]
                or list(blueprint["pages"][:1]),
                "source_quote": blueprint["evidence"],
            }
            if qtype == "mcq":
                update["distractor_rationales"] = [
                    "Same-domain misconception contradicted by the exact source evidence."
                    for _ in range(3)
                ]
            if qtype == "true-false" and candidate.correct_answer.strip().casefold() == "false":
                update["false_statement_basis"] = blueprint["evidence"]
            questions.append(candidate.model_copy(update=update))
        return _RawQuizPool(questions=questions)

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["response_model"] is _RawContentMap:
            value = self._map_from_prompt(kwargs["user_prompt"])
        else:
            value = self._annotate_pool(self.pool, kwargs["user_prompt"])
        return FakeCompletion(value)


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
        question_types=["mcq"],
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
        dict(id="b", prompt="Which factor is stated to increase photosynthesis up to a saturation point?", correct_answer="Light intensity", options=["Light intensity", "Carbon dioxide concentration", "Temperature", "Glucose production"], source_pages=[4], explanation="The rate of photosynthesis increases with light intensity up to a saturation point."),
    ])
    result = generate_quiz(
        FakeQuizService(pool), BIOLOGY_SOURCE,
        **default_kwargs(count=2, previous_questions=["What is the primary function of photosynthesis?"]),
    )
    prompts = [q.prompt.lower() for q in result.questions]
    assert "what is the main purpose of photosynthesis?" not in prompts
    assert "which factor is stated to increase photosynthesis up to a saturation point?" in prompts


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
        dict(id="b", prompt="Which products do the light reactions produce?", correct_answer="ATP and NADPH", options=["ATP and NADPH", "ATP and oxygen", "NADPH and oxygen", "Water and oxygen"], source_pages=[2], explanation="The light reactions produce ATP and NADPH."),
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
        dict(id="a", type="mcq", prompt="ما هي وظيفة البناء الضوئي؟", correct_answer="تحويل الطاقة الضوئية إلى طاقة كيميائية", options=["تحويل الطاقة الضوئية إلى طاقة كيميائية", "تحويل الطاقة الكيميائية إلى طاقة ضوئية", "تخزين الطاقة الضوئية في النباتات", "إطلاق الطاقة الكيميائية من النباتات"], explanation="البناء الضوئي يحول الطاقة الضوئية إلى طاقة كيميائية.", source_pages=[1]),
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
        dict(id="a", prompt="Which process converts light into chemical energy?", correct_answer="Photosynthesis", options=["Photosynthesis", "The light reactions", "ATP reactions", "NADPH reactions"], source_pages=[1], explanation="Photosynthesis converts light into chemical energy."),
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
        dict(id="a", prompt="Which process converts light energy into chemical energy?", correct_answer="Photosynthesis",
             options=["Photosynthesis", "Chemical energy", "Light energy", "Energy conversion"], source_pages=[1],
             explanation="Photosynthesis converts light energy into chemical energy."),
    ])

    class EndpointService(FakeQuizService):
        def __init__(self):
            super().__init__(pool)

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
                    "questionTypes": ["mcq"],
                    "seed": 5,
                    "previousQuestions": ["How do roots absorb water?"],
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


def test_prompt_includes_explicit_anti_boilerplate_rules() -> None:
    from app.services.quiz_concepts import build_concept_map, split_source_units
    concepts = build_concept_map(split_source_units(BIOLOGY_SOURCE.text))
    prompt = build_candidate_prompt(
        source=BIOLOGY_SOURCE, concepts=concepts, count=6, candidate_count=24,
        question_types=["mcq"], difficulty="medium", kind="practice", language="en",
        previous_questions=[],
    )
    lowered = prompt.lower()
    assert "copyright" in lowered
    assert "boilerplate" in lowered
    assert "trademarks" in lowered
    assert "headers, footers" in lowered


def test_llm_receives_cleaned_source_without_footer_text() -> None:
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
    pool = make_pool([
        dict(id="a", prompt="What is a database?", correct_answer="An organized collection of structured data",
             options=["An organized collection of structured data", "An unorganized collection of structured data", "An organized collection of unstructured data", "An organized structure without collected data"],
             source_pages=[1], explanation="The source defines a database as an organized collection of structured data."),
    ])
    service = FakeQuizService(pool)
    result = generate_quiz(service, source, **default_kwargs(count=1))
    assert len(result.questions) == 1
    user_prompt = service.calls[0]["user_prompt"]
    assert "database is defined" in user_prompt
    assert "Copyright © 2020" not in user_prompt
    assert "Oracle Database Documentation" not in user_prompt


def test_end_to_end_filters_boilerplate_candidates_from_pool() -> None:
    pool = make_pool([
        dict(id="a", prompt="What is the main purpose of photosynthesis?", correct_answer="To convert light energy into chemical energy",
             options=["To convert light energy into chemical energy", "To produce oxygen only", "To store water", "To release carbon dioxide"],
             source_pages=[1], explanation="Photosynthesis converts light energy into chemical energy."),
        dict(id="b", type="fill-blank", prompt="Copyright © 2020, _____ and/or its affiliates.", correct_answer="Oracle",
             options=None, source_pages=[1], explanation="The footer of every page contains this notice."),
        dict(id="c", prompt="Which molecule do the light reactions produce as a byproduct?", correct_answer="Oxygen",
             options=["Oxygen", "Glucose", "Water", "Carbon dioxide"], source_pages=[2],
             explanation="The light reactions split water molecules and produce oxygen as a byproduct."),
        dict(id="d", prompt="Why does the Calvin cycle not require light directly?", correct_answer="It uses ATP and NADPH",
             options=["It uses ATP and NADPH", "It uses chlorophyll", "It produces oxygen", "It splits water"], source_pages=[3],
             explanation="The Calvin cycle uses ATP and NADPH produced by the light reactions."),
        dict(id="e", prompt="How do the light reactions and the Calvin cycle relate?", correct_answer="The products of one fuel the other",
             options=["The products of one fuel the other", "They occur in the same place", "They both need light", "They both produce glucose"], source_pages=[3],
             explanation="See page 3 of 12 of the publisher's manual."),
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
