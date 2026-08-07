"""File Vault API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class FileOut(BaseModel):
    id: str
    name: str
    sizeBytes: int = 0
    mimeType: str = "application/octet-stream"
    course: str | None = None
    doctorName: str | None = None
    favorite: bool = False
    pinned: bool = False
    collections: list[str] = []
    examDate: str | None = None
    readingProgressPct: int = 0
    learningStatus: str = "not-started"
    lastPage: int = 1
    totalPages: int = 0
    createdAt: str = ""
    updatedAt: str = ""
    downloadUrl: str | None = None
    analysis: dict | None = None


class FileUploadInitOut(BaseModel):
    fileId: str
    uploadUrl: str
    storageKey: str


class FileUpdateIn(BaseModel):
    favorite: bool | None = None
    pinned: bool | None = None
    collections: list[str] | None = None
    examDate: str | None = None
    readingProgressPct: int | None = None
    learningStatus: str | None = None
    lastPage: int | None = None
    totalPages: int | None = None
    analysis: dict | None = None
    metadata: dict | None = None
    course: str | None = None
    doctorName: str | None = None


class NoteOut(BaseModel):
    id: str
    fileId: str
    page: int
    content: str
    color: str = "#f59e0b"
    createdAt: str = ""


class NoteIn(BaseModel):
    fileId: str
    page: int = 1
    content: str
    color: str = "#f59e0b"


class BookmarkOut(BaseModel):
    id: str
    fileId: str
    page: int
    label: str
    createdAt: str = ""


class BookmarkIn(BaseModel):
    fileId: str
    page: int
    label: str = ""
