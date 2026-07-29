"""
Upload validation — runs before any file is accepted into the pipeline.

Checks (in order, cheapest first, so a malicious/malformed upload is
rejected as early as possible):

  1. Declared size vs. `settings.max_upload_size_bytes`.
  2. Extension is in the supported set (mp4, mov, avi, mkv, webm).
  3. Magic-byte sniffing via `python-magic` — the *actual* file content
     must match a known video container format, not just the extension
     the client claims (prevents disguised-file attacks).
  4. ClamAV scan (`clamd`) of the fully-uploaded file before it is queued
     for processing — matches the product spec's pipeline step "Virus
     Scan" that runs immediately after upload and before anything else.

Only after all four checks pass does `app/api/video.py` create the
`VideoLecture` row and enqueue `app.workers.celery_app.process_lecture`.
"""

from __future__ import annotations

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUPPORTED_MIME_PREFIXES = ("video/",)


class UploadValidationError(Exception):
    pass


def validate_declared_size(size_bytes: int, max_bytes: int) -> None:
    if size_bytes > max_bytes:
        raise UploadValidationError(f"File exceeds max upload size of {max_bytes} bytes.")


def validate_extension(filename: str) -> None:
    if not any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise UploadValidationError(f"Unsupported file extension for '{filename}'.")


def validate_magic_bytes(file_path: str) -> None:
    """
    TODO(real impl):
        import magic
        mime = magic.from_file(file_path, mime=True)
        if not mime.startswith(SUPPORTED_MIME_PREFIXES):
            raise UploadValidationError(f"File content does not match a supported video type (detected {mime}).")
    """
    raise NotImplementedError("Reference stub — wire in python-magic. See module docstring.")


def scan_for_viruses(file_path: str) -> None:
    """
    TODO(real impl):
        import clamd
        cd = clamd.ClamdUnixSocket()
        result = cd.scan(file_path)
        status = result[file_path][0]
        if status != "OK":
            raise UploadValidationError(f"File failed virus scan: {result[file_path]}")
    """
    raise NotImplementedError("Reference stub — wire in a ClamAV daemon. See module docstring.")
