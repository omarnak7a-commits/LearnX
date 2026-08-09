"""
Auth business logic — real Google OAuth, real JWT issuance, and real password management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    UNUSABLE_PASSWORD_HASH,
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.auth import (
    AuditEventType,
    AuditLog,
    EmailVerificationToken,
    PasswordResetToken,
    PendingGoogleSignup,
    RefreshToken,
)
from app.models.profile import AuthProvider, User, UserRole
from app.services.email import send_password_reset_email, send_verification_email
from app.services.google_oauth import GoogleUserInfo

settings = get_settings()


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EmailAlreadyRegistered(AuthError):
    def __init__(self) -> None:
        super().__init__("An account with this email already exists.", 409)


class InvalidCredentials(AuthError):
    def __init__(self) -> None:
        super().__init__("Incorrect email or password.", 401)


class AccountDisabled(AuthError):
    def __init__(self) -> None:
        super().__init__("This account has been disabled.", 403)


class EmailNotVerified(AuthError):
    def __init__(self) -> None:
        super().__init__("Please verify your email address before continuing.", 403)


class InvalidOrExpiredToken(AuthError):
    def __init__(self, what: str = "token") -> None:
        super().__init__(f"This {what} is invalid or has expired.", 400)


def _log(db: Session, event: AuditEventType, user_id: str | None, detail: str = "",
         ip: str | None = None, user_agent: str | None = None) -> None:
    try:
        db.add(AuditLog(user_id=user_id, event_type=event, detail=detail,
                         ip_address=ip, user_agent=user_agent))
    except Exception:
        pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def register_user(db: Session, full_name: str, email: str, password: str, role: str,
                   ip: str | None, user_agent: str | None) -> tuple[User, str]:
    email = email.lower().strip()
    if get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegistered()

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole(role),
        provider=AuthProvider.email,
        email_verified=False,
        onboarding_complete=False,
    )
    db.add(user)
    db.flush()

    raw_token = _issue_verification_token(db, user)
    _log(db, AuditEventType.register, user.id, detail=f"role={role}", ip=ip, user_agent=user_agent)
    db.commit()
    db.refresh(user)
    return user, raw_token


def _issue_verification_token(db: Session, user: User) -> str:
    raw_token = generate_opaque_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(hours=settings.email_verification_token_ttl_hours),
        )
    )
    return raw_token


def send_verification_email_for(user: User, raw_token: str) -> None:
    verify_url = f"{settings.app_base_url}/verify-email?token={raw_token}"
    send_verification_email(user.email, user.full_name, verify_url)


def resend_verification(db: Session, email: str) -> str | None:
    user = get_user_by_email(db, email)
    if user is None or user.email_verified:
        return None
    raw_token = _issue_verification_token(db, user)
    _log(db, AuditEventType.email_verification_resent, user.id)
    db.commit()
    return raw_token


def verify_email(db: Session, raw_token: str) -> User:
    token_hash = hash_token(raw_token)
    record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    if record is None or record.used_at is not None or record.expires_at < datetime.utcnow():
        raise InvalidOrExpiredToken("verification link")

    user = get_user_by_id(db, record.user_id)
    if user is None:
        raise InvalidOrExpiredToken("verification link")

    user.email_verified = True
    record.used_at = datetime.utcnow()
    _log(db, AuditEventType.email_verified, user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate_with_password(db: Session, email: str, password: str,
                                ip: str | None, user_agent: str | None) -> User:
    email = email.lower().strip()
    user = get_user_by_email(db, email)

    if user is None or user.provider != AuthProvider.email:
        verify_password(password, UNUSABLE_PASSWORD_HASH)
        _log(db, AuditEventType.login_failed, user.id if user else None,
             detail=f"email={email}", ip=ip, user_agent=user_agent)
        db.commit()
        raise InvalidCredentials()

    if not verify_password(password, user.hashed_password):
        _log(db, AuditEventType.login_failed, user.id, detail=f"email={email}", ip=ip, user_agent=user_agent)
        db.commit()
        raise InvalidCredentials()

    if not user.is_active:
        raise AccountDisabled()

    if settings.require_email_verification and not user.email_verified:
        raise EmailNotVerified()

    user.last_login = datetime.utcnow()
    _log(db, AuditEventType.login_success, user.id, ip=ip, user_agent=user_agent)
    db.commit()
    db.refresh(user)
    return user


@dataclass
class GoogleAuthOutcome:
    user: User | None
    pending_token: str | None


PENDING_GOOGLE_SIGNUP_TTL_MINUTES = 10


def login_or_register_with_google(db: Session, info: GoogleUserInfo,
                                   ip: str | None, user_agent: str | None) -> GoogleAuthOutcome:
    existing_by_sub = db.scalar(select(User).where(User.google_sub == info.sub))
    if existing_by_sub is not None:
        existing_by_sub.last_login = datetime.utcnow()
        _log(db, AuditEventType.google_login, existing_by_sub.id, ip=ip, user_agent=user_agent)
        db.commit()
        db.refresh(existing_by_sub)
        return GoogleAuthOutcome(user=existing_by_sub, pending_token=None)

    existing_by_email = get_user_by_email(db, info.email)
    if existing_by_email is not None:
        if info.email_verified:
            existing_by_email.google_sub = info.sub
            existing_by_email.last_login = datetime.utcnow()
            _log(db, AuditEventType.google_login, existing_by_email.id, ip=ip, user_agent=user_agent)
            db.commit()
            db.refresh(existing_by_email)
            return GoogleAuthOutcome(user=existing_by_email, pending_token=None)
        raise AuthError(
            "An account with this email already exists. Please log in with your password.",
            409,
        )

    raw_pending_token = generate_opaque_token()
    db.add(
        PendingGoogleSignup(
            token_hash=hash_token(raw_pending_token),
            google_sub=info.sub,
            email=info.email.lower(),
            email_verified=info.email_verified,
            full_name=info.full_name,
            avatar_url=info.picture,
            expires_at=datetime.utcnow() + timedelta(minutes=PENDING_GOOGLE_SIGNUP_TTL_MINUTES),
        )
    )
    _log(db, AuditEventType.google_login, None, detail=f"pending_signup email={info.email}", ip=ip, user_agent=user_agent)
    db.commit()
    return GoogleAuthOutcome(user=None, pending_token=raw_pending_token)


def complete_google_signup(db: Session, raw_pending_token: str, role: str,
                            ip: str | None, user_agent: str | None) -> User:
    token_hash = hash_token(raw_pending_token)
    record = db.scalar(select(PendingGoogleSignup).where(PendingGoogleSignup.token_hash == token_hash))
    if record is None or record.used_at is not None or record.expires_at < datetime.utcnow():
        raise InvalidOrExpiredToken("Google sign-up session")

    if db.scalar(select(User).where(User.google_sub == record.google_sub)) is not None:
        raise AuthError("This Google account has already completed sign-up. Please sign in instead.", 409)
    if get_user_by_email(db, record.email) is not None:
        raise AuthError("An account with this email already exists. Please sign in instead.", 409)

    user = User(
        email=record.email,
        hashed_password=UNUSABLE_PASSWORD_HASH,
        full_name=record.full_name,
        role=UserRole(role),
        provider=AuthProvider.google,
        google_sub=record.google_sub,
        avatar_url=record.avatar_url,
        email_verified=record.email_verified,
        onboarding_complete=False,
    )
    db.add(user)
    db.flush()
    user.last_login = datetime.utcnow()
    record.used_at = datetime.utcnow()
    _log(db, AuditEventType.google_login, user.id, detail="new_account", ip=ip, user_agent=user_agent)
    db.commit()
    db.refresh(user)
    return user


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


def issue_tokens(db: Session, user: User, remember_me: bool,
                  ip: str | None, user_agent: str | None, family_id: str | None = None) -> IssuedTokens:
    role_val = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_access_token(user.id, role_val)

    raw_refresh = generate_opaque_token()
    ttl_days = (
        settings.refresh_token_ttl_days_remember_me if remember_me else settings.refresh_token_ttl_days
    )
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)

    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=expires_at,
        remember_me=remember_me,
        ip_address=ip,
        user_agent=user_agent,
    )
    if family_id:
        record.family_id = family_id
    db.add(record)
    db.commit()

    return IssuedTokens(access_token=access_token, refresh_token=raw_refresh, refresh_expires_at=expires_at)


def rotate_refresh_token(db: Session, raw_refresh_token: str,
                          ip: str | None, user_agent: str | None) -> tuple[User, IssuedTokens]:
    token_hash = hash_token(raw_refresh_token)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if record is None:
        raise InvalidOrExpiredToken("session")

    if record.revoked_at is not None:
        db.query(RefreshToken).filter(
            RefreshToken.family_id == record.family_id, RefreshToken.revoked_at.is_(None)
        ).update({RefreshToken.revoked_at: datetime.utcnow()})
        _log(db, AuditEventType.refresh_reuse_detected, record.user_id, ip=ip, user_agent=user_agent)
        db.commit()
        raise InvalidOrExpiredToken("session")

    if record.expires_at < datetime.utcnow():
        raise InvalidOrExpiredToken("session")

    user = get_user_by_id(db, record.user_id)
    if user is None or not user.is_active:
        raise InvalidOrExpiredToken("session")

    record.revoked_at = datetime.utcnow()
    new_tokens = issue_tokens(db, user, record.remember_me, ip, user_agent, family_id=record.family_id)

    new_record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(new_tokens.refresh_token))
    )
    if new_record:
        record.replaced_by_id = new_record.id
    db.commit()

    return user, new_tokens


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record and record.revoked_at is None:
        record.revoked_at = datetime.utcnow()
        _log(db, AuditEventType.logout, record.user_id)
        db.commit()


def revoke_all_sessions(db: Session, user: User) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: datetime.utcnow()})
    user.refresh_token_version += 1
    _log(db, AuditEventType.logout_all, user.id)
    db.commit()


def request_password_reset(db: Session, email: str, ip: str | None) -> str | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None

    raw_token = generate_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.password_reset_token_ttl_minutes),
            request_ip=ip,
        )
    )
    _log(db, AuditEventType.password_reset_requested, user.id, ip=ip)
    db.commit()
    return raw_token


def send_password_reset_email_for(user_email: str, full_name: str, raw_token: str) -> None:
    reset_url = f"{settings.app_base_url}/reset-password?token={raw_token}"
    send_password_reset_email(user_email, full_name, reset_url)


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    token_hash = hash_token(raw_token)
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if record is None or record.used_at is not None or record.expires_at < datetime.utcnow():
        raise InvalidOrExpiredToken("reset link")

    user = get_user_by_id(db, record.user_id)
    if user is None:
        raise InvalidOrExpiredToken("reset link")

    user.hashed_password = hash_password(new_password)
    user.provider = AuthProvider.email
    record.used_at = datetime.utcnow()

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: datetime.utcnow()})
    user.refresh_token_version += 1

    _log(db, AuditEventType.password_reset_completed, user.id)
    db.commit()
    db.refresh(user)
    return user
