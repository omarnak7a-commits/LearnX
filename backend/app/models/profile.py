"""
ORM models for the Student Profile, University/Faculty/Department
directory, and Academic Ranking system.

Mirrors the frontend types in `src/types/profile.ts` and the seed catalog
in `src/data/academicCatalog.ts`. Like every other module in `backend/`,
**nothing here has been run** — see `backend/README.md` for why (no
Postgres, no deployed auth service in this sandbox). This file exists so
a backend team has an exact, typed schema to implement against instead
of reverse-engineering one from the frontend's localStorage-backed
`ProfileContext`.

`planner.py` and `video.py` already reference a `users` table via
`ForeignKey("users.id")` without ever defining it (this repo's backend
skeleton was built feature-by-feature, auth last) — this module is the
first to actually define `User`, which is why it also extends it with
every field the spec's `BACKEND` section calls for:
`university_id`, `faculty_id`, `department_id`, `academic_year`,
`semester`, `study_goals`, `xp`, `level`, `rank`, `badges`, `streak`.

`xp` and `level` are still stored as columns here (unlike the frontend,
which computes them on the fly from live activity — see
`src/hooks/useProfileStats.ts`) because a real backend needs a durable,
queryable value to sort leaderboards by without recomputing every
student's entire course/quiz history on every leaderboard request; a
background job (`app/services/ranking.py`, not yet written) would be
responsible for keeping `xp`/`level`/`rank` in sync whenever a scoring
event happens, the same way `app/services/study_planner.py` reacts to
`PlanRegenerationTrigger` events for the planner.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AcademicYear(str, enum.Enum):
    year_1 = "year-1"
    year_2 = "year-2"
    year_3 = "year-3"
    year_4 = "year-4"
    year_5 = "year-5"
    graduate = "graduate"


class Semester(str, enum.Enum):
    semester_1 = "semester-1"
    semester_2 = "semester-2"
    summer = "summer"


class RankingScope(str, enum.Enum):
    """Mirrors `RankingScope` in `src/types/profile.ts`."""

    university = "university"
    faculty = "faculty"
    department = "department"
    academic_year = "academicYear"
    course = "course"
    friends = "friends"


class University(Base):
    __tablename__ = "universities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    short_name: Mapped[str] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(128))
    city: Mapped[str] = mapped_column(String(128))

    faculties: Mapped[list["Faculty"]] = relationship(back_populates="university")


class Faculty(Base):
    __tablename__ = "faculties"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    university_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("universities.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    icon: Mapped[str] = mapped_column(String(16), default="🎓")

    university: Mapped["University"] = relationship(back_populates="faculties")
    departments: Mapped[list["Department"]] = relationship(back_populates="faculty")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    faculty_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("faculties.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))

    faculty: Mapped["Faculty"] = relationship(back_populates="departments")


class User(Base):
    """
    The extended User model the spec's `BACKEND` section asks for.

    Auth fields (`email`, `hashed_password`) are the minimal baseline any
    real auth system needs; every academic/progression field below is
    additive on top of that baseline, per the spec's "Extend the existing
    User model" instruction — none of it replaces or removes anything an
    auth system would already need.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    bio: Mapped[str] = mapped_column(Text, default="")

    # ── Academic identity — real foreign keys, never hardcoded/duplicated
    #    strings, matching the spec's "Do NOT hardcode values." ──
    university_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("universities.id"), nullable=True, index=True
    )
    faculty_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("faculties.id"), nullable=True, index=True
    )
    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True, index=True
    )
    academic_year: Mapped[AcademicYear | None] = mapped_column(Enum(AcademicYear), nullable=True)
    semester: Mapped[Semester | None] = mapped_column(Enum(Semester), nullable=True)
    student_id_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    study_goals: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # University/Faculty are only editable post-onboarding if this is
    # explicitly cleared by an admin/transfer-request workflow — mirrors
    # `academicIdentityLocked` in `src/types/profile.ts`.
    academic_identity_locked: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Progression / gamification ──
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    # Cached rank snapshot for the "all students, all-time" scope only —
    # every other scope (faculty/department/course/weekly/monthly/etc.)
    # is served by `app/services/ranking.py` computing a live SQL
    # `RANK() OVER (...)` window query rather than a stored column,
    # since a single integer can't represent "rank in N different
    # simultaneous scopes" without staleness.
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    badges: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_study_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    university: Mapped["University | None"] = relationship()
    faculty: Mapped["Faculty | None"] = relationship()
    department: Mapped["Department | None"] = relationship()


class Friendship(Base):
    """Directed friend-connection edge, used by the leaderboard's
    "Friends" ranking scope. Symmetric friendships are represented as two
    rows (A→B and B→A), created together by the service layer, so a
    single-direction query (`WHERE user_id = :me`) is enough to answer
    "who are my friends" without a join on OR conditions."""

    __tablename__ = "friendships"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)
    friend_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RankingSnapshot(Base):
    """
    Precomputed leaderboard row, refreshed periodically (or on scoring
    events) by `app/services/ranking.py` so the Rankings page can page
    through thousands of students without a live aggregation query per
    request. One row per (user, scope, scope_value, timeframe) tuple —
    e.g. (user=42, scope=faculty, scope_value=<faculty_id>, timeframe=weekly).
    """

    __tablename__ = "ranking_snapshots"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)
    scope: Mapped[RankingScope] = mapped_column(Enum(RankingScope), index=True)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)  # 'weekly' | 'monthly' | 'all-time'
    xp_in_period: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer, index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
