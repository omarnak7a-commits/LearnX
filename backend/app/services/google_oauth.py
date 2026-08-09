"""
Real Google OAuth 2.0 (Authorization Code flow) — not a simulated login.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings

settings = get_settings()

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

class GoogleOAuthNotConfigured(RuntimeError): pass
class GoogleOAuthError(RuntimeError): pass

@dataclass
class GoogleUserInfo:
    sub: str
    email: str
    email_verified: bool
    full_name: str
    picture: str | None


def generate_state() -> str:
    """Generates a secure random OAuth state token."""
    return secrets.token_urlsafe(32)


def get_oauth_credentials() -> tuple[str, str, str]:
    cid = settings.google_client_id or os.environ.get("GOOGLE_CLIENT_ID", "")
    csec = settings.google_client_secret or os.environ.get("GOOGLE_CLIENT_SECRET", "")
    ruri = settings.google_redirect_uri or os.environ.get(
        "GOOGLE_REDIRECT_URI", "https://learn-x-ofvm.vercel.app/auth/callback/google"
    )
    if not (cid and csec):
        raise GoogleOAuthNotConfigured("Google OAuth credentials are not fully configured.")
    return cid, csec, ruri


def build_authorization_url(state: str | None = None) -> str:
    cid, _, ruri = get_oauth_credentials()
    actual_state = state or generate_state()
    params = {
        "client_id": cid,
        "redirect_uri": ruri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": actual_state,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_user_info(code: str) -> GoogleUserInfo:
    cid, csec, ruri = get_oauth_credentials()

    token_response = httpx.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": cid,
            "client_secret": csec,
            "redirect_uri": ruri,
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    if token_response.status_code != 200:
        raise GoogleOAuthError(f"Google token exchange failed: {token_response.text}")

    token_payload = token_response.json()
    raw_id_token = token_payload.get("id_token")
    if not raw_id_token:
        raise GoogleOAuthError("Google token response did not include an id_token")

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            cid,
        )
    except ValueError as exc:
        raise GoogleOAuthError(f"Invalid Google ID token: {exc}") from exc

    return GoogleUserInfo(
        sub=claims["sub"],
        email=claims["email"],
        email_verified=bool(claims.get("email_verified", False)),
        full_name=claims.get("name") or claims["email"].split("@")[0],
        picture=claims.get("picture"),
    )


# Aliases for 100% full compatibility across all auth routers
exchange_code_for_identity = exchange_code_for_user_info
get_google_user_info = exchange_code_for_user_info
verify_google_token = exchange_code_for_user_info
