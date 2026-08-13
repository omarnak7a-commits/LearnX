"""Secure loading and text extraction for user-owned File Vault PDFs."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.file_vault import VaultFile
from app.services import storage


class AIDocumentError(RuntimeError):
    pass


class AIDocumentNotFoundError(AIDocumentError):
    pass


class AIDocumentUnsupportedError(AIDocumentError):
    pass


@dataclass(frozen=True)
class AIDocumentSource:
    file_id: str | None
    title: str
    text: str
    page_count: int

    def prompt_block(self) -> str:
        return (
            f"<source title={self.title!r} pages={self.page_count}>\n"
            f"{self.text}\n"
            "</source>"
        )


def source_from_text(text: str, title: str | None = None) -> AIDocumentSource:
    clean = _clean_text(text)
    if not clean:
        raise AIDocumentUnsupportedError("The supplied text has no readable content.")
    return AIDocumentSource(
        file_id=None,
        title=(title or "Provided study material")[:512],
        text=f"[Page 1]\n{clean}",
        page_count=1,
    )


def load_owned_pdf(
    *,
    db: Session,
    user_id: str,
    file_id: str,
    settings: Settings,
    allowed_pages: list[int] | None = None,
) -> tuple[VaultFile, AIDocumentSource]:
    """Load a VaultFile only when both row ownership and key scope match."""
    try:
        normalized_file_id = str(uuid.UUID(str(file_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AIDocumentNotFoundError("File not found.") from exc

    file = db.scalar(
        select(VaultFile).where(
            VaultFile.id == normalized_file_id,
            VaultFile.owner_id == str(user_id),
        )
    )
    if file is None:
        # A 404 for both missing and foreign-owned IDs prevents enumeration.
        raise AIDocumentNotFoundError("File not found.")
    if not file.storage_key:
        raise AIDocumentUnsupportedError("This file is not available in private storage.")
    if file.mime_type != "application/pdf" and not file.name.lower().endswith(".pdf"):
        raise AIDocumentUnsupportedError("Only PDF files can be analyzed from the File Vault.")

    try:
        pdf_bytes = storage.download_user_object(
            str(user_id),
            file.storage_key,
            settings.ai_max_document_bytes,
        )
    except storage.StorageError as exc:
        raise AIDocumentUnsupportedError(str(exc)) from exc

    source = _extract_pdf(
        pdf_bytes,
        file_id=str(file.id),
        title=file.name,
        max_characters=settings.ai_max_document_characters,
        allowed_pages=allowed_pages,
    )
    return file, source


def _extract_pdf(
    data: bytes,
    *,
    file_id: str,
    title: str,
    max_characters: int,
    allowed_pages: list[int] | None,
) -> AIDocumentSource:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise AIDocumentUnsupportedError("Password-protected PDFs cannot be analyzed.")
    except AIDocumentUnsupportedError:
        raise
    except (PdfReadError, ValueError, OSError) as exc:
        raise AIDocumentUnsupportedError("The stored file is not a readable PDF.") from exc

    page_count = len(reader.pages)
    if page_count == 0:
        raise AIDocumentUnsupportedError("The PDF has no pages.")

    if allowed_pages is None:
        selected_pages = list(range(1, page_count + 1))
    else:
        selected_pages = sorted(set(allowed_pages))
        if not selected_pages or selected_pages[0] < 1 or selected_pages[-1] > page_count:
            raise AIDocumentUnsupportedError("One or more selected pages are outside the PDF.")

    chunks: list[str] = []
    used = 0
    for page_number in selected_pages:
        try:
            raw = reader.pages[page_number - 1].extract_text() or ""
        except (PdfReadError, ValueError, KeyError):
            raw = ""
        clean = _clean_text(raw)
        if not clean:
            continue
        header = f"[Page {page_number}]\n"
        remaining = max_characters - used - len(header)
        if remaining <= 0:
            break
        page_text = clean[:remaining]
        chunks.append(f"{header}{page_text}")
        used += len(header) + len(page_text)
        if used >= max_characters:
            break

    if not chunks:
        raise AIDocumentUnsupportedError(
            "No extractable text was found. Scanned PDFs need OCR before AI analysis."
        )

    return AIDocumentSource(
        file_id=file_id,
        title=title[:512],
        text="\n\n".join(chunks),
        page_count=page_count,
    )


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
