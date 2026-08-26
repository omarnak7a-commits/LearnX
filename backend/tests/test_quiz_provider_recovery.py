"""Provider top-up, quality judge, and exact-count recovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_documents import source_from_text
from app.services.ai_service import AIServiceError, AIStructuredCompletion
from app.services.quiz_pipeline import (
    QuizMaterialError,
    _RawQuizPool,
    generate_quiz,
)
from app.services.quiz_quality_judge import (
    _RawQualityJudgement,
    heuristic_quality_issues,
)
from app.services.quiz_understanding import _RawUnderstanding
from tests.quiz_fakes import FakeQuizService
from tests.test_quiz_exact_count import ALL_TYPES, NoProvider, load_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"


def _kwargs(**overrides):
    base = dict(
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )
    base.update(overrides)
    return base


class PartialWriter:
    """Understanding works; writer returns only the first N blueprint-shaped items."""

    def __init__(self, keep: int) -> None:
        self.keep = keep
        self.inner = FakeQuizService(title="cell")
        self.writer_calls = 0

    def complete_structured(self, **kwargs):
        model = kwargs["response_model"]
        if model is _RawUnderstanding or model is _RawQualityJudgement:
            return self.inner.complete_structured(**kwargs)
        self.writer_calls += 1
        full = self.inner.complete_structured(**kwargs)
        kept = list(full.value.questions)[: self.keep]
        return AIStructuredCompletion(
            value=_RawQuizPool(questions=kept),
            provider="gemini",
            model="gemini-test",
            fallback_used=False,
        )


class EmptyWriter(FakeQuizService):
    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawUnderstanding:
            return super().complete_structured(**kwargs)
        if kwargs["response_model"] is _RawQualityJudgement:
            return super().complete_structured(**kwargs)
        return AIStructuredCompletion(
            value=_RawQuizPool(questions=[]),
            provider="gemini",
            model="gemini-test",
            fallback_used=False,
        )


class FailingWriter:
    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawUnderstanding:
            raise AIServiceError("understanding down")
        raise AIServiceError("writer down")


def test_provider_returns_enough_candidates_exact_count() -> None:
    result = generate_quiz(
        FakeQuizService(title="cell"),
        load_pdf("cell-biology-ch3.pdf"),
        **_kwargs(),
    )
    assert len(result.questions) == 8
    assert result.telemetry["quiz_requested"] == 8
    prompts = [q.prompt for q in result.questions]
    assert len(set(prompts)) == 8


def test_provider_returns_four_then_topup_to_eight() -> None:
    service = PartialWriter(keep=4)
    result = generate_quiz(service, load_pdf("cell-biology-ch3.pdf"), **_kwargs())
    assert len(result.questions) == 8
    assert service.writer_calls >= 2
    assert result.telemetry["provider_topup_calls"] >= 1 or result.telemetry[
        "deterministic_candidates_returned"
    ] >= 1


def test_provider_returns_two_then_topup_to_eight() -> None:
    service = PartialWriter(keep=2)
    result = generate_quiz(service, load_pdf("cell-biology-ch3.pdf"), **_kwargs())
    assert len(result.questions) == 8
    assert result.telemetry["provider_generation_calls"] >= 1


def test_provider_returns_zero_uses_deterministic_fallback() -> None:
    result = generate_quiz(EmptyWriter(title="cell"), load_pdf("cell-biology-ch3.pdf"), **_kwargs())
    assert len(result.questions) == 8
    assert result.telemetry["deterministic_candidates_returned"] >= 8


def test_provider_completely_fails_uses_deterministic_fallback() -> None:
    result = generate_quiz(FailingWriter(), load_pdf("cell-biology-ch3.pdf"), **_kwargs())
    assert len(result.questions) == 8
    assert result.fallback_used is True
    assert result.provider == "deterministic"


def test_poor_quality_candidate_is_rejected_by_judge() -> None:
    from app.services.quiz_blueprints import QuestionBlueprint
    from app.schemas.ai import AIQuizQuestion

    question = AIQuizQuestion(
        id="q1",
        type="mcq",
        prompt="What is photosynthesis?",
        options=["Photosynthesis", "The photosynthesis", "Light", "Water"],
        correct_answer="Photosynthesis",
        explanation="The source defines photosynthesis as converting light energy.",
        difficulty="medium",
        source_pages=[1],
    )
    blueprint = QuestionBlueprint(
        id="bp-1",
        concept_id="c1",
        concept="Photosynthesis",
        knowledge_target_id="t1",
        knowledge_target="define photosynthesis",
        knowledge_type="definition",
        cognitive_skill="understanding",
        question_type="mcq",
        difficulty="medium",
        importance=0.9,
        evidence="Photosynthesis converts light energy into chemical energy.",
        pages=(1,),
    )
    issues = heuristic_quality_issues(question, blueprint)
    assert issues
    assert any("ambiguous" in issue or "also be correct" in issue for issue in issues)


def test_ambiguous_mcq_is_rejected() -> None:
    test_poor_quality_candidate_is_rejected_by_judge()


def test_genuine_content_shortage_is_truthful_422() -> None:
    thin = source_from_text(
        "Photosynthesis is the process by which plants convert light into chemical energy.",
        "Thin note",
    )
    with pytest.raises(QuizMaterialError) as excinfo:
        generate_quiz(NoProvider(), thin, **_kwargs())
    assert excinfo.value.requested == 8
    assert excinfo.value.available < 8


def test_no_unnecessary_duplicate_questions() -> None:
    result = generate_quiz(
        FakeQuizService(title="cell"),
        load_pdf("cell-biology-ch3.pdf"),
        **_kwargs(),
    )
    prompts = [q.prompt.strip().casefold() for q in result.questions]
    assert len(set(prompts)) == len(prompts)
    targets = [record.knowledge_target_id for record in result.provenance]
    assert len(set(targets)) == len(targets)


def test_sql18_shaped_provider_failure_returns_eight() -> None:
    from app.services.ai_documents import _extract_pdf_uncached, clear_extraction_cache

    clear_extraction_cache()
    source = _extract_pdf_uncached(
        FIXTURE.read_bytes(),
        file_id="sql18",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    result = generate_quiz(NoProvider(), source, **_kwargs(count=8))
    assert len(result.questions) == 8


@pytest.mark.parametrize("count", [3, 5, 8, 12])
def test_exact_counts_when_supported(count: int) -> None:
    result = generate_quiz(
        NoProvider(),
        load_pdf("cell-biology-ch3.pdf"),
        **_kwargs(count=count),
    )
    assert len(result.questions) == count
