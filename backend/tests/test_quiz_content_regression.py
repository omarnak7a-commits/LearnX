"""Regression coverage for educational-content sufficiency in real PDFs."""

from __future__ import annotations

import pytest

from app.services.ai_documents import AIDocumentSource, _extract_pdf
from app.services.ai_service import AIUnavailableError
from app.services.quiz_pipeline import _RawQuizPool, build_quiz_context, generate_quiz
from tests.test_pdf_extraction import _build_pdf
from tests.quiz_fakes import FakeQuizService, default_kwargs, make_pool


def biology_pool() -> _RawQuizPool:
    return make_pool(
        [
            dict(
                id="photosynthesis-purpose",
                prompt="What is the main purpose of photosynthesis?",
                correct_answer="light energy into chemical energy",
                options=[
                    "light energy into chemical energy",
                    "stored energy from glucose",
                    "genetic information before division",
                    "water through animal cells",
                ],
                source_pages=[1],
                explanation="Photosynthesis converts light energy into chemical energy in chloroplasts.",
            ),
            dict(
                id="light-reactions",
                prompt="Which products of the light reactions power carbon fixation?",
                correct_answer="ATP and NADPH",
                options=["ATP and NADPH", "DNA and RNA", "Glucose and oxygen", "Water and carbon dioxide"],
                source_pages=[2],
                explanation="ATP and NADPH power carbon fixation.",
            ),
            dict(
                id="calvin-cycle",
                prompt=(
                    "Suppose carbon dioxide enters the Calvin cycle. "
                    "What would happen to the carbon dioxide?"
                ),
                correct_answer="The Calvin cycle fixes carbon dioxide",
                options=[
                    "The Calvin cycle fixes carbon dioxide",
                    "The light reactions split water",
                    "Chlorophyll captures photons",
                    "ATP and NADPH power carbon fixation",
                ],
                source_pages=[3],
                explanation=(
                    "The Calvin cycle fixes carbon dioxide and builds carbohydrates "
                    "through enzyme-controlled reactions."
                ),
            ),
        ]
    )


def test_real_multi_page_pdf_with_flattened_footers_generates_questions() -> None:
    """Exercise real PDF bytes -> pypdf -> cleaning -> concepts -> quiz."""
    pdf = _build_pdf(
        [
            "Photosynthesis converts light energy into chemical energy in chloroplasts. Chlorophyll captures photons. Copyright © 2024, Example Press. All rights reserved. Page 1 of 3",
            "The light reactions split water and produce oxygen, ATP, and NADPH. ATP and NADPH power carbon fixation. Copyright © 2024, Example Press. All rights reserved. Page 2 of 3",
            "The Calvin cycle fixes carbon dioxide and builds carbohydrates through enzyme-controlled reactions. Copyright © 2024, Example Press. All rights reserved. Page 3 of 3",
        ]
    )
    source = _extract_pdf(
        pdf,
        file_id="real-pdf",
        title="Real Biology Handout.pdf",
        max_characters=50_000,
        allowed_pages=None,
    )

    context = build_quiz_context(source)
    assert len(context.units) == 3
    assert context.sentences  # explanatory prose survives cleaning
    cleaned = " ".join(unit.text for unit in context.units)
    assert "Photosynthesis converts" in cleaned
    assert "Calvin cycle fixes" in cleaned
    assert "Copyright" not in cleaned and "©" not in cleaned

    service = FakeQuizService(biology_pool())
    result = generate_quiz(service, source, **default_kwargs(count=3))
    assert result.questions
    prompts = [question.prompt for question in result.questions]
    assert len(prompts) == len(set(prompts))
    llm_prompt = service.calls[0]["user_prompt"]
    assert "Photosynthesis converts" in llm_prompt
    assert "Copyright" not in llm_prompt and "All rights reserved" not in llm_prompt


def test_short_meaningful_pdf_generates_a_question() -> None:
    source = _extract_pdf(
        _build_pdf(["Mitosis produces two genetically identical daughter cells."]),
        file_id="short-pdf",
        title="Mitosis note.pdf",
        max_characters=10_000,
        allowed_pages=None,
    )
    pool = make_pool(
        [
            dict(
                id="mitosis-result",
                prompt="What does mitosis produce?",
                correct_answer="Two genetically identical daughter cells",
                options=[
                    "Two genetically identical daughter cells",
                    "Four genetically different daughter cells",
                    "Two genetically different daughter cells",
                    "Four genetically identical daughter cells",
                ],
                source_pages=[1],
                explanation="The note states that mitosis produces two genetically identical daughter cells.",
            )
        ]
    )
    result = generate_quiz(
        FakeQuizService(pool),
        source,
        **default_kwargs(count=1, question_types=["mcq", "short-answer", "fill-blank"]),
    )
    assert len(result.questions) == 1


def test_metadata_only_pdf_is_rejected_before_llm_call() -> None:
    source = AIDocumentSource(
        file_id=None,
        title="Front matter.pdf",
        text=(
            "[Page 1]\nCopyright © 2024, Example Press. All rights reserved.\n"
            "Oxford University Press\nThird Edition\nISBN 978-0-12-345678-9"
        ),
        page_count=1,
    )
    service = FakeQuizService(biology_pool())
    with pytest.raises(AIUnavailableError):
        generate_quiz(service, source, **default_kwargs(count=1))
    assert service.calls == []
