"""
Shared FastAPI dependencies — real JWT auth + ownership checks.

`get_current_user` decodes the bearer JWT minted by `app/services/auth.py`
and loads the User row; `get_current_user_id` is kept as a thin helper for
endpoints that only need the id.

Token extraction is intentionally defensive: some browsers, proxies, and
serverless platforms rewrite the Authorization header (lowercase scheme,
extra quotes/whitespace, or drop it entirely). We accept, in order:

1. `Authorization` (any casing, repeated "Bearer " prefixes, stray quotes)
2. `X-Access-Token` (sent by the frontend on every authenticated call)
3. Vercel's `x-vercel-sc-headers` container — when Vercel's edge network
   moves the original headers (e.g. Authorization) out of the request it
   stores them there as a JSON object.

Any single one is enough for AI/API calls to keep working.
"""

from __future__ import annotations

import json

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.profile import User
from app.services.auth import decode_access_token

settings = get_settings()

_AUTH_ERROR_HEADERS = {"WWW-Authenticate": "Bearer"}


def extract_bearer_token(
    authorization: str | None = None,
    *,
    x_access_token: str | None = None,
) -> str | None:
    """Return a raw JWT from Authorization / X-Access-Token, or None."""

    for raw in (authorization, x_access_token):
        if raw is None:
            continue
        value = str(raw).strip().strip('"').strip("'")
        if not value:
            continue

        # Unwrap repeated "Bearer " prefixes (case-insensitive).
        while True:
            parts = value.split(None, 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                value = parts[1].strip().strip('"').strip("'")
                continue
            break

        if value and value.lower() != "bearer":
            return value
    return None


def _vercel_header_container_token(request: Request) -> str | None:
    """Recover a token Vercel moved into `x-vercel-sc-headers` (JSON object)."""
    raw = request.headers.get("x-vercel-sc-headers")
    if not raw:
        return None
    try:
        container = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(container, dict):
        return None
    for key in ("Authorization", "authorization"):
        value = container.get(key)
        token = extract_bearer_token(value)
        if token:
            return token
    token = extract_bearer_token(
        container.get("X-Access-Token") or container.get("x-access-token")
    )
    if token:
        return token
    return None


def _token_from_request(
    request: Request,
    authorization: str | None,
    x_access_token: str | None,
) -> str | None:
    token = extract_bearer_token(authorization, x_access_token=x_access_token)
    if token:
        return token

    headers = request.headers
    token = extract_bearer_token(
        headers.get("authorization") or headers.get("Authorization"),
        x_access_token=headers.get("x-access-token") or headers.get("X-Access-Token"),
    )
    if token:
        return token

    # Vercel production can relocate the Authorization header entirely.
    return _vercel_header_container_token(request)


def get_current_user_id(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_access_token: str | None = Header(default=None, alias="X-Access-Token"),
) -> str:
    """Extracts and validates the bearer JWT, returning the user id."""
    token = _token_from_request(request, authorization, x_access_token)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing bearer token",
            headers=_AUTH_ERROR_HEADERS,
        )
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers=_AUTH_ERROR_HEADERS,
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token missing subject claim",
            headers=_AUTH_ERROR_HEADERS,
        )
    return str(user_id)


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "User not found or deactivated",
            headers=_AUTH_ERROR_HEADERS,
        )
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
