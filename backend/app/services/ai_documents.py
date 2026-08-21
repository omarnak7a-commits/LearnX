"""Secure loading and text extraction for user-owned File Vault PDFs."""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, replace
from io import BytesIO
from typing import Any

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
class PageExtraction:
    """What extraction actually recovered from one PDF page.

    A page can fail to contribute for two very different reasons: it holds no
    text at all (a scanned image, a full-page diagram), or its text was
    recovered but later discarded. Recording the raw per-page result lets a
    diagnostic distinguish the two instead of guessing.
    """

    page: int
    text_length: int
    #: True when the page carries drawable content (an image XObject) even
    #: though little or no text could be extracted -- i.e. a candidate for
    #: multimodal inspection rather than a genuinely blank page.
    image_available: bool = False

    @property
    def text_available(self) -> bool:
        return self.text_length > 0


@dataclass
class AIDocumentSource:
    file_id: str | None
    title: str
    text: str
    page_count: int
    #: Per-page extraction quality, in page order. Empty for text sources.
    pages: tuple[PageExtraction, ...] = ()

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


#: Bounded, in-process cache of extracted PDF text.
#:
#: Parsing a PDF is the single most expensive step in a quiz request, and a
#: student generating a practice quiz, then an exam, then a retry over the same
#: pages would otherwise pay it every time. The key covers everything that can
#: change the extracted text, so a different page selection is a different
#: entry rather than a stale hit.
_EXTRACT_CACHE_SIZE = 8
_extract_cache: "OrderedDict[tuple[str, str, int, tuple[int, ...] | None], AIDocumentSource]" = (
    OrderedDict()
)
_extract_cache_lock = threading.Lock()


def _extract_cache_key(
    data: bytes, *, title: str, max_characters: int, allowed_pages: list[int] | None
) -> tuple[str, str, int, tuple[int, ...] | None]:
    """Identify an extraction by content, not by file id.

    Hashing the bytes means a re-uploaded or renamed file still hits, and --
    more importantly -- that a changed file never does.
    """
    digest = hashlib.blake2b(data, digest_size=16).hexdigest()
    pages = tuple(sorted(set(allowed_pages))) if allowed_pages is not None else None
    return (digest, title[:512], max_characters, pages)


def clear_extraction_cache() -> None:
    """Drop all cached extractions (used by tests)."""
    with _extract_cache_lock:
        _extract_cache.clear()


def _extract_pdf(
    data: bytes,
    *,
    file_id: str,
    title: str,
    max_characters: int,
    allowed_pages: list[int] | None,
) -> AIDocumentSource:
    key = _extract_cache_key(
        data, title=title, max_characters=max_characters, allowed_pages=allowed_pages
    )
    with _extract_cache_lock:
        cached = _extract_cache.get(key)
        if cached is not None:
            _extract_cache.move_to_end(key)
            # file_id is request scoped; the parsed text is not.
            return replace(cached, file_id=file_id)

    source = _extract_pdf_uncached(
        data,
        file_id=file_id,
        title=title,
        max_characters=max_characters,
        allowed_pages=allowed_pages,
    )
    with _extract_cache_lock:
        _extract_cache[key] = source
        _extract_cache.move_to_end(key)
        while len(_extract_cache) > _EXTRACT_CACHE_SIZE:
            _extract_cache.popitem(last=False)
    return source


#: Never trim a page below this: a few words carry no teachable content, and a
#: page that survives only as a fragment is worse than an evenly sampled one.
_MIN_PAGE_CHARACTERS = 400


def _trim_at_boundary(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` characters without splitting a sentence.

    A half sentence is not evidence -- the grounding gates quote source spans
    verbatim, so a truncated clause becomes an unusable (or misleading) quote.
    """
    if len(text) <= limit:
        return text
    window = text[:limit]
    for terminator in (". ", "? ", "! ", "\n"):
        cut = window.rfind(terminator)
        if cut >= limit // 2:
            return window[: cut + 1].strip()
    return window.rstrip()


def _page_has_image(page: Any) -> bool:
    """Whether a page embeds drawable content (an image XObject).

    Used only for diagnostics and for deciding which pages are worth a
    multimodal look. Any pypdf error means "unknown", reported as False rather
    than failing the whole extraction over a malformed resource dictionary.
    """
    try:
        resources = page.get("/Resources")
        if resources is None:
            return False
        xobjects = resources.get_object().get("/XObject")
        if xobjects is None:
            return False
        for ref in xobjects.get_object().values():
            try:
                if ref.get_object().get("/Subtype") == "/Image":
                    return True
            except Exception:  # noqa: BLE001 - a bad entry is not an error
                continue
    except Exception:  # noqa: BLE001 - diagnostics must never break extraction
        return False
    return False


def _extract_pdf_uncached(
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

    # Read every selected page first, then decide how to fit them in the
    # character budget. The previous loop filled pages front-to-back and broke
    # when the budget ran out, so a dense 32-page PDF was silently reduced to
    # its first ~22 pages: the later chapters simply never reached the quiz
    # pipeline, and the resulting "only page(s) 1..22 of 32 were used" looked
    # like a page-scoping bug rather than truncation.
    extracted: list[tuple[int, str]] = []
    page_reports: list[PageExtraction] = []
    for page_number in selected_pages:
        page_obj = reader.pages[page_number - 1]
        try:
            raw = page_obj.extract_text() or ""
        except (PdfReadError, ValueError, KeyError):
            raw = ""
        clean = _clean_text(raw)
        page_reports.append(
            PageExtraction(
                page=page_number,
                text_length=len(clean),
                image_available=_page_has_image(page_obj),
            )
        )
        if clean:
            extracted.append((page_number, clean))

    overhead = sum(len(f"[Page {number}]\n") for number, _ in extracted)
    total_text = sum(len(text) for _, text in extracted)
    budget = max_characters - overhead

    chunks: list[str] = []
    if extracted and total_text > budget > 0:
        # Too much text for one request. Trim every page proportionally instead
        # of dropping whole pages, so the study map still covers the entire
        # document -- breadth across the PDF matters far more to a quiz than
        # complete prose on its opening chapters.
        per_page = max(_MIN_PAGE_CHARACTERS, budget // len(extracted))
        remaining = budget
        for number, text in extracted:
            if remaining <= 0:
                break
            take = min(len(text), per_page, remaining)
            chunks.append(f"[Page {number}]\n{_trim_at_boundary(text, take)}")
            remaining -= take
    else:
        for number, text in extracted:
            chunks.append(f"[Page {number}]\n{text}")

    if not chunks:
        raise AIDocumentUnsupportedError(
            "No extractable text was found. Scanned PDFs need OCR before AI analysis."
        )

    return AIDocumentSource(
        file_id=file_id,
        title=title[:512],
        text="\n\n".join(chunks),
        page_count=page_count,
        pages=tuple(page_reports),
    )


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
