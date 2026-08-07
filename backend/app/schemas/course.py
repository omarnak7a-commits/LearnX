"""Course API schemas — mirror the frontend `src/types/course.ts` shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CourseStatus = Literal["draft", "pending-review", "published", "archived"]
CourseType = Literal["university", "public", "premium"]
LessonType = Literal["video", "pdf", "notes", "quiz", "assignment"]


class LessonResourceIn(BaseModel):
    name: str
    kind: Literal["pdf", "docx", "ppt", "link", "dataset"]
    sizeLabel: str = ""


class LessonOut(BaseModel):
    id: str
    title: str
    type: LessonType
    durationMinutes: int | None = None
    completed: bool = False
    resources: list = []


class LessonIn(BaseModel):
    title: str
    type: LessonType = "video"
    durationMinutes: int | None = None
    resources: list[LessonResourceIn] = []


class ModuleOut(BaseModel):
    id: str
    title: str
    lessons: list[LessonOut] = []


class ModuleIn(BaseModel):
    title: str


class CourseBase(BaseModel):
    title: str = ""
    description: str = ""
    category: str = ""
    faculty: str = ""
    department: str = ""
    academicLevel: str = ""
    courseType: CourseType = "university"
    status: CourseStatus = "draft"
    color: str = "#2DD4BF"
    icon: str = "📘"
    priceUsd: float | None = None
    allowXpRedemption: bool = False
    xpPrice: int | None = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    faculty: str | None = None
    department: str | None = None
    academicLevel: str | None = None
    courseType: CourseType | None = None
    status: CourseStatus | None = None
    color: str | None = None
    icon: str | None = None
    priceUsd: float | None = None
    allowXpRedemption: bool | None = None
    xpPrice: int | None = None


class CourseOut(CourseBase):
    id: str
    doctorName: str = ""
    doctorInitials: str = ""
    rating: float = 4.5
    studentsCount: int = 0
    completionRate: float = 0.0
    createdAt: str = ""
    lastUpdated: str = ""
    modules: list[ModuleOut] = []
    enrolled: bool = False
    saved: bool = False
    progressPct: int = 0
    completedLessonIds: list[str] = []
    purchasedViaReward: bool = False


class EnrollmentToggleOut(BaseModel):
    enrolled: bool
    progressPct: int = 0


class SavedToggleOut(BaseModel):
    saved: bool


class LessonCompleteOut(BaseModel):
    lessonId: str
    completed: bool
    progressPct: int


class RosterStudentCourse(BaseModel):
    course_id: str
    title: str
    progress_pct: int
    enrolled_at: str | None = None
    completed_at: str | None = None


class RosterStudentOut(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    courses: list[RosterStudentCourse] = []
