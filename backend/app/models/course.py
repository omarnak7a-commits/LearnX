"""
Full Course model — the real Course & Roster engine schema.

Course tree:  Course 1─N Module 1─N Lesson
Enrollment:   Course N─N Student (via Enrollment, with progress + completion)
Progress:     LessonProgress rows per (student, lesson) — the source of
              truth for the per-student progress % shown in the UI.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CourseStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending-review"
    published = "published"
    archived = "archived"


class CourseType(str, enum.Enum):
    university = "university"
    public = "public"
    premium = "premium"


class LessonType(str, enum.Enum):
    video = "video"
    pdf = "pdf"
    notes = "notes"
    quiz = "quiz"
    assignment = "assignment"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), default="")
    code: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(128), default="")
    faculty: Mapped[str] = mapped_column(String(255), default="")
    department: Mapped[str] = mapped_column(String(255), default="")
    academic_level: Mapped[str] = mapped_column(String(64), default="")

    course_type: Mapped[CourseType] = mapped_column(Enum(CourseType), default=CourseType.university)
    status: Mapped[CourseStatus] = mapped_column(Enum(CourseStatus), default=CourseStatus.draft)

    color: Mapped[str] = mapped_column(String(16), default="#2DD4BF")
    icon: Mapped[str] = mapped_column(String(8), default="📘")
    rating: Mapped[float] = mapped_column(Float, default=4.5)

    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    allow_xp_redemption: Mapped[bool] = mapped_column(Boolean, default=False)
    xp_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    students_count: Mapped[int] = mapped_column(Integer, default=0)
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseModule.order_index"
    )


class CourseModule(Base):
    __tablename__ = "course_modules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["CourseLesson"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="CourseLesson.order_index"
    )


class CourseLesson(Base):
    __tablename__ = "course_lessons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("course_modules.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[LessonType] = mapped_column(Enum(LessonType), default=LessonType.video)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    # Resource metadata (name / kind / size) stored as JSONB — the actual
    # bytes live in Supabase Storage under a user-scoped key.
    resources: Mapped[list] = mapped_column(JSONB, default=list)

    module: Mapped[CourseModule] = relationship(back_populates="lessons")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purchased_via_reward: Mapped[bool] = mapped_column(Boolean, default=False)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_lesson_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("course_lessons.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
