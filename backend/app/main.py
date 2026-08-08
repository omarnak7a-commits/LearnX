from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import auth, calendar, courses, file_vault, notifications, planner, video, websockets
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title="LearnX API",
    description="Production authentication + Courses + File Vault + Calendar backend.",
    version="0.2.0",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
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
app.include_router(video.router, prefix=settings.api_prefix)
app.include_router(planner.router, prefix=settings.api_prefix)
app.include_router(websockets.router)

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "google_oauth_configured": settings.google_oauth_configured,
        "email_delivery_configured": settings.email_delivery_configured,
    }

@app.api_route("/api/migrate", methods=["GET", "POST"])
@app.api_route("/migrate", methods=["GET", "POST"])
def migrate_database() -> dict:
    try:
        import app.models
        from app.core.db import Base, engine
        Base.metadata.create_all(bind=engine)
        return {
            "status": "ok",
            "message": "Database tables created successfully on Supabase Postgres",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.on_event("startup")
def auto_create_tables():
    try:
        import app.models
        from app.core.db import Base, engine
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
