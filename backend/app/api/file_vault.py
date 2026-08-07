"""File Vault API — real upload/download via Supabase Storage S3.

Flow for a new file:
  1. POST /file-vault/upload-init  → creates VaultFile row, returns
     {fileId, uploadUrl (presigned PUT), storageKey}
  2. Client PUTs bytes directly to uploadUrl (never through the API).
  3. POST /file-vault/{file_id}/complete → marks the file ready.

Reading: GET /file-vault/{file_id}/download returns a short-lived
presigned GET URL (objects are never public).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
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


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    note = db.get(StudentNote, note_id)
    if note is None or note.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found.")
    db.delete(note)
    db.commit()


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


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    mark = db.get(FileBookmark, bookmark_id)
    if mark is None or mark.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bookmark not found.")
    db.delete(mark)
    db.commit()
