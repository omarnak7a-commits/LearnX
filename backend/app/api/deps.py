"""
Shared FastAPI dependencies — real JWT auth + ownership checks.

`get_current_user` decodes the bearer JWT minted by `app/services/auth.py`
and loads the User row; `get_current_user_id` is kept as a thin helper for
endpoints that only need the id.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.profile import User
from app.services.auth import decode_access_token

settings = get_settings()


def get_current_user_id(authorization: str = Header(default="")) -> str:
    """Extracts and validates the bearer JWT, returning the user id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject claim")
    return user_id


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated")
    return user


def require_role(*roles: str):
    """Dependency factory: e.g. `require_role("doctor")`."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return checker


def require_owner(resource_owner_id: str, current_user_id: str) -> None:
    """Row-level authorization check — call in single-resource GET/PATCH/DELETE."""
    if resource_owner_id != current_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to access this resource")
