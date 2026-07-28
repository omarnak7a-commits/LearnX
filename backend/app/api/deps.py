"""
Shared FastAPI dependencies — auth + ownership checks.

Reference implementation — real JWT validation, not wired to a running
auth provider here.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def get_current_user_id(authorization: str = Header(default="")) -> str:
    """
    Extracts and validates the bearer JWT, returning the authenticated
    user's ID. Every router in app/api/* depends on this so no endpoint
    can accidentally skip authentication.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject claim")
    return user_id


def require_owner(resource_owner_id: str, current_user_id: str) -> None:
    """Row-level authorization check — call this in every single-resource GET/PATCH/DELETE."""
    if resource_owner_id != current_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to access this resource")
