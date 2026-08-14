"""File Vault API — real upload/download via Supabase Storage S3.

Flow for a new file:
  1. POST /file-vault/upload-init  → creates VaultFile row, returns
     {fileId, uploadUrl (presigned PUT), storageKey}
  2. Client PUTs bytes directly to uploadUrl (never through the API).
  3. POST /file-vault/{file_id}/complete → marks the file ready.

Reading bytes into the in-browser PDF Viewer:
  GET /file-vault/{file_id}/content
  Returns a streamed `application/pdf` response, ownership-checked and
  JWT-authenticated. The PDF Viewer and the AI text-extraction layer both
  hit this same endpoint — the viewer streams the bytes; the AI server-
  side load path reuses `app.services.ai_documents.load_owned_pdf`.
  The download endpoint below returns a short-lived presigned GET URL for
  consumers that prefer a single signed redirect (objects are never public).
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.core.db import get_db
from app.models.file_vault import FileBookmark, StudentNote, VaultFile
from app.models.profile import User
from app.schemas.file_vault import (
    BookmarkIn,
    BookmarkOut,
    FileOut,
    FileUpdateIn,
    FileUploadInitOut,
    NoteIn,
    NoteOut,
)
from app.services import storage

router = APIRouter(prefix="/file-vault", tags=["file-vault"])

# 64 MiB hard ceiling for the in-browser PDF Viewer endpoint. The AI text
# layer uses a much lower `ai_max_document_bytes` (15 MiB) and a separate
# auth-checked codepath; the viewer just needs the raw PDF bytes.
VIEWER_MAX_PDF_BYTES = 64 * 1024 * 1024

# 1 MiB streaming chunks — Vercel Python serverless can flush a chunk of
# this size comfortably without timing out the lambda response.
VIEWER_CHUNK_BYTES = 1024 * 1024

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    cleaned = _FILENAME_SAFE.sub("_", name or "file.pdf").strip("._")
    return cleaned or "file.pdf"


def _file_out(db: Session, f: VaultFile, include_url: bool = True) -> FileOut:
    download_url = None
    if include_url and f.storage_key:
        try:
            download_url = storage.get_presigned_download_url(f.storage_key)
        except storage.StorageError:
            download_url = None
    return FileOut(
        id=str(f.id),
        name=f.name,
        sizeBytes=f.size_bytes,
        mimeType=f.mime_type,
        course=f.course,
        doctorName=f.doctor_name,
        favorite=f.favorite,
        pinned=f.pinned,
        collections=f.collections or [],
        examDate=f.exam_date,
        readingProgressPct=f.reading_progress_pct,
        learningStatus=f.learning_status,
        lastPage=f.last_page,
        totalPages=f.total_pages,
        createdAt=f.created_at.isoformat() if f.created_at else "",
        updatedAt=f.updated_at.isoformat() if f.updated_at else "",
        downloadUrl=download_url,
        analysis=f.analysis,
    )


@router.get("", response_model=list[FileOut])
def list_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FileOut]:
    files = list(
        db.scalars(
            select(VaultFile).where(VaultFile.owner_id == user.id).order_by(VaultFile.updated_at.desc())
        ).all()
    )
    return [_file_out(db, f) for f in files]


@router.post("/upload-init", response_model=FileUploadInitOut)
def upload_init(
    filename: str,
    content_type: str = "application/octet-stream",
    size_bytes: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileUploadInitOut:
    upload_url, key = storage.get_presigned_upload_url(
        str(user.id), "vault", filename, content_type
    )
    file = VaultFile(
        owner_id=user.id,
        name=filename,
        size_bytes=size_bytes,
        mime_type=content_type,
        storage_key=key,
    )
    db.add(file)
    db.commit()
    db.refresh(file)
    return FileUploadInitOut(fileId=str(file.id), uploadUrl=upload_url, storageKey=key)


@router.post("/{file_id}/complete", response_model=FileOut)
def complete_upload(
    file_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileOut:
    file = db.get(VaultFile, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    require_owner(str(file.owner_id), str(user.id))
    return _file_out(db, file)


@router.patch("/{file_id}", response_model=FileOut)
def update_file(
    file_id: str,
    payload: FileUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileOut:
    file = db.get(VaultFile, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    require_owner(str(file.owner_id), str(user.id))

    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "favorite": "favorite",
        "pinned": "pinned",
        "collections": "collections",
        "examDate": "exam_date",
        "readingProgressPct": "reading_progress_pct",
        "learningStatus": "learning_status",
        "lastPage": "last_page",
        "totalPages": "total_pages",
        "analysis": "analysis",
        "metadata": "metadata_payload",
        "course": "course",
        "doctorName": "doctor_name",
    }
    for camel, snake in mapping.items():
        if camel in data:
            setattr(file, snake, data[camel])
    db.commit()
    db.refresh(file)
    return _file_out(db, file)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_file(
    file_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    file = db.get(VaultFile, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    require_owner(str(file.owner_id), str(user.id))
    try:
        storage.delete_object(str(user.id), file.storage_key)
    except storage.StorageError:
        pass  # object may already be gone — still delete the row
    db.delete(file)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    file = db.get(VaultFile, file_id)
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    require_owner(str(file.owner_id), str(user.id))
    url = storage.get_presigned_download_url(file.storage_key)
    return {"downloadUrl": url, "name": file.name}


# Cache headers on a per-user per-file basis. The body never changes
# (immutable once uploaded), but the metadata is keyed by user because
# we want to disable intermediary caching across tenants.
@router.get("/{file_id}/content")
def download_owned_pdf_bytes(
    file_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the raw PDF bytes for a file owned by the caller.

    This is the canonical "I want to render this PDF" endpoint: the
    in-browser PDF Viewer and any authenticated PDF download tool MUST
    use this route instead of asking the client to talk to Supabase
    directly. Every byte that crosses the wire is:

      * owned by the calling user (404 for missing/foreign IDs);
      * sent only after a valid JWT (401 otherwise);
      * streamed from private storage with `Content-Type: application/pdf`;
      * capped at 64 MiB to keep the serverless response bounded.

    The endpoint supports HTTP Range requests so the browser/PDF.js can
    resume interrupted downloads and avoid re-fetching the whole file.
    """
    file = db.get(VaultFile, file_id)
    if file is None or str(file.owner_id) != str(user.id):
        # 404 for both missing and foreign-owned IDs prevents enumeration.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    if not file.storage_key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This file is not available in private storage yet.",
        )
    if file.mime_type and file.mime_type != "application/pdf" and not file.name.lower().endswith(".pdf"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PDF files can be streamed from the File Vault.",
        )

    range_header = request.headers.get("range") or request.headers.get("Range")
    range_start: int | None = None
    range_end: int | None = None
    if range_header:
        match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
        if match:
            raw_start, raw_end = match.group(1), match.group(2)
            try:
                if raw_start == "" and raw_end != "":
                    # Suffix range: last N bytes
                    suffix = int(raw_end)
                    if suffix > 0:
                        # Resolved after we know content_length
                        range_start = -1  # sentinel
                        range_end = suffix
                else:
                    if raw_start != "":
                        range_start = max(0, int(raw_start))
                    if raw_end != "":
                        range_end = max(0, int(raw_end))
            except ValueError:
                range_start = None
                range_end = None

    # Probe the object's full size before deciding whether to apply the
    # Range; this also gives us a clear 404 path if the storage layer
    # rejects the key (e.g. it does not start with `users/{user_id}/`).
    try:
        content_length, _probe_status, _probe_iter = storage.stream_user_object(
            str(user.id),
            file.storage_key,
            chunk_bytes=VIEWER_CHUNK_BYTES,
            max_bytes=VIEWER_MAX_PDF_BYTES,
        )
    except storage.StorageError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            str(exc) or "Storage backend is unavailable for this file.",
        ) from exc

    if range_start is not None and range_end is not None and range_start == -1:
        # Suffix range: resolve against the real length.
        suffix = range_end
        range_start = max(0, content_length - suffix)
        range_end = content_length - 1

    if range_start is not None and range_end is not None:
        range_start = min(range_start, max(0, content_length - 1))
        range_end = min(range_end, content_length - 1)
        if range_end < range_start:
            range_start = None
            range_end = None

    if range_start is not None and range_end is not None:
        try:
            _len, _sc, body_iter = storage.stream_user_object(
                str(user.id),
                file.storage_key,
                chunk_bytes=VIEWER_CHUNK_BYTES,
                max_bytes=VIEWER_MAX_PDF_BYTES,
                range_start=range_start,
                range_end=range_end,
            )
            response_status = 206
        except storage.StorageError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                str(exc) or "Storage backend is unavailable for this file.",
            ) from exc
    else:
        try:
            _len, _sc, body_iter = storage.stream_user_object(
                str(user.id),
                file.storage_key,
                chunk_bytes=VIEWER_CHUNK_BYTES,
                max_bytes=VIEWER_MAX_PDF_BYTES,
            )
            response_status = 200
        except storage.StorageError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                str(exc) or "Storage backend is unavailable for this file.",
            ) from exc

    headers: dict[str, str] = {
        "Content-Type": "application/pdf",
        "Content-Disposition": f'inline; filename="{_safe_filename(file.name)}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0, must-revalidate",
        "X-Content-Type-Options": "nosniff",
    }
    if response_status == 206 and range_start is not None and range_end is not None:
        headers["Content-Range"] = f"bytes {range_start}-{range_end}/{content_length}"
        headers["Content-Length"] = str(range_end - range_start + 1)
    else:
        headers["Content-Length"] = str(content_length)

    return StreamingResponse(
        body_iter,
        status_code=response_status,
        headers=headers,
        media_type="application/pdf",
    )


# ── Notes ────────────────────────────────────────────────────────────

@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NoteOut]:
    notes = list(
        db.scalars(
            select(StudentNote)
            .join(VaultFile, VaultFile.id == StudentNote.file_id)
            .where(VaultFile.owner_id == user.id)
            .order_by(StudentNote.created_at.desc())
        ).all()
    )
    return [
        NoteOut(
            id=str(n.id), fileId=str(n.file_id), page=n.page,
            content=n.content, color=n.color,
            createdAt=n.created_at.isoformat() if n.created_at else "",
        )
        for n in notes
    ]


@router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    file = db.get(VaultFile, payload.fileId)
    if file is None or file.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    note = StudentNote(
        file_id=payload.fileId, owner_id=user.id,
        page=payload.page, content=payload.content, color=payload.color,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut(
        id=str(note.id), fileId=str(note.file_id), page=note.page,
        content=note.content, color=note.color,
        createdAt=note.created_at.isoformat() if note.created_at else "",
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_note(
    note_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    note = db.get(StudentNote, note_id)
    if note is None or note.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found.")
    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Bookmarks ────────────────────────────────────────────────────────

@router.get("/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BookmarkOut]:
    marks = list(
        db.scalars(
            select(FileBookmark)
            .join(VaultFile, VaultFile.id == FileBookmark.file_id)
            .where(VaultFile.owner_id == user.id)
            .order_by(FileBookmark.created_at.desc())
        ).all()
    )
    return [
        BookmarkOut(
            id=str(b.id), fileId=str(b.file_id), page=b.page, label=b.label,
            createdAt=b.created_at.isoformat() if b.created_at else "",
        )
        for b in marks
    ]


@router.post("/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    payload: BookmarkIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookmarkOut:
    file = db.get(VaultFile, payload.fileId)
    if file is None or file.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    mark = FileBookmark(file_id=payload.fileId, owner_id=user.id, page=payload.page, label=payload.label)
    db.add(mark)
    db.commit()
    db.refresh(mark)
    return BookmarkOut(
        id=str(mark.id), fileId=str(mark.file_id), page=mark.page, label=mark.label,
        createdAt=mark.created_at.isoformat() if mark.created_at else "",
    )


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_bookmark(
    bookmark_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    mark = db.get(FileBookmark, bookmark_id)
    if mark is None or mark.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bookmark not found.")
    db.delete(mark)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
