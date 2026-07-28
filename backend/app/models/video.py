"""
ORM models for the AI Video Intelligence feature.

Field names deliberately mirror `src/types/video.ts` so the FastAPI
response schemas (`app/schemas/video.py`) can be generated with minimal
translation and the frontend types stay a 1:1 contract with the API.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class VideoSourceType(str, enum.Enum):
    upload = "upload"
    zoom = "zoom"
    teams = "teams"
    meet = "meet"
    screen_recording = "screen-recording"
    lecture = "lecture"


class VideoProcessingState(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class VideoLecture(Base):
    """One uploaded lecture and everything the AI pipeline produced for it."""

    __tablename__ = "video_lectures"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)
    course_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[VideoSourceType] = mapped_column(Enum(VideoSourceType))
    state: Mapped[VideoProcessingState] = mapped_column(
        Enum(VideoProcessingState), default=VideoProcessingState.queued
    )

    # Storage keys — never expose directly; always resolve to a signed URL
    # via app/services/storage.py before sending to the client.
    original_storage_key: Mapped[str] = mapped_column(String(512))
    optimized_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    duration_sec: Mapped[float] = mapped_column(Float, default=0)
    optimized_duration_sec: Mapped[float] = mapped_column(Float, default=0)
    learning_efficiency_score: Mapped[int] = mapped_column(Integer, default=0)

    current_stage_index: Mapped[int] = mapped_column(Integer, default=0)
    pipeline_state: Mapped[dict] = mapped_column(JSONB, default=dict)  # list[PipelineStage]

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    chapters: Mapped[list["Chapter"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    silence_segments: Mapped[list["SilenceSegment"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan"
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "video_chapters"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("video_lectures.id"), index=True)

    index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    difficulty: Mapped[str] = mapped_column(String(16))  # easy | medium | hard
    confidence: Mapped[float] = mapped_column(Float)
    exam_importance: Mapped[int] = mapped_column(Integer)
    estimated_study_minutes: Mapped[int] = mapped_column(Integer)

    # Denormalized JSON for concept/formula/tip lists — small, read-heavy,
    # and only ever fully replaced together by the concept-extraction stage.
    key_concepts: Mapped[list] = mapped_column(JSONB, default=list)
    formulas: Mapped[list] = mapped_column(JSONB, default=list)
    exam_tips: Mapped[list] = mapped_column(JSONB, default=list)

    lecture: Mapped[VideoLecture] = relationship(back_populates="chapters")


class TranscriptSegment(Base):
    __tablename__ = "video_transcript_segments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("video_lectures.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("video_chapters.id"))

    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    speaker: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(Text)

    # Embedding vector for semantic search / RAG grounding of the AI chat.
    # In production this is a `pgvector` column; represented generically
    # here since pgvector may not be installed in every environment.
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    lecture: Mapped[VideoLecture] = relationship(back_populates="transcript_segments")


class SilenceSegment(Base):
    __tablename__ = "video_silence_segments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("video_lectures.id"), index=True)

    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(32))
    removed: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[float] = mapped_column(Float)

    lecture: Mapped[VideoLecture] = relationship(back_populates="silence_segments")


class Flashcard(Base):
    __tablename__ = "video_flashcards"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("video_lectures.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("video_chapters.id"))

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))

    # Per-user spaced-repetition state lives in a separate join table
    # (`user_flashcard_progress`) so the same generated card can be
    # reviewed independently by every enrolled student.
    lecture: Mapped[VideoLecture] = relationship(back_populates="flashcards")


class QuizQuestion(Base):
    __tablename__ = "video_quiz_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    lecture_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("video_lectures.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("video_chapters.id"))

    type: Mapped[str] = mapped_column(String(32))  # mcq | true-false | short-answer | fill-blank
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))

    lecture: Mapped[VideoLecture] = relationship(back_populates="quiz_questions")
