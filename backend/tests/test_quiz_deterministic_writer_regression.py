"""Regression coverage for deterministic fallback writing from PDF evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services import storage as storage_service
from app.services.ai_documents import clear_extraction_cache, source_from_text, _extract_pdf_uncached
from app.services.ai_service import AIServiceError, AIStructuredCompletion
from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_deterministic import (
    deterministic_candidates,
    replan_unsafe_mcq_blueprints,
)
from app.services.quiz_pipeline import _RawQuizPool, build_quiz_context, generate_quiz
from app.services.quiz_understanding import DocumentUnderstanding, deterministic_understanding

import app.api.ai as ai_api


ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]
FILE_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
SQL18_FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"


class NoProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("provider unavailable")


class EmptyWriterProvider:
    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawQuizPool:
            return AIStructuredCompletion(
                value=_RawQuizPool(questions=[]),
                provider="gemini",
                model="fake",
                fallback_used=False,
            )
        raise AIServiceError("understanding unavailable")


class FailingProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("provider unavailable")


def _understanding(text: str) -> DocumentUnderstanding:
    source = source_from_text(text, title="Document")
    context = build_quiz_context(source)
    return deterministic_understanding(context.units, title="Document")


def _blueprint(
    *,
    concept_id: str,
    concept: str,
    evidence: str,
    question_type: str = "short-answer",
    skill: str = "understanding",
    facet_kind: str = "",
    answer_clause: str = "",
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=f"bp-{concept_id}-{question_type}",
        concept_id=concept_id,
        concept=concept,
        knowledge_target_id=f"{concept_id}--{skill}",
        knowledge_target=f"understand {concept}",
        knowledge_type="definition",
        cognitive_skill=skill,
        question_type=question_type,
        difficulty="medium",
        importance=1.0,
        evidence=evidence,
        pages=(1,),
        topic="",
        facet_kind=facet_kind,
        answer_clause=answer_clause,
    )


def test_no_answer_claim_uses_clear_explanatory_evidence_sentence() -> None:
    understanding = _understanding(
        "A transaction is a unit of work executed atomically.\n"
        "Atomicity ensures that a transaction is treated as a single unit."
    )
    blueprint = _blueprint(
        concept_id="transaction",
        concept="transaction",
        evidence="A transaction is a unit of work executed atomically.",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1
    assert written[0]["prompt"] == "What is transaction?"
    assert written[0]["correct_answer"] == "a unit of work executed atomically"
    assert written[0]["correct_answer"] in blueprint.evidence


def test_no_facet_strong_evidence_still_writes_grounded_question() -> None:
    understanding = _understanding(
        "Atomicity ensures that a transaction is treated as a single unit.\n"
        "Consistency ensures that committed data satisfies constraints."
    )
    blueprint = _blueprint(
        concept_id="atomicity",
        concept="Atomicity",
        evidence="Atomicity ensures that a transaction is treated as a single unit.",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1
    assert written[0]["prompt"] == "What is Atomicity?"
    assert written[0]["correct_answer"] == (
        "ensures that a transaction is treated as a single unit"
    )


def test_insufficient_mcq_distractors_replans_to_selected_safe_type() -> None:
    understanding = _understanding(
        "A primary key uniquely identifies each row in a table.\n"
        "A foreign key references a primary key in another table."
    )
    mcq = _blueprint(
        concept_id="primary-key",
        concept="primary key",
        evidence="A primary key uniquely identifies each row in a table.",
        question_type="mcq",
    )

    replanned = replan_unsafe_mcq_blueprints(
        [mcq],
        selected_question_types=["mcq", "short-answer"],
        understanding=understanding,
    )
    written = deterministic_candidates(replanned, language="en", understanding=understanding)

    assert [plan.question_type for plan in replanned] == ["short-answer"]
    assert len(written) == 1
    assert written[0]["type"] == "short-answer"
    assert written[0]["correct_answer"] == "uniquely identifies each row in a table"


def test_mcq_only_shortage_is_truthful_skip_not_weak_mcq() -> None:
    understanding = _understanding(
        "A primary key uniquely identifies each row in a table.\n"
        "A foreign key references a primary key in another table."
    )
    mcq = _blueprint(
        concept_id="primary-key",
        concept="primary key",
        evidence="A primary key uniquely identifies each row in a table.",
        question_type="mcq",
    )

    replanned = replan_unsafe_mcq_blueprints(
        [mcq], selected_question_types=["mcq"], understanding=understanding
    )
    drops: dict[str, int] = {}
    written = deterministic_candidates(
        replanned, language="en", understanding=understanding, drop_reasons=drops
    )

    assert [plan.question_type for plan in replanned] == ["mcq"]
    assert written == []
    assert drops == {"too_few_distractors": 1}


def _sql18_source():
    clear_extraction_cache()
    return _extract_pdf_uncached(
        SQL18_FIXTURE.read_bytes(),
        file_id="sql18-shaped",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )


def _provider_returning(question_count: int):
    class Provider(NoProvider):
        def complete_structured(self, **kwargs):
            if kwargs["response_model"] is _RawQuizPool:
                questions = []
                for index in range(question_count):
                    bp = f"bp-{index + 1}"
                    questions.append(
                        {
                            "blueprint_id": bp,
                            "type": "short-answer",
                            "prompt": f"What is Concept {index + 1}?",
                            "correct_answer": f"a mechanism that produces grounded outcome {index + 1} for learners",
                            "options": None,
                            "explanation": f"Concept {index + 1} is a mechanism that produces grounded outcome {index + 1} for learners.",
                            "source_pages": [1],
                            "source_quote": f"Concept {index + 1} is a mechanism that produces grounded outcome {index + 1} for learners.",
                        }
                    )
                return AIStructuredCompletion(
                    value=_RawQuizPool.model_validate({"questions": questions}),
                    provider="gemini",
                    model="fake",
                    fallback_used=False,
                )
            raise AIServiceError("force deterministic understanding")

    return Provider()


def test_provider_writer_returns_zero_deterministic_fallback_reaches_8() -> None:
    result = generate_quiz(
        EmptyWriterProvider(),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


# Provider candidates here intentionally do not need to survive; the regression
# is that deterministic top-up still fills the exact requested count.

def test_provider_writer_returns_two_deterministic_topup_reaches_8() -> None:
    result = generate_quiz(
        _provider_returning(2),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=3,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


def test_provider_writer_returns_five_deterministic_topup_reaches_8() -> None:
    result = generate_quiz(
        _provider_returning(5),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=5,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


def test_provider_succeeds_with_at_least_8_no_unnecessary_fallback(monkeypatch) -> None:
    from app.schemas.ai import AIQuizQuestion
    from app.services.quiz_blueprints import semantic_objective_key
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import _top_up_candidates, build_quiz_context
    from app.services.quiz_scoring import ScoredCandidate
    import app.services.quiz_pipeline as pipeline

    source = _sql18_source()
    context = build_quiz_context(source)
    understanding = deterministic_understanding(context.units, title="SQL18")
    context.understanding = understanding
    context.knowledge_targets = build_knowledge_targets(understanding)

    blueprint_by_id = {}
    scored = []
    for index, concept in enumerate(understanding.important_concepts(), start=1):
        blueprint = _blueprint(
            concept_id=concept.concept_id,
            concept=concept.name,
            evidence=concept.primary_evidence,
        )
        blueprint = replace(blueprint, id=f"provider-bp-{index}")
        blueprint_by_id[blueprint.id] = blueprint
        question = AIQuizQuestion(
            id=f"provider-q-{index}",
            type="short-answer",
            prompt=f"What is {concept.name}?",
            correctAnswer="directly supported by the cited evidence",
            explanation=concept.primary_evidence,
            difficulty="medium",
            sourcePages=list(concept.source_pages[:1] or [1]),
        )
        scored.append(
            ScoredCandidate(
                question=question,
                score=0.9,
                concept=concept.concept_id,
                skill="understanding",
                pattern="provider",
                objective_key=semantic_objective_key(
                    concept.concept_id, blueprint.knowledge_target_id, "understanding"
                ),
                blueprint_id=blueprint.id,
            )
        )

    def _should_not_write(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("deterministic top-up ran despite a full provider pool")

    monkeypatch.setattr(pipeline, "deterministic_candidates", _should_not_write)
    funnel = {"topup_rounds": [], "deterministic_drop_reasons": {}, "plans_skipped_reason": {}}
    provider_trace = {}

    topped_up, _ = _top_up_candidates(
        scored,
        {},
        context=context,
        source=source,
        understanding=understanding,
        blueprint_by_id=blueprint_by_id,
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        language="en",
        seed=1,
        previous_questions=[],
        quality_threshold=0.68,
        rejections=[],
        provider_trace=provider_trace,
        funnel=funnel,
    )

    assert topped_up == scored
    assert provider_trace == {}
    assert funnel["topup_rounds"] == [{"round": 1, "stop_reason": "pool_sufficient"}]

def test_genuine_content_shortage_truthful_422_path() -> None:
    source = source_from_text(
        "A checksum is a value computed from a block of data.",
        title="Thin",
    )
    try:
        generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=ALL_TYPES,
            difficulty="medium",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the source.",
        )
    except Exception as exc:
        assert exc.__class__.__name__ in {"QuizMaterialError", "AIUnavailableError"}
    else:  # pragma: no cover - this is the forbidden outcome
        raise AssertionError("thin source unexpectedly produced eight questions")


def test_no_duplicate_questions_and_exact_supported_counts() -> None:
    source = _sql18_source()
    for count in (3, 5, 8, 12):
        result = generate_quiz(
            NoProvider(),
            source,
            count=count,
            question_types=ALL_TYPES,
            difficulty="medium",
            kind="exam",
            language="en",
            seed=count,
            previous_questions=[],
            system_prompt="Use only the source.",
        )
        prompts = [question.prompt for question in result.questions]
        assert len(result.questions) == count
        assert len(set(prompts)) == len(prompts)


def test_sql18_shaped_fixture_provider_failures_reaches_8_over_http() -> None:
    clear_extraction_cache()
    pdf = SQL18_FIXTURE.read_bytes()
    record = SimpleNamespace(
        id=FILE_ID,
        owner_id=OWNER_ID,
        name="SQL18.pdf",
        size_bytes=len(pdf),
        mime_type="application/pdf",
        storage_key=f"users/{OWNER_ID}/vault/SQL18.pdf",
        analysis=None,
    )

    class FakeSession:
        def get(self, _model, file_id):
            return record if str(file_id) == FILE_ID else None

        def scalar(self, _stmt):
            return record

        def close(self):
            pass

    def _db():
        db = FakeSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)
    app.dependency_overrides[ai_api.get_ai_service] = lambda: FailingProvider()
    original_download = storage_service.download_user_object
    storage_service.download_user_object = lambda *_a, **_k: pdf
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/quiz",
                json={
                    "fileId": FILE_ID,
                    "count": 8,
                    "kind": "exam",
                    "scope": "document",
                    "diagnostics": True,
                },
            )
    finally:
        storage_service.download_user_object = original_download
        app.dependency_overrides = {}
        clear_extraction_cache()

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["questions"]) == 8
    diagnostics = body["diagnostics"]
    assert diagnostics["accepted"] == 8
    assert diagnostics["grounding_rejected"] == 0
    assert diagnostics["provider_calls"]["understanding_failed"] == 1
    assert diagnostics["provider_calls"]["writer_failed"] == 1
