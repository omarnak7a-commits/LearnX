"""Auth API — email/password + Google OAuth 2.0 (real flows).

Endpoints:
  POST /auth/register          → create account, send verification email
  POST /auth/login             → issue session JWT
  GET  /auth/me                → current user (requires bearer token)
  POST /auth/verify-email      → verify with emailed token
  POST /auth/resend-verification
  POST /auth/forgot-password   → email a reset link
  POST /auth/reset-password    → set new password with emailed token
  GET  /auth/google            → redirect to Google consent screen
  GET  /auth/google/callback   → exchange code, verify ID token (JWKS),
                                 upsert user, redirect to frontend with JWT
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.auth_tokens import EmailVerificationToken, PasswordResetToken
from app.models.profile import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.services import email as email_service
from app.services.auth import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    token_expiry,
    verify_password,
)
from app.services.google_oauth import (
    GoogleOAuthError,
    build_authorization_url,
    exchange_code_for_identity,
    generate_state,
)
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        auth_provider=user.auth_provider,
        is_verified=user.is_verified,
        avatar_url=user.avatar_url,
        onboarding_complete=user.onboarding_complete,
    )


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(str(user.id), user.role),
        user=_user_out(user),
        requires_email_verification=settings.require_email_verification and not user.is_verified,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="student",
        auth_provider="email",
        is_verified=not settings.require_email_verification,
    )
    db.add(user)
    db.flush()

    if settings.require_email_verification:
        token = generate_token()
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=token_expiry(),
            )
        )
    db.commit()
    db.refresh(user)

    if settings.require_email_verification:
        verify_url = f"{settings.app_base_url}/verify-email?token={token}"
        try:
            email_service.send_verification_email(user.email, user.full_name, verify_url)
        except email_service.EmailError as exc:
            logger.warning("verification email not sent: %s", exc)

    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated.")

    user.last_login_at = datetime.utcnow()
    db.commit()
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post("/verify-email", response_model=UserOut)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> UserOut:
    record = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(payload.token)
        )
    )
    if record is None or record.used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid verification token.")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification token expired.")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    record.used = True
    user.is_verified = True
    db.commit()

    try:
        email_service.send_welcome_email(user.email, user.full_name)
    except email_service.EmailError:
        pass
    return _user_out(user)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is not None and not user.is_verified:
        token = generate_token()
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=token_expiry(),
            )
        )
        db.commit()
        verify_url = f"{settings.app_base_url}/verify-email?token={token}"
        try:
            email_service.send_verification_email(user.email, user.full_name, verify_url)
        except email_service.EmailError as exc:
            logger.warning("verification email not sent: %s", exc)
    # Always 202 to avoid account enumeration.
    return {"ok": True}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is not None:
        token = generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=token_expiry(),
            )
        )
        db.commit()
        reset_url = f"{settings.app_base_url}/reset-password?token={token}"
        try:
            email_service.send_password_reset_email(user.email, user.full_name, reset_url)
        except email_service.EmailError as exc:
            logger.warning("reset email not sent: %s", exc)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    record = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token)
        )
    )
    if record is None or record.used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid reset token.")
    if record.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token expired.")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    record.used = True
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


# ────────────────────────────────────────────────────────────────────
# Google OAuth 2.0
# ────────────────────────────────────────────────────────────────────

STATE_COOKIE = "learnx_oauth_state"


@router.get("/google")
def google_login() -> RedirectResponse:
    state = generate_state()
    try:
        url = build_authorization_url(state)
    except GoogleOAuthError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    resp = RedirectResponse(url)
    resp.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=600,
    )
    return resp


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not state or state != cookie_state:
        return RedirectResponse(f"{settings.app_base_url}/login?error=invalid_state")
    if not code:
        return RedirectResponse(f"{settings.app_base_url}/login?error=access_denied")

    try:
        identity = exchange_code_for_identity(code)
    except (GoogleOAuthError, ValueError) as exc:
        logger.warning("google exchange failed: %s", exc)
        return RedirectResponse(f"{settings.app_base_url}/login?error=google_auth_failed")

    email = identity["email"]
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            hashed_password=None,
            full_name=identity["full_name"],
            avatar_url=identity.get("avatar_url"),
            auth_provider="google",
            role="student",
            is_verified=True,
        )
        db.add(user)
    else:
        user.auth_provider = "google"
        if not user.full_name and identity["full_name"]:
            user.full_name = identity["full_name"]
        user.is_verified = True
        if identity.get("avatar_url"):
            user.avatar_url = identity["avatar_url"]

    user.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token(str(user.id), user.role)
    resp = RedirectResponse(f"{settings.app_base_url}/auth/callback/google?token={token}")
    resp.delete_cookie(STATE_COOKIE)
    return resp
