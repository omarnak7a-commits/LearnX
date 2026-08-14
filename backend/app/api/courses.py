"""Course API — Course & Roster engine.

Endpoints (all under /api/v1/courses):
  GET    ""                       → list courses (doctor's own or published catalog)
  POST   ""                       → create course (doctor)
  GET    "/{course_id}"           → course detail incl. student state
  PATCH  "/{course_id}"           → update course (doctor)
  DELETE "/{course_id}"           → delete course (doctor)
  POST   "/{course_id}/modules"   → add module
  POST   "/{course_id}/modules/{module_id}/lessons" → add lesson
  PATCH  "/modules/{module_id}"   → rename module
  PATCH  "/lessons/{lesson_id}"   → rename lesson
  DELETE "/modules/{module_id}"   → delete module (+lessons)
  DELETE "/lessons/{lesson_id}"   → delete lesson
  POST   "/{course_id}/reorder-modules"
  POST   "/modules/{module_id}/reorder-lessons"
  POST   "/{course_id}/enroll"    → enroll / unenroll
  POST   "/{course_id}/save"      → toggle saved
  POST   "/{course_id}/lessons/{lesson_id}/complete" → toggle lesson completion
  GET    "/roster/students"       → doctor's students with progress
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.db import get_db
from app.models.course import Course, CourseModule
from app.models.profile import User
from app.schemas.course import (
    CourseCreate,
    CourseOut,
    CourseUpdate,
    EnrollmentToggleOut,
    LessonCompleteOut,
    LessonIn,
    ModuleIn,
    ModuleOut,
    RosterStudentOut,
    SavedToggleOut,
)
from app.services import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


def _module_out(db: Session, module: CourseModule, student_id: str | None = None) -> ModuleOut:
    completed_ids: set[str] = set()
    if student_id is not None:
        from app.services.course_service import student_course_state

        state = student_course_state(db, module.course, student_id)
        completed_ids = set(state["completed_lesson_ids"])
    return ModuleOut(
        id=str(module.id),
        title=module.title,
        lessons=[
            {
                "id": str(l.id),
                "title": l.title,
                "type": l.type.value,
                "durationMinutes": l.duration_minutes,
                "completed": str(l.id) in completed_ids,
                "resources": l.resources or [],
            }
            for l in module.lessons
        ],
    )


def _course_out(db: Session, course: Course, student: User | None = None) -> CourseOut:
    modules = [_module_out(db, m, str(student.id) if student else None) for m in course.modules]
    state = course_service.student_course_state(db, course, str(student.id)) if student else {
        "enrolled": False, "saved": False, "purchased_via_reward": False,
        "progress_pct": 0, "completed_lesson_ids": [], "completed_at": None,
        "last_viewed_at": None,
    }
    doctor = db.get(User, course.doctor_id) if course.doctor_id else None
    return CourseOut(
        id=str(course.id),
        title=course.title,
        description=course.description,
        category=course.category,
        faculty=course.faculty,
        department=course.department,
        academicLevel=course.academic_level,
        courseType=course.course_type.value,
        status=course.status.value,
        color=course.color,
        icon=course.icon,
        priceUsd=course.price_usd,
        allowXpRedemption=course.allow_xp_redemption,
        xpPrice=course.xp_price,
        doctorName=doctor.full_name if doctor else "",
        doctorInitials="".join(w[0] for w in (doctor.full_name.split() if doctor else [])[:2]).upper(),
        rating=course.rating,
        studentsCount=course.students_count,
        completionRate=course.completion_rate,
        createdAt=course.created_at.isoformat() if course.created_at else "",
        lastUpdated=course.last_updated.isoformat() if course.last_updated else "",
        modules=modules,
        enrolled=state["enrolled"],
        saved=state["saved"],
        progressPct=state["progress_pct"],
        completedLessonIds=state["completed_lesson_ids"],
        purchasedViaReward=state["purchased_via_reward"],
    )


@router.get("", response_model=list[CourseOut])
def list_courses(
    scope: str = "catalog",  # "catalog" (published) | "mine" (doctor's)
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseOut]:
    if scope == "mine":
        if user.role != "doctor":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only doctors have their own courses.")
        courses = course_service.list_courses(db, doctor_id=str(user.id))
    else:
        courses = course_service.list_courses(db, published_only=True)
    return [_course_out(db, c, user) for c in courses]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> CourseOut:
    data = payload.model_dump()
    # camelCase → snake_case for the service layer
    snake = {
        "academicLevel": "academic_level",
        "courseType": "course_type",
        "priceUsd": "price_usd",
        "allowXpRedemption": "allow_xp_redemption",
        "xpPrice": "xp_price",
    }
    normalized = {snake.get(k, k): v for k, v in data.items()}
    course = course_service.create_course(db, str(user.id), normalized)
    return _course_out(db, course, user)


@router.get("/roster/students", response_model=list[RosterStudentOut])
def roster_students(
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> list[RosterStudentOut]:
    return course_service.doctor_roster(db, str(user.id))


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseOut:
    course = course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    if course.status != "published" and course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    return _course_out(db, course, user)


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: str,
    payload: CourseUpdate,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> CourseOut:
    course = course_service.get_course(db, course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    snake = {
        "academicLevel": "academic_level",
        "courseType": "course_type",
        "priceUsd": "price_usd",
        "allowXpRedemption": "allow_xp_redemption",
        "xpPrice": "xp_price",
    }
    data = {snake.get(k, k): v for k, v in payload.model_dump(exclude_unset=True).items()}
    course = course_service.update_course(db, course, data)
    return _course_out(db, course, user)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_course(
    course_id: str,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> Response:
    course = course_service.get_course(db, course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    course_service.delete_course(db, course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{course_id}/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def add_module(
    course_id: str,
    payload: ModuleIn,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> ModuleOut:
    course = course_service.get_course(db, course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    module = course_service.add_module(db, course_id, payload.title)
    db.refresh(module)
    return _module_out(db, module)


@router.post("/{course_id}/modules/{module_id}/lessons", status_code=status.HTTP_201_CREATED)
def add_lesson(
    course_id: str,
    module_id: str,
    payload: LessonIn,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> dict:
    course = course_service.get_course(db, course_id)
    module = db.get(CourseModule, module_id)
    if course is None or course.doctor_id != user.id or module is None or module.course_id != course_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    lesson = course_service.add_lesson(
        db, module_id, payload.title, payload.type,
    )
    if payload.resources:
        lesson.resources = [r.model_dump() for r in payload.resources]
        db.commit()
    return {"id": str(lesson.id), "title": lesson.title, "type": lesson.type.value}


@router.patch("/modules/{module_id}")
def rename_module(
    module_id: str,
    payload: ModuleIn,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> dict:
    module = db.get(CourseModule, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course = db.get(Course, module.course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course_service.update_module_title(db, module_id, payload.title)
    return {"ok": True}


@router.patch("/lessons/{lesson_id}")
def rename_lesson(
    lesson_id: str,
    payload: LessonIn,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.course import CourseLesson

    lesson = db.get(CourseLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found.")
    module = db.get(CourseModule, lesson.module_id)
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found.")
    course_service.update_lesson_title(db, lesson_id, payload.title)
    return {"ok": True}


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_module(
    module_id: str,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> Response:
    module = db.get(CourseModule, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course = db.get(Course, module.course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course_service.delete_module(db, module_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_lesson(
    lesson_id: str,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> Response:
    from app.models.course import CourseLesson

    lesson = db.get(CourseLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found.")
    module = db.get(CourseModule, lesson.module_id)
    course = db.get(Course, module.course_id) if module else None
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found.")
    course_service.delete_lesson(db, lesson_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{course_id}/reorder-modules")
def reorder_modules(
    course_id: str,
    payload: dict,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> dict:
    course = course_service.get_course(db, course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    course_service.reorder_modules(db, course_id, payload.get("moduleIds", []))
    return {"ok": True}


@router.post("/modules/{module_id}/reorder-lessons")
def reorder_lessons(
    module_id: str,
    payload: dict,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
) -> dict:
    module = db.get(CourseModule, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course = db.get(Course, module.course_id)
    if course is None or course.doctor_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found.")
    course_service.reorder_lessons(db, module_id, payload.get("lessonIds", []))
    return {"ok": True}


@router.post("/{course_id}/enroll", response_model=EnrollmentToggleOut)
def enroll(
    course_id: str,
    payload: dict | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrollmentToggleOut:
    course = course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    state = course_service.student_course_state(db, course, str(user.id))
    if state["enrolled"]:
        course_service.unenroll(db, course, str(user.id))
        return EnrollmentToggleOut(enrolled=False, progressPct=0)
    purchased = bool(payload and payload.get("purchasedViaReward"))
    course_service.enroll(db, course, str(user.id), purchased_via_reward=purchased)
    return EnrollmentToggleOut(enrolled=True, progressPct=0)


@router.post("/{course_id}/save", response_model=SavedToggleOut)
def save_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedToggleOut:
    course = course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    saved = course_service.toggle_saved(db, course, str(user.id))
    return SavedToggleOut(saved=saved)


@router.post("/{course_id}/lessons/{lesson_id}/complete", response_model=LessonCompleteOut)
def complete_lesson(
    course_id: str,
    lesson_id: str,
    payload: dict | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LessonCompleteOut:
    course = course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    result = course_service.mark_lesson_complete(
        db, course, str(user.id), lesson_id,
        completed=bool(payload.get("completed")) if payload else True,
    )
    return LessonCompleteOut(**result)
