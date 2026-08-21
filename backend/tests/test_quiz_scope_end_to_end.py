"""End-to-end reproduction of the "could only verify 1" production bug.

The failure the user reported: upload a real multi-page PDF, ask for 8
questions, get "This PDF does not contain enough clearly explained material".

Every earlier test drove ``generate_quiz`` directly with a whole-document
source, which is why they all passed while production still failed. These
tests go through the actual HTTP endpoint with the payload the frontend
really sends, against a real generated PDF, so the page-scoping decision that
caused the bug is inside the code under test.

Root cause: the practice quiz sent ``allowedPages = pagesRead``. Reading
progress now marks a page read the moment it becomes active, so a student who
had opened only the title page sent ``[1]`` -- the pipeline then examined one
page of a twenty-page textbook, extracted zero concepts, and blamed the
document.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services import storage as storage_service
from app.services.ai_documents import _extract_pdf, clear_extraction_cache
from app.services.ai_service import AIServiceError
from app.services.quiz_pipeline import (
    build_document_understanding,
    build_quiz_context,
    generate_quiz,
)

OWNER_ID = "11111111-1111-1111-1111-111111111111"
FILE_ID = "33333333-3333-3333-3333-333333333333"

FIXTURE = Path(__file__).parent / "fixtures" / "textbook_20_pages.pdf"


class NoProvider:
    """Both AI providers unavailable -- the deterministic path must still work."""

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


def _owned_file() -> SimpleNamespace:
    return SimpleNamespace(
        id=FILE_ID,
        owner_id=OWNER_ID,
        name="cell-biology-textbook.pdf",
        size_bytes=len(pdf_bytes()),
        mime_type="application/pdf",
        storage_key=f"users/{OWNER_ID}/vault/textbook.pdf",
        analysis=None,
    )


@pytest.fixture
def client(monkeypatch):
    clear_extraction_cache()
    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = _db_gen(FakeSession(_owned_file()))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)

    monkeypatch.setattr(
        storage_service, "download_user_object", lambda *a, **k: pdf_bytes()
    )
    # Force the deterministic writer: the bug reproduces with no provider, and
    # this keeps the test hermetic (no network, no keys).
    import app.api.ai as ai_api

    monkeypatch.setattr(ai_api, "get_ai_service", lambda: NoProvider())
    app.dependency_overrides[ai_api.get_ai_service] = lambda: NoProvider()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def ask(client, **payload):
    body = {"fileId": FILE_ID, "count": 8}
    body.update(payload)
    return client.post("/api/v1/ai/quiz", json=body)


# --------------------------------------------------------------------------- #
# The exact reported bug
# --------------------------------------------------------------------------- #


def test_the_reported_bug_eight_requested_from_a_real_pdf(client) -> None:
    """A realistic 20-page PDF must yield 8 questions, not 'only verified 1'."""
    response = ask(client)
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == 8


def test_a_page_restriction_is_ignored_unless_the_caller_asks_for_it(client) -> None:
    """The regression: pagesRead=[1] must NOT silently shrink a full-PDF quiz.

    This is the exact payload the practice quiz used to send. Before the fix
    the request was served from page 1 alone -- a title page -- which produced
    zero concepts and the misleading error.
    """
    response = ask(client, allowedPages=[1])
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == 8


def test_explicit_pages_read_scope_really_does_restrict(client) -> None:
    """The opposite behaviour must remain available and must differ."""
    response = ask(client, scope="pages-read", allowedPages=[1])
    # Page 1 is a title page: honestly unusable, and the error must say so.
    assert response.status_code in (422, 503), response.text
    detail = response.json()["detail"]
    assert "page" in detail.lower()


def test_pages_read_scope_over_real_content_pages_stays_within_them(client) -> None:
    """Restricting to content pages works and cites only those pages."""
    response = ask(
        client, count=4, scope="pages-read", allowedPages=[3, 4, 5, 6, 7, 8]
    )
    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 4
    for question in questions:
        for page in question["sourcePages"]:
            assert page in {3, 4, 5, 6, 7, 8}


def test_the_two_scopes_are_genuinely_different_behaviours(client) -> None:
    whole = ask(client, count=4)
    assert whole.status_code == 200
    whole_pages = {
        page
        for question in whole.json()["questions"]
        for page in question["sourcePages"]
    }

    restricted = ask(client, count=4, scope="pages-read", allowedPages=[3, 4, 5])
    assert restricted.status_code == 200
    restricted_pages = {
        page
        for question in restricted.json()["questions"]
        for page in question["sourcePages"]
    }
    assert restricted_pages <= {3, 4, 5}
    # The document-scoped quiz is free to range beyond that window.
    assert not whole_pages <= {3, 4, 5}


@pytest.mark.parametrize("count", [5, 8, 10, 12])
def test_the_requested_count_is_met_for_a_rich_pdf(client, count: int) -> None:
    response = ask(client, count=count)
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == count


def test_questions_spread_across_the_document(client) -> None:
    """A 20-page PDF must not be quizzed only on its first content page."""
    response = ask(client, count=12)
    assert response.status_code == 200
    pages = {
        page
        for question in response.json()["questions"]
        for page in question["sourcePages"]
    }
    assert len(pages) >= 4, pages


# --------------------------------------------------------------------------- #
# Stage-by-stage: where the questions were being lost
# --------------------------------------------------------------------------- #


def stage_counts(allowed_pages):
    clear_extraction_cache()
    source = _extract_pdf(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-textbook",
        max_characters=200_000,
        allowed_pages=allowed_pages,
    )
    context = build_quiz_context(source)
    counts = {
        "pdf_pages_extracted": source.page_count,
        "pages_used": len(context.included_pages),
        "text_units": len(context.units),
        "concepts": 0,
        "evidence_items": 0,
    }
    try:
        understanding, _ = build_document_understanding(
            NoProvider(), source, context, system_prompt=""
        )
        counts["concepts"] = len(understanding.concepts)
        counts["evidence_items"] = sum(
            len(concept.evidence) for concept in understanding.concepts
        )
    except Exception:  # noqa: BLE001 - the point is that it produced nothing
        pass
    return counts


def test_restricting_to_page_one_is_what_destroys_the_pipeline() -> None:
    """Pin the measured root cause so it cannot silently return."""
    one_page = stage_counts([1])
    whole = stage_counts(None)

    # Extraction is fine either way -- the PDF is not the problem.
    assert one_page["pdf_pages_extracted"] == 20
    assert whole["pdf_pages_extracted"] == 20

    # But a title-page-only scope yields nothing to build questions from.
    assert one_page["pages_used"] == 1
    assert one_page["concepts"] == 0
    assert one_page["evidence_items"] == 0

    # The same PDF, unrestricted, is rich.
    assert whole["pages_used"] == 20
    assert whole["concepts"] >= 20
    assert whole["evidence_items"] >= 20


def test_the_whole_document_produces_far_more_plans_than_requested() -> None:
    clear_extraction_cache()
    source = _extract_pdf(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-textbook",
        max_characters=200_000,
        allowed_pages=None,
    )
    result = generate_quiz(
        NoProvider(),
        source,
        count=8,
        question_types=["mcq", "true-false", "short-answer", "fill-blank"],
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="",
    )
    assert len(result.questions) == 8
    # Requirement: substantially more plans than questions requested.
    assert result.telemetry["quiz_plans_created"] >= 20
    assert result.telemetry["concepts_found"] >= 8


def test_evidence_keeps_page_numbers_and_knowledge_types() -> None:
    clear_extraction_cache()
    source = _extract_pdf(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-textbook",
        max_characters=200_000,
        allowed_pages=None,
    )
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    for concept in understanding.important_concepts():
        assert concept.name
        assert concept.description
        assert concept.knowledge_type
        assert concept.source_pages
        for evidence in concept.evidence:
            assert evidence.text.strip()
            assert 1 <= evidence.page <= 20


def test_a_narrow_scope_failure_message_names_the_scope() -> None:
    """Requirement 10: don't blame the PDF for a page restriction."""
    from app.services.ai_service import AIUnavailableError

    clear_extraction_cache()
    source = _extract_pdf(
        pdf_bytes(),
        file_id="t",
        title="cell-biology-textbook",
        max_characters=200_000,
        allowed_pages=[1],
    )
    with pytest.raises(AIUnavailableError) as excinfo:
        generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=["mcq", "true-false", "short-answer", "fill-blank"],
            difficulty="medium",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="",
            # The caller genuinely restricted the request, which is what
            # licenses the "only page(s) ..." wording. Without this the
            # message must NOT imply a restriction -- see
            # test_the_scope_note_distinguishes_a_restriction_from_unreadable_pages.
            requested_pages=[1],
        )
    message = str(excinfo.value)
    assert "only page(s) 1 of 20" in message


def test_diagnostics_report_every_stage(client) -> None:
    """A debug view must expose the funnel, and never a secret."""
    response = ask(client, count=8, diagnostics=True)
    assert response.status_code == 200, response.text
    payload = response.json()
    diagnostics = payload["diagnostics"]
    for key in (
        "requested",
        "extracted_pages",
        "pages_used",
        "concepts",
        "evidence_items",
        "plans",
        "candidates_generated",
        "accepted",
        "rejected",
        "rejections",
    ):
        assert key in diagnostics
    assert diagnostics["requested"] == 8
    assert diagnostics["accepted"] == 8
    assert diagnostics["extracted_pages"] == 20
    assert diagnostics["plans"] >= 20

    blob = repr(payload).lower()
    for secret in ("api_key", "apikey", "authorization", "bearer ", "secret"):
        assert secret not in blob


def test_diagnostics_are_absent_unless_requested(client) -> None:
    response = ask(client, count=8)
    assert response.status_code == 200
    assert response.json().get("diagnostics") is None
