"""Tests A/B/C: a 32-page PDF must be analysed in full for a document-scoped exam.

The reported failure was:

    "... LearnX could only verify 1. (only page(s) 2, 3, 4, 5, 6, 7, 8, 9... of
    32 were used)"

Two independent defects can produce that shape, and both are covered here:

1. The request being narrowed to ``pagesRead`` (pages 2-9 of 32).
2. Extraction silently dropping later pages once the character budget ran out.
   The old loop filled pages front-to-back and ``break``-ed, so a dense
   32-page PDF reached the pipeline as its first ~22 pages.

Everything runs through the real HTTP endpoint with the payload the frontend
sends, because the previous bug survived exactly by being tested one layer too
low.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services import storage as storage_service
from app.services.ai_documents import (
    _extract_pdf_uncached,
    clear_extraction_cache,
)
from app.services.ai_service import AIServiceError
from app.services.quiz_pipeline import build_quiz_context

OWNER_ID = "11111111-1111-1111-1111-111111111111"
FILE_ID = "33333333-3333-3333-3333-333333333333"

FIXTURE = Path(__file__).parent / "fixtures" / "textbook_32_pages.pdf"

#: The pages the student happened to open, exactly as in the bug report.
PAGES_READ = [2, 3, 4, 5, 6, 7, 8, 9]


class NoProvider:
    """Both providers down: the deterministic path must still fill the exam."""

    def complete_structured(self, **_kwargs):
        raise AIServiceError("no provider configured")


def pdf_bytes() -> bytes:
    return FIXTURE.read_bytes()


class FakeSession:
    def __init__(self, file_obj):
        self._file = file_obj

    def get(self, _model, file_id):
        if self._file is None or str(self._file.id) != str(file_id):
            return None
        return self._file

    def scalar(self, _stmt):
        return self._file


def _db_gen(db):
    def _get_db():
        yield db

    return _get_db


@pytest.fixture
def client(monkeypatch):
    clear_extraction_cache()
    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = _db_gen(
        FakeSession(
            SimpleNamespace(
                id=FILE_ID,
                owner_id=OWNER_ID,
                name="cell-biology-32.pdf",
                size_bytes=len(pdf_bytes()),
                mime_type="application/pdf",
                storage_key=f"users/{OWNER_ID}/vault/cell-biology-32.pdf",
                analysis=None,
            )
        )
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)
    monkeypatch.setattr(
        storage_service, "download_user_object", lambda *a, **k: pdf_bytes()
    )

    import app.api.ai as ai_api

    app.dependency_overrides[ai_api.get_ai_service] = lambda: NoProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def ask(client, **payload):
    body = {"fileId": FILE_ID, "count": 8}
    body.update(payload)
    return client.post("/api/v1/ai/quiz", json=body)


def pages_in(text: str) -> list[int]:
    return [int(value) for value in re.findall(r"\[Page (\d+)\]", text)]


# --------------------------------------------------------------------------- #
# Test A: scope="document" must use the whole 32-page PDF
# --------------------------------------------------------------------------- #


def test_a_document_scope_is_not_reduced_to_pages_read(client) -> None:
    """The exact reported payload: pages 2-9 read, exam over the whole PDF."""
    response = ask(
        client, count=8, kind="exam", scope="document", allowedPages=PAGES_READ
    )
    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 8

    cited = {page for question in questions for page in question["sourcePages"]}
    # The whole document was available, so the quiz is not confined to 2-9.
    assert not cited <= set(PAGES_READ), (
        f"document-scoped exam was still limited to pagesRead: {sorted(cited)}"
    )


def test_a_pages_outside_pages_read_are_available_as_evidence(client) -> None:
    response = ask(
        client, count=8, kind="exam", scope="document", allowedPages=PAGES_READ
    )
    assert response.status_code == 200, response.text
    cited = {
        page
        for question in response.json()["questions"]
        for page in question["sourcePages"]
    }
    assert any(page > max(PAGES_READ) for page in cited), sorted(cited)


def test_a_the_pipeline_receives_all_thirty_two_pages(client) -> None:
    """Prove it at the source, not just by inspecting citations."""
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        allowedPages=PAGES_READ,
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["extracted_pages"] == 32
    assert diagnostics["pages_used"] == 32
    assert diagnostics["accepted"] == 8


def test_a_the_error_message_can_never_blame_pages_read_in_document_scope(
    client,
) -> None:
    response = ask(
        client, count=8, kind="exam", scope="document", allowedPages=PAGES_READ
    )
    assert response.status_code == 200, response.text
    assert "only page(s)" not in response.text


# --------------------------------------------------------------------------- #
# Test B: scope="pages-read" must use only those pages
# --------------------------------------------------------------------------- #


def test_b_pages_read_scope_uses_only_the_pages_read(client) -> None:
    response = ask(
        client, count=8, kind="practice", scope="pages-read", allowedPages=PAGES_READ
    )
    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 8
    for question in questions:
        for page in question["sourcePages"]:
            assert page in PAGES_READ, f"leaked page {page}"


def test_b_no_evidence_from_other_pages_can_appear(client) -> None:
    """Check the extracted source itself, not only the citations."""
    clear_extraction_cache()
    restricted = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-32",
        max_characters=100_000,
        allowed_pages=PAGES_READ,
    )
    assert pages_in(restricted.text) == PAGES_READ
    context = build_quiz_context(restricted)
    assert sorted(context.included_pages) == PAGES_READ


def test_b_the_two_scopes_produce_different_quizzes(client) -> None:
    document = ask(
        client, count=8, kind="exam", scope="document", allowedPages=PAGES_READ
    )
    restricted = ask(
        client, count=8, kind="practice", scope="pages-read", allowedPages=PAGES_READ
    )
    assert document.status_code == 200
    assert restricted.status_code == 200

    doc_pages = {
        p for q in document.json()["questions"] for p in q["sourcePages"]
    }
    read_pages = {
        p for q in restricted.json()["questions"] for p in q["sourcePages"]
    }
    assert read_pages <= set(PAGES_READ)
    assert not doc_pages <= set(PAGES_READ)


# --------------------------------------------------------------------------- #
# Test C: 8 grounded questions from the full PDF
# --------------------------------------------------------------------------- #


def test_c_eight_question_exam_from_the_full_pdf(client) -> None:
    response = ask(client, count=8, kind="exam", scope="document")
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == 8


def test_c_every_question_is_grounded_in_the_pdf(client) -> None:
    response = ask(client, count=8, kind="exam", scope="document")
    assert response.status_code == 200, response.text

    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-32",
        max_characters=100_000,
        allowed_pages=None,
    )
    valid_pages = set(pages_in(source.text))
    for question in response.json()["questions"]:
        assert question["prompt"].strip()
        assert question["correctAnswer"].strip()
        assert question["sourcePages"]
        for page in question["sourcePages"]:
            assert page in valid_pages


def test_c_questions_are_spread_across_the_document(client) -> None:
    response = ask(client, count=8, kind="exam", scope="document")
    assert response.status_code == 200
    cited = {
        page
        for question in response.json()["questions"]
        for page in question["sourcePages"]
    }
    assert len(cited) >= 5, sorted(cited)


@pytest.mark.parametrize("count", [5, 8, 12])
def test_c_the_requested_count_is_met(client, count: int) -> None:
    response = ask(client, count=count, kind="exam", scope="document")
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == count


# --------------------------------------------------------------------------- #
# Extraction must not silently drop the back half of a long PDF
# --------------------------------------------------------------------------- #


def test_extraction_covers_every_page_within_the_character_budget() -> None:
    """Regression: a dense PDF used to arrive as its first ~22 pages.

    The old loop appended whole pages until the budget ran out and then broke,
    so later chapters never reached the pipeline at all.
    """
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-32",
        max_characters=100_000,
        allowed_pages=None,
    )
    assert pages_in(source.text) == list(range(1, 33))
    assert len(source.text) <= 100_000


def test_a_tight_budget_still_samples_the_whole_document() -> None:
    """Even a budget far too small must keep breadth rather than truncating."""
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-32",
        max_characters=20_000,
        allowed_pages=None,
    )
    covered = pages_in(source.text)
    assert len(source.text) <= 20_000
    # Breadth is what a quiz needs; the last page must still be represented.
    assert covered[0] == 1
    assert covered[-1] == 32
    assert len(covered) >= 25


def test_trimming_never_leaves_a_half_sentence() -> None:
    from app.services.ai_documents import _trim_at_boundary

    text = "First sentence here. Second sentence follows. Third one trails off"
    trimmed = _trim_at_boundary(text, 46)
    assert trimmed.endswith(".")
    assert "Third one trails off" not in trimmed


def test_a_page_restriction_still_wins_over_the_budget() -> None:
    """Trimming must not resurrect pages the caller excluded."""
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-32",
        max_characters=20_000,
        allowed_pages=PAGES_READ,
    )
    assert pages_in(source.text) == PAGES_READ


# --------------------------------------------------------------------------- #
# The Exam tab's real payload, and the message it can produce
# --------------------------------------------------------------------------- #

#: Exactly what src/context/FileVaultContext.tsx generateExam() sends today.
EXAM_PAYLOAD_KEYS = {"fileId", "count", "questionTypes", "kind", "scope"}


def test_the_exam_tab_payload_carries_document_scope_and_no_page_list() -> None:
    """Guard the built request shape, not just the backend behaviour.

    The screenshot that reopened this bug came from a deployed bundle built
    before scope existed. Asserting on the compiled source keeps a future edit
    from quietly reintroducing `allowedPages` into the exam call.
    """
    context = (
        Path(__file__).resolve().parents[2] / "src" / "context" / "FileVaultContext.tsx"
    ).read_text(encoding="utf-8")
    exam = context.split("const generateExam")[1].split("const recordAttempt")[0]
    assert "scope: 'document'" in exam
    assert "allowedPages" not in exam, "the exam must never send a page restriction"


def test_full_document_exam_never_says_only_pages_were_used(client) -> None:
    """Acceptance criterion from the bug report."""
    response = ask(
        client,
        count=8,
        kind="exam",
        questionTypes=["mcq", "true-false", "fill-blank", "short-answer"],
        scope="document",
    )
    assert response.status_code == 200, response.text
    assert "only page(s)" not in response.text


def test_a_stale_client_sending_pages_without_scope_still_gets_the_whole_pdf(
    client,
) -> None:
    """A browser running an old bundle must not be silently restricted.

    The pre-fix bundle sent allowedPages and no scope at all. Because scope
    defaults to 'document', that payload must now be served from the whole
    document.
    """
    response = ask(
        client,
        count=8,
        kind="exam",
        allowedPages=list(range(1, 33)),
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["pages_used"] == 32
    assert diagnostics["accepted"] == 8


def test_a_stale_practice_payload_is_also_unrestricted(client) -> None:
    response = ask(
        client,
        count=8,
        kind="practice",
        allowedPages=list(range(2, 33)),
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    assert response.json()["diagnostics"]["pages_used"] == 32


def test_the_scope_note_distinguishes_a_restriction_from_unreadable_pages() -> None:
    """The screenshot's wording implied a page filter that was never applied.

    A document-scoped request whose page 1 is a scanned cover used to report
    "only page(s) 2, 3, 4 ... of 32 were used" -- indistinguishable from an
    actual pagesRead restriction.
    """
    from app.services.ai_documents import AIDocumentSource
    from app.services.quiz_pipeline import QuizContext, _scope_note

    context = QuizContext(
        units=[],
        sentences=[],
        vocab=set(),
        page_text={},
        included_pages=set(range(2, 33)),
    )
    source = AIDocumentSource(file_id="f", title="SQL18", text="x", page_count=32)

    unrestricted = _scope_note(source, context)
    assert "only page(s)" not in unrestricted
    assert "whole 32-page document was analysed" in unrestricted
    assert "no extractable text" in unrestricted

    restricted = _scope_note(source, context, requested_pages=list(range(2, 33)))
    assert "only page(s) 2, 3, 4" in restricted


def test_diagnostics_expose_the_full_funnel_for_the_exam_flow(client) -> None:
    response = ask(
        client,
        count=8,
        kind="exam",
        questionTypes=["mcq", "true-false", "fill-blank", "short-answer"],
        scope="document",
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["extracted_pages"] == 32
    assert diagnostics["pages_used"] == 32
    assert diagnostics["concepts"] > 0
    assert diagnostics["evidence_items"] > 0
    assert diagnostics["plans"] >= 8
    assert diagnostics["accepted"] == 8
