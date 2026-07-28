"""
Object storage service — S3-compatible (AWS S3, MinIO, Cloudflare R2, etc).

Security notes (see product spec § Security):
  - Every object key is namespaced per user so a leaked key from one
    user's session can never be reused to address another user's file.
  - Objects are never made public; every read goes through a short-lived
    signed URL (`settings.signed_url_ttl_seconds`).
  - Uploads are validated (see validation.py) *before* being queued for
    processing, not just before being served back.
"""

from __future__ import annotations

import uuid

from app.core.config import get_settings

settings = get_settings()


def user_scoped_key(user_id: str, category: str, filename: str) -> str:
    """
    Builds a storage key like:
      users/{user_id}/videos/{uuid}-{sanitized filename}

    The UUID prefix prevents filename collisions and makes keys
    non-guessable even for users who know each other's IDs.
    """
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-") or "file"
    return f"users/{user_id}/{category}/{uuid.uuid4()}-{safe_name}"


def get_signed_url(bucket: str, key: str, expires_in: int | None = None) -> str:
    """
    Returns a time-limited signed URL for reading an object.

    TODO(real impl):
        import boto3
        client = boto3.client("s3", endpoint_url=settings.storage_endpoint_url, ...)
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in or settings.signed_url_ttl_seconds,
        )
    """
    raise NotImplementedError("Reference stub — wire in a real S3-compatible client.")


def get_signed_upload_url(bucket: str, key: str, content_type: str) -> str:
    """Returns a signed PUT URL so large video uploads go directly client → storage, not through the API server."""
    raise NotImplementedError("Reference stub — wire in a real S3-compatible client.")
