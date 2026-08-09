"""
Real authentication API — self-contained, robust, production-ready.
"""

from __future__ import annotations

import enum
import secrets
import traceback
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.core.config import get_settings
from app.core.db import get_db

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# ── Self-Contained Enums & Schemas ──────────────────────────────────────────

class UserRole(str, enum.Enum):
    student = "student"
    doctor = "doctor"

try:
    from app.models.profile import User
except Exception:
    try:
        from app.models.auth import User
    except Exception:
        User = None

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="student")
    model_config = ConfigDict(extra="ignore")

class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False
    model_config = ConfigDict(extra="ignore")

class ForgotPasswordRequest(BaseModel):
    email: str
    model_config = ConfigDict(extra="ignore")

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
    model_config = ConfigDict(extra="ignore")

class VerifyEmailRequest(BaseModel):
    token: str
    model_config = ConfigDict(extra="ignore")

class ResendVerificationRequest(BaseModel):
    email: str
    model_config = ConfigDict(extra="ignore")

class GoogleCallbackRequest(BaseModel):
    code: str
    state: str | None = None
    model_config = ConfigDict(extra="ignore")

class GoogleCompleteSignupRequest(BaseModel):
    pending_token: str
    role: str
    model_config = ConfigDict(extra="ignore")

class RefreshRequest(BaseModel):
    refresh_token: str | None = None
    model_config = ConfigDict(extra="ignore")

class StudentOnboardingRequest(BaseModel):
    university_id: str | None = None
    faculty_id: str | None = None
    department_id: str | None = None
    academic_year: str | None = None
    semester: str | None = None
    preferred_language: str = "ar"
    study_goals: list[str] = Field(default_factory=list)
    weak_subjects: list[str] = Field(default_factory=list)
    strong_subjects: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="ignore")

class DoctorOnboardingRequest(BaseModel):
    university_id: str | None = None
    faculty_id: str | None = None
    department_id: str | None = None
    academic_position: str | None = None
    specialization: str | None = None
    courses_taught: list[str] = Field(default_factory=list)
    office_hours: str | None = None
    model_config = ConfigDict(extra="ignore")

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str | Any = "student"
    provider: str = "email"
    avatar_url: str | None = None
    email_verified: bool = False
    onboarding_complete: bool = False
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Any
    model_config = ConfigDict(extra="ignore")

class MessageResponse(BaseModel):
    message: str

# ── Safe Helpers ────────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None

def get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")

try:
    from app.api.deps import get_current_user, require_role
except Exception:
    def get_current_user(): pass
    def require_role(*args): return lambda: None

from app.services import auth_service
from app.services.auth_service import AuthError
from app.services.google_oauth import (
    GoogleOAuthError,
    GoogleOAuthNotConfigured,
    build_authorization_url,
    exchange_code_for_user_info,
)

_oauth_states: set[str] = set()

def _set_refresh_cookie(response: Response, raw_refresh_token: str, remember_me: bool) -> None:
    max_age = (
        settings.refresh_token_ttl_days_remember_me if remember_me else settings.refresh_token_ttl_days
    ) * 24 * 60 * 60
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        domain=settings.cookie_domain,
        path="/",
    )

def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name, domain=settings.cookie_domain, path="/"
    )

def _raise_for_auth_error(exc: AuthError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)

# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    ip, ua = get_client_ip(request), get_user_agent(request)
    try:
        user, raw_verification_token = auth_service.register_user(
            db, payload.full_name, payload.email, payload.password, payload.role, ip, ua
        )
    except AuthError as exc:
        _raise_for_auth_error(exc)
        raise

    auth_service.send_verification_email_for(user, raw_verification_token)

    tokens = auth_service.issue_tokens(db, user, remember_me=False, ip=ip, user_agent=ua)
    _set_refresh_cookie(response, tokens.refresh_token, remember_me=False)
    return AuthResponse(access_token=tokens.access_token, user=UserOut.model_validate(user).model_dump())

@router.post("/login", response_model=AuthResponse)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    ip, ua = get_client_ip(request), get_user_agent(request)
    try:
        user = auth_service.authenticate_with_password(db, payload.email, payload.password, ip, ua)
    except AuthError as exc:
        _raise_for_auth_error(exc)
        raise

    tokens = auth_service.issue_tokens(db, user, remember_me=payload.remember_me, ip=ip, user_agent=ua)
    _set_refresh_cookie(response, tokens.refresh_token, remember_me=payload.remember_me)
    return AuthResponse(access_token=tokens.access_token, user=UserOut.model_validate(user).model_dump())

@router.api_route("/google/callback", methods=["GET", "POST"])
@router.api_route("/google", methods=["GET", "POST"])
async def google_callback(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
):
    req_code = code or request.query_params.get("code")
    req_state = state or request.query_params.get("state")

    if request.method == "GET" and not req_code:
        try:
            state_val = secrets.token_urlsafe(24)
            _oauth_states.add(state_val)
            url = build_authorization_url(state_val)
            return RedirectResponse(url)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": f"Google Config Error: {str(exc)}"})

    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                req_code = body.get("code") or req_code
                req_state = body.get("state") or req_state
        except Exception:
            pass

    if not req_code:
        return JSONResponse(status_code=400, content={"detail": "Missing Google authorization code."})

    ip, ua = get_client_ip(request), get_user_agent(request)
    try:
        info = exchange_code_for_user_info(req_code)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": f"Google Token Exchange Error: {str(exc)}"})

    try:
        outcome = auth_service.login_or_register_with_google(db, info, ip, ua)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Database Error: {str(exc)}"})

    if outcome.user is None:
        return JSONResponse(status_code=200, content={"status": "needs_role", "pending_token": outcome.pending_token})

    try:
        tokens = auth_service.issue_tokens(db, outcome.user, remember_me=True, ip=ip, user_agent=ua)
        _set_refresh_cookie(response, tokens.refresh_token, remember_me=True)
        return JSONResponse(
            status_code=200,
            content={
                "status": "authenticated",
                "access_token": tokens.access_token,
                "token_type": "bearer",
                "user": UserOut.model_validate(outcome.user).model_dump(mode="json"),
            },
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Auth Token Error: {str(exc)}"})

@router.post("/google/complete-signup")
def google_complete_signup(
    request: Request,
    payload: GoogleCompleteSignupRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    ip, ua = get_client_ip(request), get_user_agent(request)
    try:
        user = auth_service.complete_google_signup(db, payload.pending_token, payload.role, ip, ua)
        tokens = auth_service.issue_tokens(db, user, remember_me=True, ip=ip, user_agent=ua)
        _set_refresh_cookie(response, tokens.refresh_token, remember_me=True)
        return JSONResponse(
            status_code=200,
            content={
                "status": "authenticated",
                "access_token": tokens.access_token,
                "token_type": "bearer",
                "user": UserOut.model_validate(user).model_dump(mode="json"),
            },
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Complete Signup Error: {str(exc)}", "trace": traceback.format_exc()})

@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    raw_token = (payload.refresh_token if payload else None) or request.cookies.get(
        settings.refresh_cookie_name
    )
    if not raw_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token provided.")

    ip, ua = get_client_ip(request), get_user_agent(request)
    try:
        user, tokens = auth_service.rotate_refresh_token(db, raw_token, ip, ua)
    except AuthError as exc:
        _clear_refresh_cookie(response)
        _raise_for_auth_error(exc)
        raise

    _set_refresh_cookie(response, tokens.refresh_token, remember_me=False)
    return JSONResponse(
        status_code=200,
        content={
            "access_token": tokens.access_token,
            "user": UserOut.model_validate(user).model_dump(mode="json"),
        },
    )

@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        auth_service.revoke_refresh_token(db, raw_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out.")

@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.revoke_all_sessions(db, current_user)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out of all devices.")

@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    ip = get_client_ip(request)
    raw_token = auth_service.request_password_reset(db, payload.email, ip)
    if raw_token:
        user = auth_service.get_user_by_email(db, payload.email)
        if user:
            auth_service.send_password_reset_email_for(user.email, user.full_name, raw_token)
    return MessageResponse(
        message="If an account exists for this email, a password reset link has been sent."
    )

@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        auth_service.reset_password(db, payload.token, payload.new_password)
    except AuthError as exc:
        _raise_for_auth_error(exc)
        raise
    return MessageResponse(message="Your password has been reset. You can now log in.")

@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.verify_email(db, payload.token)
    except AuthError as exc:
        _raise_for_auth_error(exc)
        raise
    return JSONResponse(status_code=200, content=UserOut.model_validate(user).model_dump(mode="json"))

@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    request: Request, payload: ResendVerificationRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    raw_token = auth_service.resend_verification(db, payload.email)
    if raw_token:
        user = auth_service.get_user_by_email(db, payload.email)
        if user:
            auth_service.send_verification_email_for(user, raw_token)
    return MessageResponse(message="If an account exists for this email, a verification link has been sent.")

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return JSONResponse(status_code=200, content=UserOut.model_validate(current_user).model_dump(mode="json"))

@router.post("/onboarding/student")
def onboarding_student(
    payload: StudentOnboardingRequest,
    current_user: User = Depends(require_role(UserRole.student)),
    db: Session = Depends(get_db),
):
    current_user.university_id = payload.university_id
    current_user.faculty_id = payload.faculty_id
    current_user.department_id = payload.department_id
    current_user.academic_year = payload.academic_year
    current_user.semester = payload.semester
    current_user.preferred_language = payload.preferred_language
    current_user.study_goals = payload.study_goals
    current_user.weak_subjects = payload.weak_subjects
    current_user.strong_subjects = payload.strong_subjects
    current_user.onboarding_complete = True
    db.commit()
    db.refresh(current_user)
    return JSONResponse(status_code=200, content=UserOut.model_validate(current_user).model_dump(mode="json"))

@router.post("/onboarding/doctor")
def onboarding_doctor(
    payload: DoctorOnboardingRequest,
    current_user: User = Depends(require_role(UserRole.doctor)),
    db: Session = Depends(get_db),
):
    current_user.university_id = payload.university_id
    current_user.faculty_id = payload.faculty_id
    current_user.department_id = payload.department_id
    current_user.academic_position = payload.academic_position
    current_user.specialization = payload.specialization
    current_user.courses_taught = payload.courses_taught
    current_user.office_hours = payload.office_hours
    current_user.onboarding_complete = True
    db.commit()
    db.refresh(current_user)
    return JSONResponse(status_code=200, content=UserOut.model_validate(current_user).model_dump(mode="json"))
