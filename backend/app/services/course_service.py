"""Course & Roster engine — the service layer behind `/api/v1/courses`.

Responsibilities:
  - CRUD for courses (doctor-owned) + module/lesson tree management.
  - Enrollment & unenrollment, saved/bookmark toggling.
  - Lesson completion → per-student progress %, course completion rate.
  - Doctor roster: all students enrolled in the doctor's courses with
    per-course progress (used by `/api/v1/courses/roster/students`).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course import Course, CourseLesson, CourseModule, Enrollment, LessonProgress
from app.models.profile import User


class CourseError(Exception):
    pass


# ────────────────────────────────────────────────────────────────────
# Course CRUD
# ────────────────────────────────────────────────────────────────────

def create_course(db: Session, doctor_id: str, data: dict) -> Course:
    course = Course(doctor_id=doctor_id, **{k: v for k, v in data.items() if hasattr(Course, k)})
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def get_course(db: Session, course_id: str) -> Course | None:
    return db.get(Course, course_id)


def update_course(db: Session, course: Course, data: dict) -> Course:
    allowed = {
        "title", "description", "category", "faculty", "department",
        "academic_level", "course_type", "status", "color", "icon",
        "price_usd", "allow_xp_redemption", "xp_price",
    }
    for k, v in data.items():
        if k in allowed:
            setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


def list_courses(db: Session, *, doctor_id: str | None = None, published_only: bool = False) -> list[Course]:
    q = select(Course)
    if doctor_id:
        q = q.where(Course.doctor_id == doctor_id)
    if published_only:
        q = q.where(Course.status == "published")
    q = q.order_by(Course.created_at.desc())
    return list(db.scalars(q).all())


def delete_course(db: Session, course_id: str) -> None:
    db.execute(Course.__table__.delete().where(Course.id == course_id))
    db.commit()


# ────────────────────────────────────────────────────────────────────
# Module / Lesson tree
# ────────────────────────────────────────────────────────────────────

def add_module(db: Session, course_id: str, title: str) -> CourseModule:
    count = db.scalar(select(func.count()).select_from(CourseModule).where(CourseModule.course_id == course_id)) or 0
    module = CourseModule(course_id=course_id, title=title, order_index=count)
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


def add_lesson(db: Session, module_id: str, title: str, lesson_type: str) -> CourseLesson:
    count = db.scalar(select(func.count()).select_from(CourseLesson).where(CourseLesson.module_id == module_id)) or 0
    lesson = CourseLesson(module_id=module_id, title=title, type=lesson_type, order_index=count)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


def update_module_title(db: Session, module_id: str, title: str) -> None:
    db.query(CourseModule).filter_by(id=module_id).update({"title": title})
    db.commit()


def update_lesson_title(db: Session, lesson_id: str, title: str) -> None:
    db.query(CourseLesson).filter_by(id=lesson_id).update({"title": title})
    db.commit()


def delete_lesson(db: Session, lesson_id: str) -> None:
    db.query(CourseLesson).filter_by(id=lesson_id).delete()
    db.commit()


def delete_module(db: Session, module_id: str) -> None:
    db.query(CourseLesson).filter(CourseLesson.module_id == module_id).delete()
    db.query(CourseModule).filter_by(id=module_id).delete()
    db.commit()


def reorder_modules(db: Session, course_id: str, module_ids: list[str]) -> None:
    for idx, module_id in enumerate(module_ids):
        db.query(CourseModule).filter_by(id=module_id, course_id=course_id).update({"order_index": idx})
    db.commit()


def reorder_lessons(db: Session, module_id: str, lesson_ids: list[str]) -> None:
    for idx, lesson_id in enumerate(lesson_ids):
        db.query(CourseLesson).filter_by(id=lesson_id, module_id=module_id).update({"order_index": idx})
    db.commit()


# ────────────────────────────────────────────────────────────────────
# Enrollment / progress
# ────────────────────────────────────────────────────────────────────

def enroll(db: Session, course: Course, student_id: str, *, purchased_via_reward: bool = False) -> Enrollment:
    existing = db.scalar(
        select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id)
    )
    if existing:
        return existing
    enrollment = Enrollment(
        course_id=course.id, student_id=student_id, purchased_via_reward=purchased_via_reward
    )
    course.students_count += 1
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def unenroll(db: Session, course: Course, student_id: str) -> None:
    db.query(Enrollment).filter_by(course_id=course.id, student_id=student_id).delete()
    if course.students_count > 0:
        course.students_count -= 1
    db.commit()


def toggle_saved(db: Session, course: Course, student_id: str) -> bool:
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id)
    )
    if enrollment is None:
        enrollment = Enrollment(course_id=course.id, student_id=student_id, saved=True)
        db.add(enrollment)
        db.commit()
        return True
    enrollment.saved = not enrollment.saved
    db.commit()
    return enrollment.saved


def mark_lesson_complete(
    db: Session, course: Course, student_id: str, lesson_id: str, completed: bool = True
) -> dict:
    """Toggles a lesson's completion and recomputes progress + completion rate."""
    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.course_id == course.id,
            LessonProgress.lesson_id == lesson_id,
            LessonProgress.student_id == student_id,
        )
    )
    if progress is None:
        progress = LessonProgress(
            course_id=course.id, lesson_id=lesson_id, student_id=student_id, completed=completed
        )
        db.add(progress)
    else:
        progress.completed = completed
    db.flush()

    lesson_ids = [
        lid
        for (lid,) in db.execute(
            select(CourseLesson.id)
            .join(CourseModule, CourseModule.id == CourseLesson.module_id)
            .where(CourseModule.course_id == course.id)
        ).all()
    ]
    total = len(lesson_ids)
    done = db.scalar(
        select(func.count()).select_from(LessonProgress).where(
            LessonProgress.course_id == course.id,
            LessonProgress.student_id == student_id,
            LessonProgress.completed.is_(True),
        )
    ) or 0

    progress_pct = round(done / total * 100) if total else 0

    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id)
    )
    if enrollment is not None:
        enrollment.last_viewed_at = func.now()
        if completed:
            enrollment.last_lesson_id = lesson_id
        if progress_pct >= 100 and enrollment.completed_at is None:
            enrollment.completed_at = func.now()
        elif progress_pct < 100:
            enrollment.completed_at = None

    # Course-level completion rate = average across enrolled students.
    enrolled = db.scalar(
        select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course.id)
    ) or 0
    if enrolled and total:
        completed_all = db.execute(
            select(LessonProgress.student_id)
            .where(
                LessonProgress.course_id == course.id,
                LessonProgress.completed.is_(True),
            )
            .group_by(LessonProgress.student_id)
            .having(func.count() == total)
        ).scalars().all()
        course.completion_rate = round(len(completed_all) / enrolled * 100, 1)

    db.commit()
    return {"progress_pct": progress_pct, "completed": completed, "lesson_id": lesson_id}


def student_course_state(db: Session, course: Course, student_id: str) -> dict:
    """Enrollment/saved/progress state for one student + one course."""
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student_id)
    )
    total = db.scalar(
        select(func.count())
        .select_from(CourseLesson)
        .join(CourseModule)
        .where(CourseModule.course_id == course.id)
    ) or 0
    done = db.scalar(
        select(func.count()).select_from(LessonProgress).where(
            LessonProgress.course_id == course.id,
            LessonProgress.student_id == student_id,
            LessonProgress.completed.is_(True),
        )
    ) or 0
    completed_ids = set(
        db.execute(
            select(LessonProgress.lesson_id).where(
                LessonProgress.course_id == course.id,
                LessonProgress.student_id == student_id,
                LessonProgress.completed.is_(True),
            )
        ).scalars().all()
    )
    return {
        "enrolled": enrollment is not None,
        "saved": bool(enrollment and enrollment.saved),
        "purchased_via_reward": bool(enrollment and enrollment.purchased_via_reward),
        "progress_pct": round(done / total * 100) if total else 0,
        "completed_lesson_ids": sorted(completed_ids),
        "completed_at": enrollment.completed_at.isoformat() if enrollment and enrollment.completed_at else None,
        "last_viewed_at": enrollment.last_viewed_at.isoformat() if enrollment and enrollment.last_viewed_at else None,
    }


# ────────────────────────────────────────────────────────────────────
# Doctor roster
# ────────────────────────────────────────────────────────────────────

def doctor_roster(db: Session, doctor_id: str) -> list[dict]:
    """All students enrolled in any of the doctor's courses, with progress."""
    course_ids = list(
        db.execute(select(Course.id).where(Course.doctor_id == doctor_id)).scalars().all()
    )
    if not course_ids:
        return []

    rows = db.execute(
        select(
            User.id, User.email, User.full_name, User.avatar_url,
            Course.id, Course.title,
            Enrollment.enrolled_at, Enrollment.completed_at,
        )
        .join(Enrollment, Enrollment.student_id == User.id)
        .join(Course, Course.id == Enrollment.course_id)
        .where(Course.id.in_(course_ids))
        .order_by(User.full_name)
    ).all()

    # per (student, course) progress
    progress_map: dict[tuple[str, str], int] = {}
    for course_id in course_ids:
        lesson_ids = list(
            db.execute(
                select(CourseLesson.id)
                .join(CourseModule, CourseModule.id == CourseLesson.module_id)
                .where(CourseModule.course_id == course_id)
            ).scalars().all()
        )
        total = len(lesson_ids)
        if not total:
            continue
        per_student = db.execute(
            select(LessonProgress.student_id, func.count())
            .where(
                LessonProgress.course_id == course_id,
                LessonProgress.completed.is_(True),
            )
            .group_by(LessonProgress.student_id)
        ).all()
        for student_id, done in per_student:
            progress_map[(student_id, course_id)] = round(done / total * 100)

    grouped: dict[str, dict] = {}
    for student_id, email, full_name, avatar, course_id, course_title, enrolled_at, completed_at in rows:
        entry = grouped.setdefault(
            student_id,
            {
                "id": student_id,
                "email": email,
                "full_name": full_name,
                "avatar_url": avatar,
                "courses": [],
            },
        )
        entry["courses"].append(
            {
                "course_id": course_id,
                "title": course_title,
                "progress_pct": progress_map.get((student_id, course_id), 0),
                "enrolled_at": enrolled_at.isoformat() if enrolled_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None,
            }
        )
    return list(grouped.values())
