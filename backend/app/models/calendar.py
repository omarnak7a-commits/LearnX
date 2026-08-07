"""Calendar + Notifications models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CalendarEventType(str, enum.Enum):
    exam = "exam"
    assignment = "assignment"
    quiz = "quiz"
    study_session = "study-session"
    personal = "personal"
    course_deadline = "course-deadline"
    meeting = "meeting"
    custom = "custom"


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[str] = mapped_column(String(16), index=True)  # ISO "YYYY-MM-DD"
    time: Mapped[str | None] = mapped_column(String(8), nullable=True)  # "HH:mm"
    color: Mapped[str] = mapped_column(String(16), default="#2DD4BF")
    type: Mapped[CalendarEventType] = mapped_column(
        Enum(CalendarEventType), default=CalendarEventType.custom
    )
    course_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    reminder_minutes_before: Mapped[int | None] = mapped_column(Integer, nullable=True)

    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NotificationKind(str, enum.Enum):
    announcement = "announcement"
    assignment = "assignment"
    quiz = "quiz"
    message = "message"
    reminder = "reminder"
    system = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    recipient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind), default=NotificationKind.system)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(16), default="🔔")
    link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
