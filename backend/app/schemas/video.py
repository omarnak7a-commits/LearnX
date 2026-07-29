"""
Pydantic response/request schemas for the AI Video Intelligence API.

These are a direct, field-for-field mirror of `src/types/video.ts` — kept
in sync intentionally so the frontend's mock-data shape and the real API
response shape never diverge, minimizing the future migration diff.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class PipelineStageStatus(str, Enum):
    pending = "pending"
    active = "active"
    done = "done"
    skipped = "skipped"
    error = "error"


class PipelineStageOut(BaseModel):
    id: str
    label: str
    description: str
    status: PipelineStageStatus
    progress: float | None = None
    duration_ms: int | None = None


class SilenceSegmentOut(BaseModel):
    id: str
    start_sec: float
    end_sec: float
    reason: Literal[
        "dead-air", "setup-time", "waiting", "repeated-pause", "idle-moment", "meaningful-pause"
    ]
    removed: bool
    confidence: float


class ChapterConceptOut(BaseModel):
    term: str
    definition: str


class ChapterOut(BaseModel):
    id: str
    index: int
    title: str
    start_sec: float
    end_sec: float
    difficulty: Literal["easy", "medium", "hard"]
    confidence: float
    exam_importance: int
    estimated_study_minutes: int
    key_concepts: list[ChapterConceptOut]
    formulas: list[str]
    exam_tips: list[str]


class TranscriptSegmentOut(BaseModel):
    id: str
    start_sec: float
    end_sec: float
    speaker: str
    text: str
    chapter_id: str


class SummaryContentOut(BaseModel):
    level: Literal["quick", "detailed", "bullet", "exam", "revision", "one-minute"]
    label: str
    points: list[str]


class FlashcardOut(BaseModel):
    id: str
    chapter_id: str
    question: str
    answer: str
    difficulty: Literal["easy", "medium", "hard"]
    favorite: bool
    mastered_level: int


class QuizQuestionOut(BaseModel):
    id: str
    chapter_id: str
    type: Literal["mcq", "true-false", "short-answer", "fill-blank"]
    prompt: str
    options: list[str] | None
    correct_answer: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"]


class MindMapNodeOut(BaseModel):
    id: str
    label: str
    children: list["MindMapNodeOut"]


MindMapNodeOut.model_rebuild()


class VideoStatsOut(BaseModel):
    original_duration_sec: float
    optimized_duration_sec: float
    minutes_saved: float
    percent_removed: int
    learning_efficiency_score: int


class VideoLectureOut(BaseModel):
    id: str
    title: str
    course: str
    source_type: Literal["upload", "zoom", "teams", "meet", "screen-recording", "lecture"]
    uploaded_at: str
    state: Literal["queued", "processing", "ready", "failed"]
    current_stage_index: int
    pipeline: list[PipelineStageOut]
    duration_sec: float
    stats: VideoStatsOut
    silence_segments: list[SilenceSegmentOut]
    chapters: list[ChapterOut]


class VideoUploadInitRequest(BaseModel):
    """
    Starts a resumable/chunked upload session. The client then PUTs chunks
    to `/videos/{upload_id}/chunks/{index}` and finally POSTs
    `/videos/{upload_id}/complete`, at which point the pipeline is queued.
    """

    filename: str
    content_type: str
    total_size_bytes: int
    source_type: Literal["upload", "zoom", "teams", "meet", "screen-recording", "lecture"]
    course_id: str | None = None


class VideoUploadInitResponse(BaseModel):
    upload_id: str
    chunk_size_bytes: int
    chunk_count: int


class VideoChatRequest(BaseModel):
    message: str


class ChatCitationOut(BaseModel):
    chapter_id: str
    chapter_title: str
    timestamp_sec: float


class VideoChatResponse(BaseModel):
    """
    The assistant must ground every answer in retrieved transcript chunks
    (see app/services/rag.py) and always return at least one citation
    when the answer references lecture content — matching the product
    requirement "Never hallucinate. Always cite timestamps."
    """

    text: str
    citations: list[ChatCitationOut]
