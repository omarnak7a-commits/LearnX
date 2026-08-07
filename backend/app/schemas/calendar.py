"""Calendar + Notifications API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CalendarEventType = Literal[
    "exam", "assignment", "quiz", "study-session", "personal",
    "course-deadline", "meeting", "custom",
]


class CalendarEventOut(BaseModel):
    id: str
    title: str
    description: str = ""
    date: str
    time: str | None = None
    color: str = "#2DD4BF"
    type: CalendarEventType = "custom"
    courseId: str | None = None
    reminderMinutesBefore: int | None = None
    completed: bool = False
    completedAt: int | None = None
    createdAt: int = 0
    updatedAt: int = 0


class CalendarEventIn(BaseModel):
    title: str
    description: str = ""
    date: str
    time: str | None = None
    color: str = "#2DD4BF"
    type: CalendarEventType = "custom"
    courseId: str | None = None
    reminderMinutesBefore: int | None = None


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    date: str | None = None
    time: str | None = None
    color: str | None = None
    type: CalendarEventType | None = None
    courseId: str | None = None
    reminderMinutesBefore: int | None = None
    completed: bool | None = None


class NotificationOut(BaseModel):
    id: str
    kind: str = "system"
    title: str
    body: str = ""
    icon: str = "🔔"
    link: str | None = None
    read: bool = False
    createdAt: int = 0
