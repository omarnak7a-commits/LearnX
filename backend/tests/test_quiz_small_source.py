"""End-to-end regression for a small but legitimate educational source."""

from __future__ import annotations

from app.services.ai_documents import source_from_text
from app.services.ai_service import AIStructuredCompletion
from app.services.quiz_pipeline import _RawQuizPool, generate_quiz
from app.services.quiz_understanding import _RawUnderstanding

EVIDENCE = "Evaporation is the process by which liquid water changes into water vapor."
SOURCE_TEXT = "[Page 1]\n" + EVIDENCE + "\nHeat supplies the energy that causes evaporation."


class SmallSourceService:
    """A cooperative provider: understands the note, then writes to the plan."""

    def __init__(self) -> None:
        self.calls = 0

    def complete_structured(self, **kwargs):
        self.calls += 1
        if kwargs["response_model"] is _RawUnderstanding:
            value = _RawUnderstanding.model_validate(
                {
                    "subject": "Earth science",
                    "summary": "The note explains evaporation and the energy that drives it.",
                    "main_topics": [
                        {
                            "name": "Evaporation",
                            "concept_ids": ["evaporation"],
                            "source_pages": [1],
                        }
                    ],
                    "concepts": [
                        {
                            "id": "evaporation",
                            "name": "Evaporation",
                            "description": "Liquid water changing into water vapor.",
                            "topic": "Evaporation",
                            "knowledge_type": "process",
                            "teaching_emphasis": "high",
                            "evidence_quotes": [EVIDENCE],
                            "source_pages": [1],
                            "why_important": "It is the note's central process.",
                        }
                    ],
                    "learning_objectives": [
                        {
                            "text": "Explain how evaporation changes liquid water.",
                            "concept_ids": ["evaporation"],
                            "source_pages": [1],
                        }
                    ],
                }
            )
        else:
            value = _RawQuizPool.model_validate(
                {
                    "questions": [
                        {
                            "id": "small-1",
                            "blueprint_id": "bp-1",
                            "type": "short-answer",
                            "prompt": "How does evaporation change liquid water?",
                            "correct_answer": "Liquid water changes into water vapor.",
                            "explanation": EVIDENCE,
                            "difficulty": "hard",
                            "source_pages": [1],
                            "source_quote": EVIDENCE,
                        }
                    ]
                }
            )
        return AIStructuredCompletion(
            value=value,
            provider="gemini",
            model="test-model",
            fallback_used=False,
        )


def test_small_educational_source_still_yields_a_grounded_question() -> None:
    service = SmallSourceService()
    result = generate_quiz(
        service,
        source_from_text(SOURCE_TEXT, title="Evaporation note"),
        count=3,
        question_types=["short-answer"],
        difficulty="medium",
        kind="practice",
        language="en",
        seed=17,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )

    assert service.calls == 2  # understand first, then write
    assert result.questions
    question = result.questions[0]
    assert question.prompt == "How does evaporation change liquid water?"
    assert question.correct_answer == "Liquid water changes into water vapor."
    assert question.source_pages == [1]
    assert question.difficulty == "medium"

    # The study map was built before the question, and the question traces back.
    assert result.understanding is not None
    assert "evaporation" in result.understanding.summary.lower()
    trace = result.provenance[0]
    assert trace.concept_id == "evaporation"
    assert trace.knowledge_target_id
    assert trace.quality_score > 0
