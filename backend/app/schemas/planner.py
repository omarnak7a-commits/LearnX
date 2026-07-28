"""Pydantic schemas for the AI Study Plan Generator API — mirrors src/types/planner.ts."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class StudyTaskOut(BaseModel):
    id: str
    title: str
    subject: str
    type: Literal[
        "lecture", "revision", "practice", "quiz", "flashcards", "assignment", "break", "exam-prep"
    ]
    priority: Literal["low", "medium", "high", "critical"]
    start_minute: int
    duration_minutes: int
    day: int
    done: bool
    ai_reason: str


class UpcomingExamOut(BaseModel):
    id: str
    subject: str
    title: str
    date: str
    days_away: int
    readiness: int


class WeakTopicOut(BaseModel):
    subject: str
    topic: str
    mastery_pct: int
    trend: Literal["up", "down", "flat"]


class StudyRecommendationOut(BaseModel):
    id: str
    icon: str
    title: str
    body: str
    action_label: str
    kind: Literal["next", "revise", "break", "lecture", "quiz", "flashcards", "weak-topic"]


class PlanRegenerationTrigger(str, Enum):
    quiz_completed = "quiz-completed"
    lecture_uploaded = "lecture-uploaded"
    exam_added = "exam-added"
    assignment_submitted = "assignment-submitted"
    performance_improved = "performance-improved"
    performance_declined = "performance-declined"


class RegeneratePlanRequest(BaseModel):
    trigger: PlanRegenerationTrigger
    context: dict = {}


class RegeneratePlanResponse(BaseModel):
    message: str
    tasks: list[StudyTaskOut]
