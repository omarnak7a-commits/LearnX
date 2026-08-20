"""The PDF -> quiz contract: exactly what was requested, or an honest refusal.

These tests cover the failure this pipeline exists to prevent: a student
finishes a PDF, asks for an eight-question exam, and receives one question --
sometimes about something the PDF never discussed.

They deliberately run against the *real* demo PDFs and corpus fixtures rather
than hand-written prose, because the bug only ever appeared on real documents:
the candidate pool was large enough to pass every unit test, and the shortfall
appeared at the very last stage, where redundancy gates discarded valid
questions the quiz still needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import ai_documents
from app.services.ai_documents import (
    AIDocumentSource,
    _extract_pdf,
    clear_extraction_cache,
    source_from_text,
)
from app.services.ai_service import AIServiceError, AIUnavailableError
from app.services.quiz_pipeline import (
    QuizMaterialError,
    generate_quiz,
    validate_final_quiz,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "public" / "demo-files"
CORPUS_DIR = Path(__file__).resolve().parent / "fixtures" / "domain_corpus"

ALL_TYPES = ["mcq", "true-false", "short-answer", "fill-blank"]
SEEDS = (1, 3, 5, 7, 11)


class NoProvider:
    """Gemini and Groq are both unavailable.

    This is the worst realistic case and the one the bug report describes: the
    backend must still build a complete, grounded quiz from its own study map,
    or say clearly that it cannot.
    """

    def complete_structured(self, **_kwargs):
        raise AIServiceError("no provider configured")


def load_pdf(name: str) -> AIDocumentSource:
    path = DEMO_DIR / name
    return _extract_pdf(
        path.read_bytes(),
        file_id=path.stem,
        title=path.stem,
        max_characters=200_000,
        allowed_pages=None,
    )


def load_corpus(name: str) -> AIDocumentSource:
    """Paginate a text fixture so page provenance is exercised identically."""
    raw = (CORPUS_DIR / name).read_text(encoding="utf-8")
    paragraphs = [block.strip() for block in raw.split("\n\n") if block.strip()]
    per_page = max(1, len(paragraphs) // 4)
    pages, chunk = [], []
    for paragraph in paragraphs:
        chunk.append(paragraph)
        if len(chunk) >= per_page and len(pages) < 3:
            pages.append("\n".join(chunk))
            chunk = []
    if chunk:
        pages.append("\n".join(chunk))
    text = "\n\n".join(f"[Page {i}]\n{page}" for i, page in enumerate(pages, start=1))
    return AIDocumentSource(
        file_id=name, title=name, text=text, page_count=len(pages)
    )


def build(source: AIDocumentSource, *, count: int = 8, seed: int = 1, **overrides):
    kwargs = dict(
        count=count,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=seed,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )
    kwargs.update(overrides)
    return generate_quiz(NoProvider(), source, **kwargs)


ALL_SOURCES = [
    "calculus-limits-derivatives.pdf",
    "cell-biology-ch3.pdf",
    "operating-systems-scheduling.pdf",
    "physics-newtonian-mechanics.pdf",
]


# --------------------------------------------------------------------------- #
# 1. An 8-question request returns exactly 8 valid questions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ALL_SOURCES)
@pytest.mark.parametrize("seed", SEEDS)
def test_eight_requested_returns_exactly_eight(name: str, seed: int) -> None:
    result = build(load_pdf(name), count=8, seed=seed)
    assert len(result.questions) == 8


@pytest.mark.parametrize(
    "name",
    ["chemistry-bonding.txt", "geography-landforms.txt", "history-ww1.txt", "literature-analysis.txt"],
)
@pytest.mark.parametrize("seed", SEEDS)
def test_eight_requested_across_subjects(name: str, seed: int) -> None:
    """Subject neutrality: the count holds for history and literature too."""
    result = build(load_corpus(name), count=8, seed=seed)
    assert len(result.questions) == 8


@pytest.mark.parametrize("count", [3, 5, 8, 10])
def test_other_counts_are_honoured_exactly(count: int) -> None:
    result = build(load_pdf("cell-biology-ch3.pdf"), count=count)
    assert len(result.questions) == count


def test_the_reported_symptom_never_recurs() -> None:
    """A request for 8 must never come back as 1."""
    result = build(load_pdf("physics-newtonian-mechanics.pdf"), count=8)
    assert len(result.questions) != 1
    assert len(result.questions) == 8


# --------------------------------------------------------------------------- #
# 2. Questions are grounded in the PDF
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ALL_SOURCES)
def test_every_question_is_traceable_to_a_pdf_concept(name: str) -> None:
    source = load_pdf(name)
    result = build(source, count=8)
    assert len(result.provenance) == len(result.questions)

    concepts = {c.concept_id for c in result.understanding.important_concepts()}
    for record in result.provenance:
        assert record.concept_id in concepts
        assert record.knowledge_target_id
        assert record.source_pages


@pytest.mark.parametrize("name", ALL_SOURCES)
def test_no_question_cites_a_page_the_document_does_not_have(name: str) -> None:
    source = load_pdf(name)
    result = build(source, count=8)
    for question in result.questions:
        assert question.source_pages
        for page in question.source_pages:
            assert 1 <= page <= source.page_count


def test_questions_are_not_derived_from_the_filename() -> None:
    """The title is metadata, never a source of knowledge."""
    source = load_pdf("cell-biology-ch3.pdf")
    result = build(source, count=8)
    for question in result.questions:
        assert "cell-biology-ch3" not in question.prompt.lower()
        assert ".pdf" not in question.prompt.lower()


# --------------------------------------------------------------------------- #
# 3./4. Unrelated questions and unsupported answers are rejected
# --------------------------------------------------------------------------- #


def _validation_kit(name: str = "cell-biology-ch3.pdf"):
    from app.services.quiz_pipeline import build_document_understanding, build_quiz_context

    source = load_pdf(name)
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    result = build(source, count=8)
    provenance = {record.question_id: record for record in result.provenance}
    return source, context, understanding, result, provenance


def test_a_question_about_a_concept_not_in_the_pdf_is_rejected() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    question = result.questions[0]
    record = provenance[question.id]
    # Same well-formed question, but attributed to a concept the PDF lacks.
    provenance[question.id] = type(record)(
        **{**record.__dict__, "concept_id": "quantum-chromodynamics", "concept": "Quantum chromodynamics"}
    )

    valid, notes = validate_final_quiz(
        [question],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id=provenance,
        requested_types=ALL_TYPES,
    )
    assert valid == []
    assert "not in the document study map" in notes[0].reason


def test_a_question_with_no_traceable_origin_is_rejected() -> None:
    source, context, understanding, result, _ = _validation_kit()
    valid, notes = validate_final_quiz(
        [result.questions[0]],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id={},  # nothing traces back
        requested_types=ALL_TYPES,
    )
    assert valid == []
    assert "not traceable" in notes[0].reason


def test_an_answer_absent_from_the_options_is_rejected() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    mcq = next(q for q in result.questions if q.type == "mcq")
    tampered = mcq.model_copy(update={"correct_answer": "A cure for the common cold"})
    valid, notes = validate_final_quiz(
        [tampered],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id={tampered.id: provenance[mcq.id]},
        requested_types=ALL_TYPES,
    )
    assert valid == []
    assert "not among the options" in notes[0].reason


def test_a_citation_to_an_unread_page_is_rejected() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    question = result.questions[0]
    tampered = question.model_copy(update={"source_pages": [source.page_count + 50]})
    valid, notes = validate_final_quiz(
        [tampered],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id={tampered.id: provenance[question.id]},
        requested_types=ALL_TYPES,
    )
    assert valid == []
    assert "not in the extracted source pages" in notes[0].reason


def test_a_question_of_an_unrequested_type_is_rejected() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    mcq = next(q for q in result.questions if q.type == "mcq")
    valid, notes = validate_final_quiz(
        [mcq],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id=provenance,
        requested_types=["short-answer"],
    )
    assert valid == []
    assert "was not requested" in notes[0].reason


def test_an_empty_answer_is_rejected() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    question = result.questions[0]
    tampered = question.model_copy(update={"correct_answer": "   "})
    valid, notes = validate_final_quiz(
        [tampered],
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id={tampered.id: provenance[question.id]},
        requested_types=ALL_TYPES,
    )
    assert valid == []
    assert "empty correct answer" in notes[0].reason


def test_a_clean_quiz_passes_final_validation_untouched() -> None:
    source, context, understanding, result, provenance = _validation_kit()
    valid, notes = validate_final_quiz(
        result.questions,
        context=context,
        source=source,
        understanding=understanding,
        provenance_by_id=provenance,
        requested_types=ALL_TYPES,
    )
    assert len(valid) == len(result.questions)
    assert notes == []


# --------------------------------------------------------------------------- #
# 5. A PDF with insufficient content does not return a fake quiz
# --------------------------------------------------------------------------- #


def test_a_thin_note_refuses_rather_than_inventing_questions() -> None:
    thin = source_from_text(
        "Photosynthesis is the process by which plants convert light into chemical energy.",
        "Thin note",
    )
    with pytest.raises(QuizMaterialError) as excinfo:
        build(thin, count=8)
    error = excinfo.value
    assert error.requested == 8
    assert error.available < 8
    # The message must name the real limit: the document, not the service.
    assert "does not contain enough" in str(error)
    assert str(error.available) in str(error)


def test_a_contentless_source_reports_unavailable() -> None:
    with pytest.raises(AIUnavailableError):
        build(source_from_text("Water boils.", "Fragment"), count=8)


def test_a_filename_shaped_source_produces_no_quiz() -> None:
    """The filename is not knowledge; it cannot seed a quiz."""
    with pytest.raises(AIUnavailableError):
        build(source_from_text("cell-biology-ch3", "cell-biology-ch3"), count=8)


def test_a_thin_note_never_returns_a_partial_quiz_silently() -> None:
    thin = source_from_text(
        "Evaporation is the process by which liquid water changes into water vapor. "
        "Heat supplies the energy that causes evaporation.",
        "Note",
    )
    try:
        result = build(thin, count=8)
    except AIUnavailableError:
        return  # refusing outright is also correct
    assert len(result.questions) == 8, "a partial quiz must raise, not be returned"


# --------------------------------------------------------------------------- #
# 6. Page references remain correct
# --------------------------------------------------------------------------- #


def test_page_references_point_at_pages_that_really_exist() -> None:
    source = load_pdf("cell-biology-ch3.pdf")
    result = build(source, count=8)
    telemetry = result.telemetry
    assert telemetry["pages_used"] == sorted(set(telemetry["pages_used"]))
    for question in result.questions:
        for page in question.source_pages:
            assert page in telemetry["pages_used"]


def test_provenance_pages_match_question_pages() -> None:
    result = build(load_pdf("operating-systems-scheduling.pdf"), count=8)
    by_id = {q.id: q for q in result.questions}
    for record in result.provenance:
        assert tuple(by_id[record.question_id].source_pages) == record.source_pages


# --------------------------------------------------------------------------- #
# 7. One failed question does not reduce the final quiz count
# --------------------------------------------------------------------------- #


def test_a_rejected_candidate_is_replaced_not_subtracted() -> None:
    """Rejections happen on real documents; the quiz still comes back full."""
    result = build(load_corpus("history-ww1.txt"), count=8)
    rejected = [n for n in result.rejections if n.stage not in {"diversity_selection"}]
    assert rejected, "expected this document to reject at least one candidate"
    assert len(result.questions) == 8


def test_the_pool_is_topped_up_when_selection_would_fall_short() -> None:
    """Regression: physics returned 7/8 because the pool had no headroom."""
    for seed in SEEDS:
        result = build(load_pdf("physics-newtonian-mechanics.pdf"), count=8, seed=seed)
        assert len(result.questions) == 8
        assert result.telemetry["quiz_plans_created"] >= 8


def test_questions_are_never_padded_by_duplication() -> None:
    """Filling the quiz must add new material, never repeat a question."""
    for name in ALL_SOURCES:
        result = build(load_pdf(name), count=8)
        prompts = [q.prompt.strip().casefold() for q in result.questions]
        assert len(set(prompts)) == len(prompts)
        pairs = {(q.prompt, q.correct_answer) for q in result.questions}
        assert len(pairs) == len(result.questions)
        targets = [r.knowledge_target_id for r in result.provenance]
        assert len(set(targets)) == len(targets)


# --------------------------------------------------------------------------- #
# 8. Repeated generation does not re-extract the PDF unnecessarily
# --------------------------------------------------------------------------- #


def test_generating_a_quiz_never_re_extracts_the_pdf(monkeypatch) -> None:
    source = load_pdf("cell-biology-ch3.pdf")
    calls = {"n": 0}
    real = ai_documents._extract_pdf_uncached

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(ai_documents, "_extract_pdf_uncached", counted)
    build(source, count=8)
    assert calls["n"] == 0, "the document is extracted once, before generation"


def test_repeated_extraction_of_the_same_pdf_is_cached(monkeypatch) -> None:
    clear_extraction_cache()
    data = (DEMO_DIR / "cell-biology-ch3.pdf").read_bytes()
    calls = {"n": 0}
    real = ai_documents._extract_pdf_uncached

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(ai_documents, "_extract_pdf_uncached", counted)
    for _ in range(4):
        _extract_pdf(
            data, file_id="f", title="cell", max_characters=200_000, allowed_pages=None
        )
    assert calls["n"] == 1


def test_a_different_page_selection_is_not_a_stale_cache_hit() -> None:
    clear_extraction_cache()
    data = (DEMO_DIR / "cell-biology-ch3.pdf").read_bytes()
    full = _extract_pdf(
        data, file_id="f", title="cell", max_characters=200_000, allowed_pages=None
    )
    page_one = _extract_pdf(
        data, file_id="f", title="cell", max_characters=200_000, allowed_pages=[1]
    )
    assert full.text != page_one.text
    assert "[Page 1]" in page_one.text
    assert "[Page 3]" not in page_one.text


# --------------------------------------------------------------------------- #
# 9. Reading-page restrictions work correctly when enabled
# --------------------------------------------------------------------------- #


def test_a_page_restricted_quiz_only_cites_the_pages_the_student_read() -> None:
    clear_extraction_cache()
    data = (DEMO_DIR / "cell-biology-ch3.pdf").read_bytes()
    read_pages = [1, 3]
    restricted = _extract_pdf(
        data,
        file_id="f",
        title="cell-biology-ch3",
        max_characters=200_000,
        allowed_pages=read_pages,
    )
    result = build(restricted, count=5)
    assert len(result.questions) == 5
    for question in result.questions:
        for page in question.source_pages:
            assert page in read_pages, "a question came from a page never read"
    assert result.telemetry["pages_used"] == read_pages


def test_restricted_extraction_keeps_real_page_numbers() -> None:
    """Page 3 must stay page 3, not be renumbered to 2."""
    clear_extraction_cache()
    data = (DEMO_DIR / "cell-biology-ch3.pdf").read_bytes()
    restricted = _extract_pdf(
        data, file_id="f", title="t", max_characters=200_000, allowed_pages=[1, 3]
    )
    assert "[Page 1]" in restricted.text
    assert "[Page 3]" in restricted.text
    assert "[Page 2]" not in restricted.text


def test_unrestricted_generation_uses_the_whole_document() -> None:
    source = load_pdf("cell-biology-ch3.pdf")
    result = build(source, count=8)
    assert result.telemetry["pages_used"] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# 10. Every question type validates correctly
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "question_type", ["mcq", "true-false", "short-answer"]
)
def test_each_question_type_produces_valid_questions(question_type: str) -> None:
    result = build(
        load_pdf("cell-biology-ch3.pdf"),
        count=4,
        question_types=[question_type],
    )
    assert len(result.questions) == 4
    for question in result.questions:
        assert question.type == question_type
        assert question.prompt.strip()
        assert question.correct_answer.strip()
        if question_type in {"mcq", "true-false"}:
            options = list(question.options or [])
            assert len(options) >= 2
            assert question.correct_answer in options
        if question_type == "true-false":
            assert {o.casefold() for o in question.options or []} == {"true", "false"}


def test_a_mixed_type_request_stays_within_the_requested_types() -> None:
    requested = ["mcq", "true-false"]
    result = build(load_pdf("cell-biology-ch3.pdf"), count=6, question_types=requested)
    assert len(result.questions) == 6
    assert {q.type for q in result.questions} <= set(requested)


def test_fill_blank_questions_carry_a_real_blank() -> None:
    from app.services.quiz_boilerplate import is_valid_fill_blank

    for name in ALL_SOURCES:
        result = build(load_pdf(name), count=8)
        for question in result.questions:
            if question.type == "fill-blank":
                assert is_valid_fill_blank(question.prompt)


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #


def test_the_funnel_is_reported_for_every_generation() -> None:
    result = build(load_pdf("cell-biology-ch3.pdf"), count=8)
    telemetry = result.telemetry
    for key in (
        "pdf_pages_available",
        "pages_used",
        "extracted_text",
        "concepts_found",
        "quiz_requested",
        "quiz_plans_created",
        "questions_generated",
        "questions_validated",
        "questions_rejected",
    ):
        assert key in telemetry
    assert telemetry["extracted_text"] == "available"
    assert telemetry["quiz_requested"] == 8
    assert telemetry["questions_validated"] == 8
    assert telemetry["concepts_found"] > 0
    assert telemetry["quiz_plans_created"] >= 8


def test_every_rejection_records_a_reason() -> None:
    result = build(load_corpus("history-ww1.txt"), count=8)
    for note in result.rejections:
        assert note.stage
        assert note.reason.strip()


def test_the_funnel_is_logged(caplog) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger="app.services.quiz_pipeline"):
        build(load_pdf("cell-biology-ch3.pdf"), count=8)
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "PDF pages available" in logged
    assert "Questions validated" in logged
    assert "Quiz requested" in logged


# --------------------------------------------------------------------------- #
# Determinism must survive the new stages
# --------------------------------------------------------------------------- #


def test_the_same_seed_still_produces_the_same_quiz() -> None:
    a = build(load_pdf("physics-newtonian-mechanics.pdf"), count=8, seed=42)
    b = build(load_pdf("physics-newtonian-mechanics.pdf"), count=8, seed=42)
    assert [q.prompt for q in a.questions] == [q.prompt for q in b.questions]
    assert [q.correct_answer for q in a.questions] == [
        q.correct_answer for q in b.questions
    ]


# --------------------------------------------------------------------------- #
# API surface: a shortfall must reach the student as an explanation
# --------------------------------------------------------------------------- #


def test_a_material_shortfall_maps_to_422_not_a_generic_outage() -> None:
    """The student must learn it was the PDF, not the AI service.

    A 503 says "try again later", which is wrong and sends them in circles; a
    422 with the real reason tells them to select more pages or ask for fewer
    questions.
    """
    from app.api.ai import _as_http_exception

    exc = _as_http_exception(
        QuizMaterialError("not enough material", requested=8, available=2)
    )
    assert exc.status_code == 422
    assert "not enough material" in exc.detail


def test_a_real_outage_still_maps_to_503() -> None:
    from app.api.ai import _as_http_exception

    exc = _as_http_exception(AIUnavailableError("provider down"))
    assert exc.status_code == 503
