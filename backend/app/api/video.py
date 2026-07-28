"""
Video Intelligence API router.

Endpoints mirror what `src/components/dashboard/student/video/*` would
call instead of reading from `src/data/videoIntelligenceMock.ts` once a
real backend exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.schemas.video import (
    VideoChatRequest,
    VideoChatResponse,
    VideoLectureOut,
    VideoUploadInitRequest,
    VideoUploadInitResponse,
)

router = APIRouter(prefix="/videos", tags=["video-intelligence"])


@router.post("/uploads", response_model=VideoUploadInitResponse)
def init_upload(
    payload: VideoUploadInitRequest,
    user_id: str = Depends(get_current_user_id),
) -> VideoUploadInitResponse:
    """
    Step 1 of a resumable upload: validates the declared size/extension
    (see app/services/validation.py), creates a queued VideoLecture row,
    and returns a chunk plan the client uploads against.
    """
    raise NotImplementedError("Reference stub — see app/services/validation.py and app/services/storage.py")


@router.post("/uploads/{upload_id}/complete")
def complete_upload(upload_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Called once every chunk has been PUT. Runs the remaining validation
    (magic bytes + virus scan), then enqueues
    `app.workers.celery_app.process_lecture`.
    """
    raise NotImplementedError("Reference stub — see app/workers/celery_app.py")


@router.get("", response_model=list[VideoLectureOut])
def list_lectures(user_id: str = Depends(get_current_user_id)) -> list[VideoLectureOut]:
    raise NotImplementedError("Reference stub — query VideoLecture rows scoped to user_id")


@router.get("/{lecture_id}", response_model=VideoLectureOut)
def get_lecture(lecture_id: str, user_id: str = Depends(get_current_user_id)) -> VideoLectureOut:
    raise NotImplementedError("Reference stub — fetch + authorize (see app/api/deps.py::require_owner)")


@router.post("/{lecture_id}/chat", response_model=VideoChatResponse)
def chat_with_lecture(
    lecture_id: str,
    payload: VideoChatRequest,
    user_id: str = Depends(get_current_user_id),
) -> VideoChatResponse:
    """Delegates to app/services/rag.py::answer_with_citations — grounded, cited, never hallucinated."""
    raise NotImplementedError("Reference stub — see app/services/rag.py")
