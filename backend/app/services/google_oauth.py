"""
Google OAuth 2.0 — REAL Authorization Code Flow with JWKS verification.

Flow (server-side, PKCE-free client_secret flow):
  1. GET  /api/v1/auth/google        → redirect to Google's consent screen
  2. Google → {GOOGLE_REDIRECT_URI}?code=...&state=...
  3. GET  /api/v1/auth/google/callback?code=...&state=...
     → exchange code for tokens via google_auth_oauthlib.flow.Flow
     → verify the ID token cryptographically with
       google.oauth2.id_token.verify_oauth2_token (JWKS, audience check)
     → upsert user (auth_provider='google') and mint our own session JWT
     → redirect to the frontend with the token.

State parameter: random value stored in a short-lived signed cookie so
the callback cannot be CSRF-replayed.
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import google.auth.transport.requests as google_requests
import google.oauth2.id_token
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleOAuthError(Exception):
    pass


def _require_configured() -> None:
    if not (settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri):
        raise GoogleOAuthError("Google OAuth is not configured (missing GOOGLE_* env vars).")


def build_authorization_url(state: str) -> str:
    """URL to send the browser to Google's consent screen."""
    _require_configured()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def _flow() -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


def exchange_code_for_identity(code: str) -> dict:
    """
    Exchanges the authorization code for tokens, then cryptographically
    verifies the ID token (JWKS + audience + issuer) and returns:
        {"email", "full_name", "avatar_url", "google_sub"}
    """
    _require_configured()
    flow = _flow()
    flow.fetch_token(code=code)

    id_token = flow.credentials.id_token
    if not id_token:
        raise GoogleOAuthError("Google did not return an ID token.")

    # verify_oauth2_token fetches Google's JWKS and validates the
    # signature, audience and expiry. Raises ValueError on any failure.
    request = google_requests.Request()
    claims = google.oauth2.id_token.verify_oauth2_token(
        id_token, request, settings.google_client_id
    )

    email = claims.get("email")
    if not email:
        raise GoogleOAuthError("Google account has no email address.")

    return {
        "email": email.lower(),
        "full_name": claims.get("name") or claims.get("email", "").split("@")[0],
        "avatar_url": claims.get("picture"),
        "google_sub": claims.get("sub"),
    }
