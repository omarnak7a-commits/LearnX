"""
FastAPI application entry point.

Run (once real dependencies are installed and infra is up — see
backend/README.md):

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import planner, video, websockets
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LearnX API",
    description="AI Video Intelligence + AI Study Planner backend (reference architecture).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video.router, prefix=settings.api_prefix)
app.include_router(planner.router, prefix=settings.api_prefix)
app.include_router(websockets.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
