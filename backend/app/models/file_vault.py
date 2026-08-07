"""File Vault models — files, notes, bookmarks, collections.

The actual bytes of a file live in Supabase Storage (S3-compatible) under
a user-scoped key (`users/{user_id}/vault/{uuid}-{name}`); these tables
hold the metadata, the student's notes/bookmarks and reading progress.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class VaultFile(Base):
    __tablename__ = "vault_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(512), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    storage_key: Mapped[str] = mapped_column(String(1024), default="")
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    collections: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    exam_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reading_progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    learning_status: Mapped[str] = mapped_column(String(32), default="not-started")
    last_page: Mapped[int] = mapped_column(Integer, default=1)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)

    # Client-side analysis is persisted here as JSON blobs so a student
    # switching devices keeps their summaries/flashcards/mind maps.
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class StudentNote(Base):
    __tablename__ = "student_notes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("vault_files.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(16), default="#f59e0b")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FileBookmark(Base):
    __tablename__ = "file_bookmarks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("vault_files.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
