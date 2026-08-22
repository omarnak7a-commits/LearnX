"""Validated request/response contracts for LearnX's online AI endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class AIBaseModel(BaseModel):
    """Use the frontend's camelCase JSON while keeping Python snake_case."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class AIProviderMetadata(AIBaseModel):
    # "deterministic" identifies LearnX's provider-free study-map writer, which
    # produces the quiz from the same semantic understanding and the same
    # quality gates when Gemini/Groq are unavailable. The response shape is
    # unchanged; this is an additive value so existing clients keep working.
    provider: Literal["gemini", "groq", "deterministic"]
    model: str
    fallback_used: bool = False


class AIChatMessage(AIBaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


AiLanguage = Literal["ar", "en"]


class AIChatRequest(AIBaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["socratic", "direct", "mentor"] = "direct"
    history: list[AIChatMessage] = Field(default_factory=list, max_length=20)
    file_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_text: str | None = Field(default=None, min_length=1, max_length=60_000)
    source_title: str | None = Field(default=None, max_length=512)
    language: AiLanguage | None = None

    @model_validator(mode="after")
    def one_optional_source(self) -> "AIChatRequest":
        if self.file_id and self.source_text:
            raise ValueError("Use fileId or sourceText, not both.")
        return self


class PageCitation(AIBaseModel):
    page: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=200)


class AIChatResponse(AIProviderMetadata):
    answer: str
    citations: list[PageCitation] = Field(default_factory=list)


class AISourceRequest(AIBaseModel):
    file_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_text: str | None = Field(default=None, min_length=20, max_length=60_000)
    source_title: str | None = Field(default=None, max_length=512)
    language: AiLanguage | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "AISourceRequest":
        if bool(self.file_id) == bool(self.source_text):
            raise ValueError("Provide exactly one of fileId or sourceText.")
        return self


class AISummaryRequest(AISourceRequest):
    detail: Literal["short", "detailed", "exam"] = "short"


class AISummaryResult(AIBaseModel):
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1, max_length=12)
    key_topics: list[str] = Field(default_factory=list, max_length=12)
    important_questions: list[str] = Field(default_factory=list, max_length=10)


class AISummaryResponse(AIProviderMetadata, AISummaryResult):
    pass


class AITopicsRequest(AISourceRequest):
    count: int = Field(default=8, ge=3, le=15)


class AITopic(AIBaseModel):
    name: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1)
    source_pages: list[int] = Field(default_factory=list, max_length=10)
    importance: Literal["high", "medium", "low"]


class AITopicsResult(AIBaseModel):
    key_topics: list[AITopic] = Field(min_length=1, max_length=15)
    important_questions: list[str] = Field(default_factory=list, max_length=15)


class AITopicsResponse(AIProviderMetadata, AITopicsResult):
    pass


QuestionType = Literal["mcq", "true-false", "fill-blank", "short-answer"]
Difficulty = Literal["easy", "medium", "hard"]


class AIQuizRequest(AISourceRequest):
    count: int = Field(default=6, ge=1, le=20)
    question_types: list[QuestionType] = Field(
        default_factory=lambda: ["mcq", "true-false", "fill-blank", "short-answer"],
        min_length=1,
        max_length=4,
    )
    difficulty: Difficulty | Literal["mixed"] = "mixed"
    kind: Literal["practice", "exam"] = "practice"
    #: Which part of the PDF the quiz may draw on.
    #:
    #:  ``document``   -- the whole uploaded PDF (the default, and what
    #:                    "make me an exam from this PDF" means).
    #:  ``pages-read`` -- only the pages the student actually opened, for the
    #:                    deliberate "quiz me on what I've read" flow.
    #:
    #: Defaulting to ``document`` matters: sourcing a whole-PDF quiz from
    #: ``pagesRead`` is how a 20-page textbook was reduced to its title page,
    #: which yielded zero concepts and the misleading "not enough material"
    #: error even though the document was full of teachable content.
    scope: Literal["document", "pages-read"] = "document"
    allowed_pages: list[int] | None = Field(default=None, min_length=1, max_length=300)
    # Optional determinism + history knobs (backward compatible; the frontend
    # does not need to send them). A seed makes selection/randomization
    # reproducible; previousQuestions lets callers suppress repeats, and the
    # backend also merges persisted analysis questions as additional history.
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    previous_questions: list[str] = Field(default_factory=list, max_length=100)
    #: Return the stage-by-stage generation funnel alongside the quiz. Counts
    #: and rejection reasons only -- never prompts, credentials or provider
    #: configuration.
    diagnostics: bool = False


class AIQuizQuestion(AIBaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: QuestionType
    prompt: str = Field(min_length=1)
    options: list[str] | None = Field(default=None, min_length=2, max_length=6)
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    difficulty: Difficulty
    source_pages: list[int] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_options(self) -> "AIQuizQuestion":
        if self.type in {"mcq", "true-false"}:
            if not self.options:
                raise ValueError("MCQ and true/false questions require options.")
            normalized = {option.casefold() for option in self.options}
            if self.correct_answer.casefold() not in normalized:
                raise ValueError("correctAnswer must match one of the options.")
        return self


class AIQuizResult(AIBaseModel):
    questions: list[AIQuizQuestion] = Field(min_length=1, max_length=20)


class AIQuizDiagnostics(BaseModel):
    """Where questions were lost, stage by stage.

    Exists because "could only verify 1" is unactionable on its own: it cannot
    distinguish a thin PDF from a page-scoping mistake from an over-strict
    validator. Contains counts and rejection reasons only.
    """

    requested: int
    extracted_pages: int
    #: Pages whose text survived extraction AND boilerplate cleaning.
    pages_used: int
    #: Pages that yielded some extractable text.
    text_pages: int = 0
    #: Pages with (almost) no text but embedded imagery -- scans, diagrams,
    #: slide screenshots. These are candidates for multimodal understanding
    #: rather than evidence that the document is empty.
    image_only_pages: int = 0
    #: Pages whose text was extracted but then discarded by cleaning. A high
    #: number here means content was lost after extraction, not absent.
    pages_dropped_in_cleaning: int = 0
    concepts: int
    evidence_items: int
    relationships: int = 0
    plans: int
    candidates_generated: int
    accepted: int
    rejected: int
    provider_errors: int = 0
    rejections: dict[str, int] = Field(default_factory=dict)
    #: Concepts the provider actually proposed, before verification. When this
    #: is high and ``concepts`` is low, the shortfall is ours, not the PDF's.
    concepts_proposed_by_provider: int = 0
    #: Why proposed concepts were dropped, keyed by gate.
    concepts_dropped_in_filtering: dict[str, int] = Field(default_factory=dict)
    #: "provider" or "deterministic". "deterministic" after a provider call
    #: succeeded means the provider's study map was discarded.
    understanding_source: str = ""
    #: Provider call outcomes: calls attempted, valid, empty, discarded.
    provider_calls: dict[str, int] = Field(default_factory=dict)
    #: Plans and candidate drops broken down by question type, so a
    #: type-allocation failure cannot masquerade as a thin document.
    plans_by_type: dict[str, int] = Field(default_factory=dict)
    candidates_by_type: dict[str, int] = Field(default_factory=dict)
    grounding_rejected: int = 0
    diversity_rejected: int = 0
    #: One entry per dropped candidate: stage, reason, concept, pages, type.
    rejection_details: list[dict[str, Any]] = Field(default_factory=list)
    #: Per-page extraction quality, capped so the payload stays small.
    page_quality: list[str] = Field(default_factory=list)


class AIQuizResponse(AIProviderMetadata, AIQuizResult):
    diagnostics: AIQuizDiagnostics | None = None


class AIFlashcardsRequest(AISourceRequest):
    count: int = Field(default=10, ge=1, le=20)
    difficulty: Difficulty | Literal["mixed"] = "mixed"


class AIFlashcard(AIBaseModel):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    source_page: int = Field(ge=1)
    mastered_level: int = Field(default=0, ge=0, le=5)


class AIFlashcardsResult(AIBaseModel):
    flashcards: list[AIFlashcard] = Field(min_length=1, max_length=20)


class AIFlashcardsResponse(AIProviderMetadata, AIFlashcardsResult):
    pass


class AIMindMapRequest(AISourceRequest):
    max_depth: int = Field(default=3, ge=2, le=4)


class AIMindMapNode(AIBaseModel):
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=240)
    source_page: int | None = Field(default=None, ge=1)
    children: list["AIMindMapNode"] = Field(default_factory=list, max_length=12)


AIMindMapNode.model_rebuild()


class AIMindMapResult(AIBaseModel):
    mind_map: AIMindMapNode


class AIMindMapResponse(AIProviderMetadata, AIMindMapResult):
    pass


class AIExplainRequest(AISourceRequest):
    topic: str = Field(min_length=1, max_length=500)
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"


class AIExplainResult(AIBaseModel):
    explanation: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1, max_length=12)
    examples: list[str] = Field(default_factory=list, max_length=6)
    common_mistakes: list[str] = Field(default_factory=list, max_length=6)
    source_pages: list[int] = Field(default_factory=list, max_length=10)


class AIExplainResponse(AIProviderMetadata, AIExplainResult):
    pass


class AIDefinition(AIBaseModel):
    term: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=1)
    source_page: int = Field(ge=1)


class AITimelineEntry(AIBaseModel):
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=240)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)


class AIDocumentAnalysis(AIBaseModel):
    ready: bool = True
    executive_summary: str = Field(min_length=1)
    short_summary: str = Field(min_length=1)
    detailed_summary: str = Field(min_length=1)
    key_concepts: list[str] = Field(min_length=1, max_length=15)
    definitions: list[AIDefinition] = Field(default_factory=list, max_length=12)
    formulas: list[str] = Field(default_factory=list, max_length=15)
    exam_tips: list[str] = Field(default_factory=list, max_length=10)
    important_questions: list[str] = Field(default_factory=list, max_length=12)
    learning_objectives: list[str] = Field(default_factory=list, max_length=10)
    difficult_topics: list[str] = Field(default_factory=list, max_length=10)
    revision_notes: list[str] = Field(default_factory=list, max_length=15)
    flashcards: list[AIFlashcard] = Field(default_factory=list, max_length=20)
    mind_map: AIMindMapNode
    timeline: list[AITimelineEntry] = Field(default_factory=list, max_length=20)
    difficulty: Difficulty
    content_density_score: int = Field(ge=0, le=100)


class AIAnalyzeRequest(AISourceRequest):
    flashcard_count: int = Field(default=10, ge=3, le=20)


class AIAnalyzeResponse(AIProviderMetadata):
    analysis: AIDocumentAnalysis
