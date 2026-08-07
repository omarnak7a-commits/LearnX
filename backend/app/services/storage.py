"""
Object storage service — REAL S3-compatible client (Supabase Storage).

Implements the operations the File Vault and Video Intelligence features
need:

  - `upload_file`: server-side PUT of bytes (small files).
  - `get_presigned_upload_url`: client-side direct-to-storage PUT for
    large uploads (video lectures), so bytes never transit the API host.
  - `get_presigned_download_url`: short-lived signed GET URLs — objects
    are never public (product spec § Security).
  - `delete_object`: permanent delete (with user-scoped key safety check).
  - `list_prefix`: list objects under a user-scoped prefix.

Every key is namespaced `users/{user_id}/...` so a leaked key can never
address another user's object.
"""

from __future__ import annotations

import logging
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_client = None


def get_client():
    """Lazily-built boto3 S3 client pointed at the configured endpoint."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url or None,
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=Config(signature_version="s3v4"),
        )
    return _client


def user_scoped_key(user_id: str, category: str, filename: str) -> str:
    """
    Builds a storage key like:
      users/{user_id}/{category}/{uuid}-{sanitized filename}

    The UUID prefix prevents filename collisions and makes keys
    non-guessable even for users who know each other's IDs.
    """
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-") or "file"
    return f"users/{user_id}/{category}/{uuid.uuid4()}-{safe_name}"


def _bucket() -> str:
    return settings.storage_bucket


class StorageError(Exception):
    pass


def upload_file(
    user_id: str,
    category: str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Uploads raw bytes server-side and returns the object key."""
    key = user_scoped_key(user_id, category, filename)
    try:
        get_client().put_object(
            Bucket=_bucket(),
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except ClientError as exc:
        logger.exception("storage upload failed for key=%s", key)
        raise StorageError(f"Upload failed: {exc}") from exc
    return key


def get_presigned_upload_url(
    user_id: str,
    category: str,
    filename: str,
    content_type: str,
    expires_in: int | None = None,
) -> tuple[str, str]:
    """
    Returns (presigned PUT url, object key) so the client can stream the
    file directly to Supabase Storage without proxying through the API.
    """
    key = user_scoped_key(user_id, category, filename)
    url = get_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in or settings.signed_url_ttl_seconds,
    )
    return url, key


def get_presigned_download_url(key: str, expires_in: int | None = None) -> str:
    """Short-lived signed GET URL — objects are never publicly readable."""
    url = get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_in or settings.signed_url_ttl_seconds,
    )
    return url


def delete_object(user_id: str, key: str) -> None:
    """Deletes an object, refusing keys that are not scoped to `user_id`."""
    expected_prefix = f"users/{user_id}/"
    if not key.startswith(expected_prefix):
        raise StorageError("Refusing to delete an object outside the caller's namespace.")
    try:
        get_client().delete_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        logger.exception("storage delete failed for key=%s", key)
        raise StorageError(f"Delete failed: {exc}") from exc


def list_prefix(user_id: str, category: str | None = None) -> list[str]:
    """Lists object keys under `users/{user_id}/{category?}`."""
    prefix = f"users/{user_id}/" + (f"{category}/" if category else "")
    try:
        resp = get_client().list_objects_v2(Bucket=_bucket(), Prefix=prefix)
        return [obj["Key"] for obj in resp.get("Contents", [])]
    except ClientError as exc:
        logger.exception("storage list failed for prefix=%s", prefix)
        raise StorageError(f"List failed: {exc}") from exc
