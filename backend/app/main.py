"""
LearnX API — FastAPI application entry point.

Run (production):
    uvicorn app.main:app --host 0.0.0.0 --port $PORT

Routes:
    /health                         → liveness probe
    /api/v1/auth/*                  → email/password + Google OAuth
    /api/v1/courses/*               → Course & Roster engine
    /api/v1/file-vault/*            → File Vault (Supabase Storage)
    /api/v1/calendar/*              → Calendar events
    /api/v1/notifications/*         → Notification feed
    /api/v1/planner/*               → Study planner
    /api/v1/videos/*                → Video intelligence
    /ws/videos/{id}/progress        → pipeline progress WebSocket
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    calendar,
    courses,
    file_vault,
    notifications,
    planner,
    video,
    websockets,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LearnX API",
    description="LearnX full-stack backend: real auth (Google OAuth + email), "
    "courses & roster, file vault, calendar, notifications.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(courses.router, prefix=settings.api_prefix)
app.include_router(file_vault.router, prefix=settings.api_prefix)
app.include_router(calendar.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(planner.router, prefix=settings.api_prefix)
app.include_router(video.router, prefix=settings.api_prefix)
app.include_router(websockets.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
