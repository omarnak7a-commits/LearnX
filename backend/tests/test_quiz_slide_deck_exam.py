"""The reported production failure: a lecture slide deck yields 1 of 8 questions.

The 32-page fixture used elsewhere is prose. Real lecture material is not: it
is bulleted, and every teaching sentence on a slide begins with a list glyph.
That single difference took the document from 26 usable concepts to 2, which is
what produced "LearnX could only verify 1 of 8". These tests pin the slide-deck
shape specifically, over the real HTTP endpoint, with the payload the frontend
sends.
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
from app.services.quiz_pipeline import build_quiz_context
from app.services.quiz_understanding import deterministic_understanding

FILE_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
PRODUCTION_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]

FIXTURE = Path(__file__).parent / "fixtures" / "sql_lecture_32_pages.pdf"


def deck_bytes() -> bytes:
    return FIXTURE.read_bytes()


class FakeSession:
    """Mirrors the session shape the real endpoint uses."""

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
        size_bytes=len(deck_bytes()),
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
        storage_service, "download_user_object", lambda *a, **k: deck_bytes()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}
    clear_extraction_cache()


def ask(client, **payload):
    body = {"fileId": FILE_ID, "count": 8}
    body.update(payload)
    return client.post("/api/v1/ai/quiz", json=body)


def _deck_context():
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        deck_bytes(),
        file_id="t",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    return source, build_quiz_context(source)


# --------------------------------------------------------------------------- #
# The root cause, in isolation
# --------------------------------------------------------------------------- #


def test_a_bullet_glyph_does_not_change_what_the_document_teaches() -> None:
    """The same sentence must be understood with or without its list marker.

    This is the whole bug. "- A primary key uniquely identifies each row" and
    "A primary key uniquely identifies each row" are the same teaching
    sentence; only typography differs.
    """
    from app.services.ai_documents import AIDocumentSource, PageExtraction

    slides = [
        ("Primary Key", "A primary key uniquely identifies each row in a table."),
        ("Foreign Key", "A foreign key references the primary key of another table."),
        ("Inner Join", "An inner join returns rows matching in both tables."),
        ("Indexes", "An index is a data structure that speeds up lookups."),
        ("Transactions", "A transaction is a unit of work executed atomically."),
        ("Views", "A view is a named query stored in the schema."),
        ("Deadlock", "A deadlock occurs when transactions wait on each other."),
        ("Triggers", "A trigger executes automatically on a table event."),
    ]

    def concepts_for(*, bulleted: bool) -> int:
        marker = "- " if bulleted else ""
        text = "\n".join(
            f"[Page {index}]\n{title}\n{marker}{body}"
            for index, (title, body) in enumerate(slides, start=1)
        )
        source = AIDocumentSource(
            file_id="f",
            title="SQL18",
            text=text,
            page_count=len(slides),
            pages=tuple(
                PageExtraction(page=index, text_length=80, image_available=False)
                for index in range(1, len(slides) + 1)
            ),
        )
        understanding = deterministic_understanding(
            build_quiz_context(source).units, title="SQL18"
        )
        return len(understanding.concepts)

    bulleted = concepts_for(bulleted=True)
    plain = concepts_for(bulleted=False)
    assert bulleted == plain, (
        f"bullets changed comprehension: {bulleted} concepts vs {plain}"
    )
    # Before the fix this was 0: every bulleted definition was invisible.
    assert bulleted >= 5


@pytest.mark.parametrize(
    "line, expected",
    [
        ("- A primary key identifies a row.", "A primary key identifies a row."),
        ("\u2022 An index speeds up lookups.", "An index speeds up lookups."),
        ("\u25cf A view is a stored query.", "A view is a stored query."),
        ("* A trigger fires on an event.", "A trigger fires on an event."),
        ("\u2013 A deadlock blocks forever.", "A deadlock blocks forever."),
        # Not bullets: these must survive untouched.
        ("-5 degrees Celsius is the floor.", "-5 degrees Celsius is the floor."),
        ("--verbose enables logging.", "--verbose enables logging."),
        ("well-formed XML is required.", "well-formed XML is required."),
    ],
)
def test_only_real_list_glyphs_are_stripped(line: str, expected: str) -> None:
    """A hyphen is only a bullet when a space follows it."""
    from app.services.quiz_boilerplate import strip_bullet_prefix

    assert strip_bullet_prefix(line) == expected


# --------------------------------------------------------------------------- #
# The reported failure, end to end over HTTP
# --------------------------------------------------------------------------- #


def test_the_reported_deck_returns_a_full_exam(client) -> None:
    """Test 1: 32 pages, production payload, 8 grounded questions."""
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
    assert diagnostics["extracted_pages"] == 32
    assert diagnostics["pages_used"] == 32
    assert diagnostics["pages_dropped_in_cleaning"] == 0
    # The regression: understanding used to survive with 2 concepts here.
    assert diagnostics["concepts"] >= 20, diagnostics
    assert diagnostics["evidence_items"] >= 8
    assert diagnostics["plans"] >= 8
    assert diagnostics["accepted"] == 8


def test_every_question_is_tied_to_a_real_page(client) -> None:
    """Test 7 (inverse): accepted questions must stay page-grounded."""
    response = ask(
        client, count=8, kind="exam", scope="document", questionTypes=PRODUCTION_TYPES
    )
    assert response.status_code == 200, response.text
    for question in response.json()["questions"]:
        pages = question.get("sourcePages") or []
        assert pages, f"question has no source page: {question['prompt']}"
        assert all(1 <= int(page) <= 32 for page in pages), pages


@pytest.mark.parametrize("question_type", PRODUCTION_TYPES)
def test_each_question_type_works_on_its_own(client, question_type: str) -> None:
    """Test 5 (part 1): no single type may carry the whole exam."""
    response = ask(
        client, count=4, kind="exam", scope="document", questionTypes=[question_type]
    )
    assert response.status_code == 200, (question_type, response.text)
    questions = response.json()["questions"]
    assert len(questions) == 4
    assert {question["type"] for question in questions} == {question_type}


def test_the_mixed_production_request_reaches_the_requested_count(client) -> None:
    """Test 5 (part 2): all four types together, exactly as the frontend asks."""
    response = ask(
        client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        diagnostics=True,
    )
    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 8
    # Every type present must be one that was requested; a type the deck cannot
    # support is redistributed, never invented.
    assert {question["type"] for question in questions} <= set(PRODUCTION_TYPES)


@pytest.mark.parametrize("seed", [1, 3, 5, 7, 11])
def test_the_deck_yields_a_full_exam_on_every_seed(client, seed: int) -> None:
    """Randomness may reorder the exam; it may never shorten it."""
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


def test_the_deck_supports_more_than_the_requested_eight(client) -> None:
    """A deck this rich must not be exhausted by eight questions."""
    response = ask(
        client, count=12, kind="exam", scope="document", questionTypes=PRODUCTION_TYPES
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["questions"]) == 12


def test_a_genuinely_thin_deck_still_fails_honestly(client, monkeypatch) -> None:
    """Test 7: the fix must not turn a real shortage into invented questions."""
    import sys

    sys.path.insert(0, str(FIXTURE.parent))
    from make_textbook_pdf import make_pdf  # type: ignore[import-not-found]

    thin = FIXTURE.parent / "_tmp_thin_deck.pdf"
    # Real teaching content, but only one concept's worth of it.
    make_pdf(
        [
            ["Lecture 1", "- A checksum is a value computed from data."],
            ["Agenda"],
            ["Questions?"],
        ],
        str(thin),
    )
    try:
        payload = thin.read_bytes()
        monkeypatch.setattr(
            storage_service, "download_user_object", lambda *a, **k: payload
        )
        clear_extraction_cache()
        response = ask(
            client,
            count=8,
            kind="exam",
            scope="document",
            questionTypes=PRODUCTION_TYPES,
            diagnostics=True,
        )
        assert response.status_code == 422, response.text
        body = response.json()
        assert isinstance(body["detail"], str)
        # The shortage must be evidenced, not asserted. Diagnostics are present
        # whenever a funnel was actually built; a deck with no teaching text at
        # all is refused earlier, by a stricter guard.
        diagnostics = body.get("diagnostics")
        if diagnostics is not None:
            assert diagnostics["concepts"] < 8, diagnostics
    finally:
        thin.unlink(missing_ok=True)
        clear_extraction_cache()


def test_bulleted_pages_are_not_reported_as_dropped(client) -> None:
    """A bulleted page is readable content and must count as used."""
    source, context = _deck_context()
    assert len(context.units) == 32
    assert sorted(context.included_pages) == list(range(1, 33))


# --------------------------------------------------------------------------- #
# Marker styles: a numbered slide is defeated by the same mechanism as a
# bulleted one, so both belong in the same guarantee.
# --------------------------------------------------------------------------- #


MIXED_FIXTURE = FIXTURE.parent / "sql_lecture_mixed_32_pages.pdf"


@pytest.fixture
def mixed_client(client, monkeypatch):
    """The deck fixture, but serving the mixed-marker PDF."""
    payload = MIXED_FIXTURE.read_bytes()
    monkeypatch.setattr(
        storage_service, "download_user_object", lambda *a, **k: payload
    )
    clear_extraction_cache()
    yield client
    clear_extraction_cache()


@pytest.mark.parametrize(
    "marker",
    [
        "- ",
        "\u2022 ",
        "* ",
        "\u25aa ",
        "\u25cf ",
        "\u2013 ",
        "\u00b7 ",
        "1. ",
        "2) ",
        "(3) ",
        "a) ",
        "\t- ",
        "  \u2022  ",
    ],
    ids=[
        "hyphen",
        "round-bullet",
        "asterisk",
        "square-bullet",
        "filled-circle",
        "en-dash",
        "middle-dot",
        "numbered-dot",
        "numbered-paren",
        "numbered-bracketed",
        "lettered",
        "tab-indented",
        "space-indented",
    ],
)
def test_no_list_marker_changes_what_the_document_teaches(marker: str) -> None:
    """Every list marker must yield the same understanding as plain prose.

    Slide decks number as often as they bullet. Both are typography, and a
    document must not teach less because of how its author formatted it.
    """
    from app.services.ai_documents import AIDocumentSource, PageExtraction

    slides = [
        ("Primary Key", "A primary key uniquely identifies each row in a table."),
        ("Foreign Key", "A foreign key references the primary key of another table."),
        ("Inner Join", "An inner join returns rows matching in both tables."),
        ("Indexes", "An index is a data structure that speeds up lookups."),
        ("Transactions", "A transaction is a unit of work executed atomically."),
        ("Views", "A view is a named query stored in the schema."),
        ("Deadlock", "A deadlock occurs when transactions wait on each other."),
        ("Triggers", "A trigger executes automatically on a table event."),
    ]

    def concepts_for(prefix: str) -> int:
        text = "\n".join(
            f"[Page {index}]\n{title}\n{prefix}{body}"
            for index, (title, body) in enumerate(slides, start=1)
        )
        source = AIDocumentSource(
            file_id="f",
            title="SQL18",
            text=text,
            page_count=len(slides),
            pages=tuple(
                PageExtraction(page=index, text_length=90, image_available=False)
                for index in range(1, len(slides) + 1)
            ),
        )
        return len(
            deterministic_understanding(
                build_quiz_context(source).units, title="SQL18"
            ).concepts
        )

    baseline = concepts_for("")
    assert baseline >= 5, "fixture no longer teaches enough to be a control"
    assert concepts_for(marker) == baseline, (
        f"marker {marker!r} cost the document concepts: "
        f"{concepts_for(marker)} vs {baseline} unmarked"
    )


@pytest.mark.parametrize(
    "line",
    [
        "-5 degrees Celsius is the floor.",
        "--verbose enables logging.",
        "well-formed XML is required.",
        "A-B testing compares two variants.",
        "x = -3 is the root of the equation.",
        "E = mc^2 relates mass and energy.",
        "f(x) = 2x + 1 defines a straight line.",
        "SELECT * FROM users WHERE id = 1;",
        "2 * 3 = 6 is a multiplication.",
        "git commit -m 'message' records a change.",
        "1929. The crash began in October.",
        "3.2 The Nucleus and Genetic Material",
        "0.5 mol of solute per litre.",
        "A. Hassan wrote this lecture.",
    ],
)
def test_content_that_merely_looks_like_a_marker_is_preserved(line: str) -> None:
    """Negative numbers, CLI flags, formulas, code and section numbers.

    The cost of over-stripping is silent corruption of the source of truth, so
    the rule is deliberately narrow.
    """
    from app.services.quiz_boilerplate import strip_bullet_prefix

    assert strip_bullet_prefix(line) == line


@pytest.mark.parametrize("line", ["1.", "-", "\u2022", "a)", "(3)"])
def test_a_marker_only_line_is_never_blanked(line: str) -> None:
    """A lone marker is a page artefact; cleaning must not delete the line."""
    from app.services.quiz_boilerplate import strip_bullet_prefix

    assert strip_bullet_prefix(line) == line


def test_a_mixed_marker_deck_returns_a_full_exam(mixed_client) -> None:
    """Every marker style in one deck, over HTTP, with the production payload."""
    response = ask(
        mixed_client,
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
    assert diagnostics["extracted_pages"] == 32
    assert diagnostics["concepts"] >= 20, diagnostics
    assert diagnostics["accepted"] == 8


def test_numbered_slides_contribute_their_own_concepts(mixed_client) -> None:
    """Concepts introduced only on numbered slides must reach the study map.

    Without this the deck could still reach 8 questions purely from its
    bulleted slides while every numbered slide stayed invisible.
    """
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        MIXED_FIXTURE.read_bytes(),
        file_id="t",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    understanding = deterministic_understanding(
        build_quiz_context(source).units, title="SQL18"
    )
    names = " ".join(concept.name.lower() for concept in understanding.concepts)
    for taught_on_a_numbered_slide in (
        "outer join",
        "projection",
        "aggregate",
        "functional dependency",
        "atomicity",
        "durability",
    ):
        assert taught_on_a_numbered_slide in names, (
            f"{taught_on_a_numbered_slide!r} was taught but never understood"
        )


def test_code_and_formulas_survive_extraction(mixed_client) -> None:
    """The PDF is the source of truth; cleaning must not rewrite it."""
    clear_extraction_cache()
    source = _extract_pdf_uncached(
        MIXED_FIXTURE.read_bytes(),
        file_id="t",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )
    joined = "\n".join(unit.text for unit in build_quiz_context(source).units)
    for verbatim in (
        "-5 degrees",
        "--verbose",
        "well-formed",
        "SELECT * FROM users",
        "f(x) = 2x + 1",
        "3.2 Cost Model",
    ):
        assert verbatim in joined, f"extraction corrupted {verbatim!r}"


@pytest.mark.parametrize("seed", [1, 3, 5, 7, 11])
def test_the_mixed_deck_is_stable_across_seeds(mixed_client, seed: int) -> None:
    response = ask(
        mixed_client,
        count=8,
        kind="exam",
        scope="document",
        questionTypes=PRODUCTION_TYPES,
        seed=seed,
    )
    assert response.status_code == 200, (seed, response.text)
    assert len(response.json()["questions"]) == 8
