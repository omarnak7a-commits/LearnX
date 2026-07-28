"""
Study Planner API router — the server counterpart to
`src/hooks/useStudyPlan.ts`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.planner import (
    RegeneratePlanRequest,
    RegeneratePlanResponse,
    StudyRecommendationOut,
    StudyTaskOut,
    UpcomingExamOut,
)

router = APIRouter(prefix="/planner", tags=["study-planner"])


@router.get("/tasks", response_model=list[StudyTaskOut])
def list_tasks(user_id: str = Depends(get_current_user_id)) -> list[StudyTaskOut]:
    raise NotImplementedError("Reference stub — query StudyTask rows for the rolling window")


@router.post("/tasks/{task_id}/toggle", response_model=StudyTaskOut)
def toggle_task(task_id: str, user_id: str = Depends(get_current_user_id)) -> StudyTaskOut:
    raise NotImplementedError("Reference stub — flip StudyTask.done and return the updated row")


@router.post("/regenerate", response_model=RegeneratePlanResponse)
def regenerate(
    payload: RegeneratePlanRequest,
    user_id: str = Depends(get_current_user_id),
) -> RegeneratePlanResponse:
    """
    Fired automatically by other routes on the relevant event (e.g. a quiz
    submission handler calls this with trigger=quiz-completed) — never
    requires the student to manually ask for a new plan, matching the
    product requirement "No manual intervention required."
    """
    raise NotImplementedError("Reference stub — see app/services/study_planner.py")


@router.get("/exams", response_model=list[UpcomingExamOut])
def list_exams(user_id: str = Depends(get_current_user_id)) -> list[UpcomingExamOut]:
    raise NotImplementedError("Reference stub — query UpcomingExam rows")


@router.get("/recommendations", response_model=list[StudyRecommendationOut])
def recommendations(user_id: str = Depends(get_current_user_id)) -> list[StudyRecommendationOut]:
    raise NotImplementedError("Reference stub — derive from current StudyTask + mastery scores")
