"""End-to-end regression for a small but legitimate educational source."""

from app.services.ai_documents import source_from_text
from app.services.ai_service import AIStructuredCompletion
from app.services.quiz_content_map import _RawContentMap
from app.services.quiz_pipeline import _RawQuizPool, generate_quiz


EVIDENCE = "Evaporation is the process by which liquid water changes into water vapor."
SOURCE_TEXT = (
    "[Page 1]\n"
    + EVIDENCE
    + "\nHeat supplies the energy that causes evaporation."
)


class SmallSourceService:
    def __init__(self) -> None:
        self.calls = 0

    def complete_structured(self, **kwargs):
        self.calls += 1
        if kwargs["response_model"] is _RawContentMap:
            value = _RawContentMap.model_validate(
                {
                    "items": [
                        {
                            "concept": "Evaporation",
                            "category": "important_definition",
                            "importance": "high",
                            "source_quote": EVIDENCE,
                            "source_pages": [1],
                            "knowledge_targets": ["liquid water changes into water vapor"],
                        }
                    ]
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
            provider="test-provider",
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

    assert service.calls == 2
    assert len(result.questions) == 1
    question = result.questions[0]
    assert question.prompt == "How does evaporation change liquid water?"
    assert question.correct_answer == "Liquid water changes into water vapor."
    assert question.source_pages == [1]
    assert question.difficulty == "medium"
