"""Auth helpers — password hashing (bcrypt), JWT minting, token hashing."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import get_settings

settings = get_settings()

# bcrypt only uses the first 72 bytes; truncating up front keeps hashing
# deterministic across library versions instead of raising on long input.
_MAX_PW_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_PW_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, role: str = "student") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def hash_token(token: str) -> str:
    """Store only SHA-256 digests of one-time tokens (verify/reset)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry(hours: int = 24) -> datetime:
    return datetime.utcnow() + timedelta(hours=hours)
