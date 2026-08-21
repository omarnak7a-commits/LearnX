"""The reported production failure: 2 of 8 questions from a 32-page deck.

Every earlier investigation ran with the providers unavailable, so the
deterministic reader built the study map and the exam came back full. That is
not what production does. Production gets an *answer* from Gemini -- and when
that answer is thinner than the document, its two concepts used to replace the
document's twenty-six.

These tests exercise the real HTTP endpoint with a provider that behaves the
way a real one does.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services import storage as storage_service
from app.services.ai_documents import _extract_pdf_uncached, clear_extraction_cache
from app.services.ai_service import AIStructuredCompletion
from app.services.quiz_pipeline import (
    _RawQuizPool,
    build_quiz_context,
    generate_quiz,
)
from app.services.quiz_understanding import (
    _RawUnderstanding,
    deterministic_understanding,
)

import app.api.ai as ai_api

FILE_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
PRODUCTION_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]
FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"


def pdf_bytes() -> bytes:
    return FIXTURE.read_bytes()


class FakeSession:
    def __init__(self, record):
        self._record = record

    def get(self, _model, file_id):
        if self._record is None or str(self._record.id) != str(file_id):
            return None
        return self._record

    def scalar(self, _stmt):
        return self._record

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    clear_extraction_cache()
    app.dependency_overrides = {}
    record = SimpleNamespace(
        id=FILE_ID,
        owner_id=OWNER_ID,
        name="SQL18.pdf",
        size_bytes=len(pdf_bytes()),
        mime_type="application/pdf",
        storage_key=f"users/{OWNER_ID}/vault/SQL18.pdf",
        analysis=None,
    )

    def _get_db():
        db = FakeSession(record)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)
    monkeypatch.setattr(
        storage_service, "download_user_object", lambda *a, **k: pdf_bytes()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}
    clear_extraction_cache()


def ask(client, **payload):
    body = {"fileId": FILE_ID, "count": 8}
    body.update(payload)
    return client.post("/api/v1/ai/quiz", json=body)


def _raw_understanding(concepts):
    return _RawUnderstanding.model_validate(
        {
            "subject": "Databases",
            "summary": "A lecture on SQL, keys, joins, normalization and transactions.",
            "main_topics": [],
            "concepts": concepts,
            "relationships": [],
            "learning_objectives": [],
        }
    )


#: Two concepts, both real and both correctly evidenced -- just far fewer than
#: the deck teaches. This is the shape that produced "2 of 8".
THIN_PROVIDER_CONCEPTS = [
    {
        "id": "c1",
        "name": "Primary Key",
        "description": "identifies rows",
        "topic": "Keys",
        "knowledge_type": "definition",
        "teaching_emphasis": "high",
        "evidence_quotes": [
            "A primary key uniquely identifies each row in a table."
        ],
        "source_pages": [4],
        "why_important": "central",
    },
    {
        "id": "c2",
        "name": "Deadlock",
        "description": "circular wait",
        "topic": "Transactions",
        "knowledge_type": "definition",
        "teaching_emphasis": "high",
        "evidence_quotes": [
            "A deadlock occurs when transactions wait on each other forever."
        ],
        "source_pages": [26],
        "why_important": "central",
    },
]


def gemini_returning(concepts, *, questions=None):
    """A provider that answers the understanding call, like production does."""
    understanding = _raw_understanding(concepts)

    class _Gemini:
        def complete_structured(self, **kwargs):
            value = (
                understanding
                if kwargs["response_model"] is _RawUnderstanding
                else _RawQuizPool(questions=list(questions or []))
            )
            return AIStructuredCompletion(
                value=value,
                provider="gemini",
                model="gemini-3.7-flash",
                fallback_used=False,
            )

    return _Gemini()


def _document_understanding():
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    context = build_quiz_context(source)
    return source, context, deterministic_understanding(context.units, title="SQL18")


# --------------------------------------------------------------------------- #
# The fixture matches the reported document profile
# --------------------------------------------------------------------------- #


def test_the_fixture_matches_the_reported_pdf_profile() -> None:
    """32 pages, 30 with text, 2 image-only -- exactly what production reports."""
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        pdf_bytes(),
        file_id="t",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    assert source.page_count == 32
    assert sum(1 for page in source.pages if page.text_available) == 30
    image_only = [
        page.page
        for page in source.pages
        if not page.text_available and page.image_available
    ]
    assert len(image_only) == 2, image_only


# --------------------------------------------------------------------------- #
# The bug, and the fix
# --------------------------------------------------------------------------- #


def test_a_thin_provider_map_no_longer_discards_the_document(client) -> None:
    """The reported failure: Gemini returns 2 concepts for a 26-concept deck.

    Before the fix this returned HTTP 422 with "could only verify 2 of 8".
    """
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["questions"]) == 8

    diagnostics = body["diagnostics"]
    assert diagnostics["concepts_proposed_by_provider"] == 2
    # The provider's own concepts are kept; the document supplies the rest.
    assert diagnostics["concepts"] >= 20, diagnostics
    assert diagnostics["understanding_source"] == "provider+document"
    assert diagnostics["provider_calls"]["provider_map_supplemented"] == 1
    assert diagnostics["accepted"] == 8


def test_the_provider_concepts_are_kept_not_replaced(client) -> None:
    """Supplementing must not throw away what the provider got right."""
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    )
    diagnostics = response.json()["diagnostics"]
    calls = diagnostics["provider_calls"]
    assert calls["provider_concepts_kept"] == 2
    assert calls["concepts_added_from_document"] >= 15


def test_a_rich_provider_map_is_left_alone(client) -> None:
    """No supplement when the provider already understood the document.

    The document must not quietly override a good provider answer.
    """
    _, context, document = _document_understanding()
    concepts = [
        {
            "id": f"c{index}",
            "name": concept.name,
            "description": concept.description or "described in the deck",
            "topic": "Course",
            "knowledge_type": "definition",
            "teaching_emphasis": "high",
            "evidence_quotes": [concept.evidence[0].text],
            "source_pages": [concept.evidence[0].page],
            "why_important": "central",
        }
        for index, concept in enumerate(document.concepts[:14], start=1)
    ]
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(concepts)
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["understanding_source"] == "provider"
    assert "provider_map_supplemented" not in diagnostics["provider_calls"]


def test_supplemented_concepts_are_all_page_grounded() -> None:
    """Every concept added from the document must cite a real page.

    The supplement may not become a backdoor for ungrounded content.
    """
    source, context, document = _document_understanding()
    page_text = {unit.page: unit.text for unit in context.units}
    assert document.concepts, "fixture teaches nothing"
    for concept in document.concepts:
        assert concept.evidence, f"{concept.name} has no evidence"
        for evidence in concept.evidence:
            assert evidence.page in page_text, (
                f"{concept.name} cites page {evidence.page}, which was not used"
            )


# --------------------------------------------------------------------------- #
# Diagnostics must localise the loss
# --------------------------------------------------------------------------- #


def test_diagnostics_break_the_funnel_down_by_question_type(client) -> None:
    """A type-allocation failure must not look like a thin document."""
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    diagnostics = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    ).json()["diagnostics"]

    plans_by_type = diagnostics["plans_by_type"]
    assert plans_by_type, diagnostics
    assert set(plans_by_type) <= set(PRODUCTION_TYPES)
    assert sum(plans_by_type.values()) == diagnostics["plans"]


def test_every_dropped_candidate_records_a_reason(client) -> None:
    """No silent drops: each rejection names its stage, reason and concept."""
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    diagnostics = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    ).json()["diagnostics"]

    assert len(diagnostics["rejection_details"]) >= diagnostics["rejected"] or (
        diagnostics["rejected"] > 40
    )
    for detail in diagnostics["rejection_details"]:
        assert detail["stage"], detail
        assert detail["reason"], detail
        # A generic catch-all is not an explanation.
        assert detail["reason"] != "failed grounding/shape/type validation", detail


def test_image_only_pages_are_named_not_just_counted(client) -> None:
    """The 2 scanned pages must be identifiable, not merely tallied."""
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    diagnostics = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    ).json()["diagnostics"]
    assert diagnostics["image_only_pages"] == 2
    quality = " ".join(diagnostics["page_quality"])
    assert "image available" in quality


# --------------------------------------------------------------------------- #
# Contract and honesty
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("count", [8, 12])
def test_the_requested_count_is_returned(client, count: int) -> None:
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    response = ask(
        client,
        count=count,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == count


@pytest.mark.parametrize("question_type", PRODUCTION_TYPES)
def test_each_type_still_works_alone(client, question_type: str) -> None:
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    response = ask(
        client,
        count=4,
        kind="exam",
        scope="document",
        questionTypes=[question_type],
    )
    assert response.status_code == 200, (question_type, response.text)
    questions = response.json()["questions"]
    assert len(questions) == 4
    assert {question["type"] for question in questions} == {question_type}


@pytest.mark.parametrize("seed", [1, 3, 5, 7, 11])
def test_the_deck_is_stable_across_seeds(client, seed: int) -> None:
    app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
        THIN_PROVIDER_CONCEPTS
    )
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        seed=seed,
    )
    assert response.status_code == 200, (seed, response.text)
    assert len(response.json()["questions"]) == 8


def test_a_document_that_cannot_support_the_count_still_fails(client) -> None:
    """The supplement must not manufacture questions from a thin document.

    Only three slides carry teaching content, so the honest answer is fewer
    than eight -- not eight invented ones.
    """
    import sys

    sys.path.insert(0, str(FIXTURE.parent))
    from make_textbook_pdf import make_pdf  # type: ignore[import-not-found]

    thin = FIXTURE.parent / "_tmp_thin_provider_deck.pdf"
    make_pdf(
        [
            ["Lecture 1", "- A checksum is a value computed from a block of data."],
            ["Agenda", "- Introductions"],
            ["Questions?"],
        ],
        str(thin),
    )
    try:
        payload = thin.read_bytes()

        def _download(*_a, **_k):
            return payload

        import app.services.storage as storage_module

        original = storage_module.download_user_object
        storage_module.download_user_object = _download
        clear_extraction_cache()
        app.dependency_overrides[ai_api.get_ai_service] = lambda: gemini_returning(
            THIN_PROVIDER_CONCEPTS
        )
        try:
            response = ask(
                client,
                count=8,
                kind="exam",
                scope="document",
                questionTypes=PRODUCTION_TYPES,
                diagnostics=True,
            )
        finally:
            storage_module.download_user_object = original
        assert response.status_code == 422, response.text
        assert isinstance(response.json()["detail"], str)
    finally:
        thin.unlink(missing_ok=True)
        clear_extraction_cache()
