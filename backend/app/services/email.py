"""
Email delivery — REAL Resend integration.

Used for:
  - Email verification (activation) with a signed verify link.
  - Password reset with a signed reset link.
  - (Optional) transactional notifications to enrolled students.

All sends go through `resend.Emails.send` with the configured
`RESEND_API_KEY` and `EMAIL_FROM_ADDRESS`.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_initialized = False


def _init_resend() -> None:
    global _initialized
    if not _initialized:
        import resend

        resend.api_key = settings.resend_api_key
        _initialized = True


class EmailError(Exception):
    pass


def _send(to: str, subject: str, html: str, text: str | None = None) -> str | None:
    """Low-level send. Returns the Resend message id."""
    if not settings.resend_api_key:
        raise EmailError("RESEND_API_KEY is not configured.")
    _init_resend()
    import resend

    try:
        resp = resend.Emails.send(
            {
                "from": settings.email_from_address,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text or "",
            }
        )
        # resend >= 2.x returns a SendResponse object with `.id`;
        # older 1.x versions returned a dict with `id` key.
        message_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else None)
        logger.info("email sent to=%s subject=%r id=%s", to, subject, message_id)
        return message_id
    except Exception as exc:  # resend raises ResendError on API failure
        logger.exception("email send failed to=%s", to)
        raise EmailError(f"Failed to send email: {exc}") from exc


def send_verification_email(to: str, full_name: str, verify_url: str) -> str | None:
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2 style="color:#0f172a">Welcome to LearnX, {full_name} 👋</h2>
      <p style="color:#334155;font-size:15px">Almost done — confirm your email address to activate your account.</p>
      <p><a href="{verify_url}" style="background:#2DD4BF;color:#042f2e;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:bold">Verify my email</a></p>
      <p style="color:#64748b;font-size:13px">This link expires in 24 hours. If you didn't create a LearnX account, ignore this email.</p>
    </div>"""
    text = f"Welcome to LearnX, {full_name}! Confirm your email by opening: {verify_url} (valid 24h)."
    return _send(to, "Verify your LearnX email", html, text)


def send_password_reset_email(to: str, full_name: str, reset_url: str) -> str | None:
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2 style="color:#0f172a">Reset your LearnX password</h2>
      <p style="color:#334155;font-size:15px">Hi {full_name}, use the button below to choose a new password.</p>
      <p><a href="{reset_url}" style="background:#2DD4BF;color:#042f2e;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:bold">Reset password</a></p>
      <p style="color:#64748b;font-size:13px">This link expires in 24 hours. If you didn't request this, you can safely ignore it.</p>
    </div>"""
    text = f"Reset your LearnX password by opening: {reset_url} (valid 24h)."
    return _send(to, "Reset your LearnX password", html, text)


def send_welcome_email(to: str, full_name: str) -> str | None:
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2 style="color:#0f172a">You're in, {full_name} 🎉</h2>
      <p style="color:#334155;font-size:15px">Your LearnX account is verified. Less stress, more success.</p>
    </div>"""
    text = f"You're in, {full_name}! Your LearnX account is verified."
    return _send(to, "Your LearnX account is verified", html, text)
