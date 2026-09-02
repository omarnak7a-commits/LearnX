"""Regression coverage for deterministic fallback writing from PDF evidence."""

from __future__ import annotations

import re

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import app
from app.services import storage as storage_service
from app.services.ai_documents import clear_extraction_cache, source_from_text, _extract_pdf_uncached
from app.services.ai_service import AIServiceError, AIStructuredCompletion
from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_deterministic import (
    _distractors,
    deterministic_candidates,
    replan_unsafe_mcq_blueprints,
)
from app.services.quiz_pipeline import (
    QuizMaterialError,
    _RawCandidate,
    _RawQuizPool,
    build_quiz_context,
    generate_quiz,
    normalize_blueprinted_candidate,
)
from app.services.quiz_understanding import DocumentUnderstanding, deterministic_understanding

import app.api.ai as ai_api


ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]
FILE_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
SQL18_FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"


class NoProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("provider unavailable")


class EmptyWriterProvider:
    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawQuizPool:
            return AIStructuredCompletion(
                value=_RawQuizPool(questions=[]),
                provider="gemini",
                model="fake",
                fallback_used=False,
            )
        raise AIServiceError("understanding unavailable")


class FailingProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("provider unavailable")


def _understanding(text: str) -> DocumentUnderstanding:
    source = source_from_text(text, title="Document")
    context = build_quiz_context(source)
    return deterministic_understanding(context.units, title="Document")


def _blueprint(
    *,
    concept_id: str,
    concept: str,
    evidence: str,
    question_type: str = "short-answer",
    skill: str = "understanding",
    facet_kind: str = "",
    answer_clause: str = "",
) -> QuestionBlueprint:
    return QuestionBlueprint(
        id=f"bp-{concept_id}-{question_type}",
        concept_id=concept_id,
        concept=concept,
        knowledge_target_id=f"{concept_id}--{skill}",
        knowledge_target=f"understand {concept}",
        knowledge_type="definition",
        cognitive_skill=skill,
        question_type=question_type,
        difficulty="medium",
        importance=1.0,
        evidence=evidence,
        pages=(1,),
        topic="",
        facet_kind=facet_kind,
        answer_clause=answer_clause,
    )


def test_no_answer_claim_uses_clear_explanatory_evidence_sentence() -> None:
    understanding = _understanding(
        "A transaction is a unit of work executed atomically.\n"
        "Atomicity ensures that a transaction is treated as a single unit."
    )
    blueprint = _blueprint(
        concept_id="transaction",
        concept="transaction",
        evidence="A transaction is a unit of work executed atomically.",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1
    assert written[0]["prompt"] == "What is transaction?"
    assert written[0]["correct_answer"] == "a unit of work executed atomically"
    assert written[0]["correct_answer"] in blueprint.evidence


def test_no_facet_strong_evidence_still_writes_grounded_question() -> None:
    understanding = _understanding(
        "Atomicity ensures that a transaction is treated as a single unit.\n"
        "Consistency ensures that committed data satisfies constraints."
    )
    blueprint = _blueprint(
        concept_id="atomicity",
        concept="Atomicity",
        evidence="Atomicity ensures that a transaction is treated as a single unit.",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1
    assert written[0]["prompt"] == "What is Atomicity?"
    assert written[0]["correct_answer"] == (
        "ensures that a transaction is treated as a single unit"
    )


def test_insufficient_mcq_distractors_replans_to_selected_safe_type() -> None:
    understanding = _understanding(
        "A primary key uniquely identifies each row in a table.\n"
        "A foreign key references a primary key in another table."
    )
    mcq = _blueprint(
        concept_id="primary-key",
        concept="primary key",
        evidence="A primary key uniquely identifies each row in a table.",
        question_type="mcq",
    )

    replanned = replan_unsafe_mcq_blueprints(
        [mcq],
        selected_question_types=["mcq", "short-answer"],
        understanding=understanding,
    )
    written = deterministic_candidates(replanned, language="en", understanding=understanding)

    assert [plan.question_type for plan in replanned] == ["short-answer"]
    assert len(written) == 1
    assert written[0]["type"] == "short-answer"
    assert written[0]["correct_answer"] == "uniquely identifies each row in a table"


def test_mcq_only_shortage_is_truthful_skip_not_weak_mcq() -> None:
    understanding = _understanding(
        "A primary key uniquely identifies each row in a table.\n"
        "A foreign key references a primary key in another table."
    )
    mcq = _blueprint(
        concept_id="primary-key",
        concept="primary key",
        evidence="A primary key uniquely identifies each row in a table.",
        question_type="mcq",
    )

    replanned = replan_unsafe_mcq_blueprints(
        [mcq], selected_question_types=["mcq"], understanding=understanding
    )
    drops: dict[str, int] = {}
    written = deterministic_candidates(
        replanned, language="en", understanding=understanding, drop_reasons=drops
    )

    assert [plan.question_type for plan in replanned] == ["mcq"]
    assert written == []
    assert drops == {"too_few_distractors": 1}


def _sql18_source():
    clear_extraction_cache()
    return _extract_pdf_uncached(
        SQL18_FIXTURE.read_bytes(),
        file_id="sql18-shaped",
        title="SQL18",
        max_characters=100_000,
        allowed_pages=None,
    )


def _provider_returning(question_count: int):
    class Provider(NoProvider):
        def complete_structured(self, **kwargs):
            if kwargs["response_model"] is _RawQuizPool:
                questions = []
                for index in range(question_count):
                    bp = f"bp-{index + 1}"
                    questions.append(
                        {
                            "blueprint_id": bp,
                            "type": "short-answer",
                            "prompt": f"What is Concept {index + 1}?",
                            "correct_answer": f"a mechanism that produces grounded outcome {index + 1} for learners",
                            "options": None,
                            "explanation": f"Concept {index + 1} is a mechanism that produces grounded outcome {index + 1} for learners.",
                            "source_pages": [1],
                            "source_quote": f"Concept {index + 1} is a mechanism that produces grounded outcome {index + 1} for learners.",
                        }
                    )
                return AIStructuredCompletion(
                    value=_RawQuizPool.model_validate({"questions": questions}),
                    provider="gemini",
                    model="fake",
                    fallback_used=False,
                )
            raise AIServiceError("force deterministic understanding")

    return Provider()


def test_provider_writer_returns_zero_deterministic_fallback_reaches_8() -> None:
    result = generate_quiz(
        EmptyWriterProvider(),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


# Provider candidates here intentionally do not need to survive; the regression
# is that deterministic top-up still fills the exact requested count.

def test_provider_writer_returns_two_deterministic_topup_reaches_8() -> None:
    result = generate_quiz(
        _provider_returning(2),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=3,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


def test_provider_writer_returns_five_deterministic_topup_reaches_8() -> None:
    result = generate_quiz(
        _provider_returning(5),
        _sql18_source(),
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=5,
        previous_questions=[],
        system_prompt="Use only the source.",
    )
    assert len(result.questions) == 8
    assert result.telemetry["questions_validated"] == 8


def test_provider_succeeds_with_at_least_8_no_unnecessary_fallback(monkeypatch) -> None:
    from app.schemas.ai import AIQuizQuestion
    from app.services.quiz_blueprints import semantic_objective_key
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_pipeline import _top_up_candidates, build_quiz_context
    from app.services.quiz_scoring import ScoredCandidate
    import app.services.quiz_pipeline as pipeline

    source = _sql18_source()
    context = build_quiz_context(source)
    understanding = deterministic_understanding(context.units, title="SQL18")
    context.understanding = understanding
    context.knowledge_targets = build_knowledge_targets(understanding)

    blueprint_by_id = {}
    scored = []
    for index, concept in enumerate(understanding.important_concepts(), start=1):
        blueprint = _blueprint(
            concept_id=concept.concept_id,
            concept=concept.name,
            evidence=concept.primary_evidence,
        )
        blueprint = replace(blueprint, id=f"provider-bp-{index}")
        blueprint_by_id[blueprint.id] = blueprint
        question = AIQuizQuestion(
            id=f"provider-q-{index}",
            type="short-answer",
            prompt=f"What is {concept.name}?",
            correctAnswer="directly supported by the cited evidence",
            explanation=concept.primary_evidence,
            difficulty="medium",
            sourcePages=list(concept.source_pages[:1] or [1]),
        )
        scored.append(
            ScoredCandidate(
                question=question,
                score=0.9,
                concept=concept.concept_id,
                skill="understanding",
                pattern="provider",
                objective_key=semantic_objective_key(
                    concept.concept_id, blueprint.knowledge_target_id, "understanding"
                ),
                blueprint_id=blueprint.id,
            )
        )

    def _should_not_write(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("deterministic top-up ran despite a full provider pool")

    monkeypatch.setattr(pipeline, "deterministic_candidates", _should_not_write)
    funnel = {"topup_rounds": [], "deterministic_drop_reasons": {}, "plans_skipped_reason": {}}
    provider_trace = {}

    topped_up, _ = _top_up_candidates(
        scored,
        {},
        context=context,
        source=source,
        understanding=understanding,
        blueprint_by_id=blueprint_by_id,
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        language="en",
        seed=1,
        previous_questions=[],
        quality_threshold=0.68,
        rejections=[],
        provider_trace=provider_trace,
        funnel=funnel,
    )

    assert topped_up == scored
    assert provider_trace == {}
    assert funnel["topup_rounds"] == [{"round": 1, "stop_reason": "pool_sufficient"}]

def test_genuine_content_shortage_truthful_422_path() -> None:
    source = source_from_text(
        "A checksum is a value computed from a block of data.",
        title="Thin",
    )
    try:
        generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=ALL_TYPES,
            difficulty="medium",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the source.",
        )
    except Exception as exc:
        assert exc.__class__.__name__ in {"QuizMaterialError", "AIUnavailableError"}
    else:  # pragma: no cover - this is the forbidden outcome
        raise AssertionError("thin source unexpectedly produced eight questions")


def test_no_duplicate_questions_and_exact_supported_counts() -> None:
    source = _sql18_source()
    for count in (3, 5, 8, 12):
        result = generate_quiz(
            NoProvider(),
            source,
            count=count,
            question_types=ALL_TYPES,
            difficulty="medium",
            kind="exam",
            language="en",
            seed=count,
            previous_questions=[],
            system_prompt="Use only the source.",
        )
        prompts = [question.prompt for question in result.questions]
        assert len(result.questions) == count
        assert len(set(prompts)) == len(prompts)


def test_sql18_shaped_fixture_provider_failures_reaches_8_over_http() -> None:
    clear_extraction_cache()
    pdf = SQL18_FIXTURE.read_bytes()
    record = SimpleNamespace(
        id=FILE_ID,
        owner_id=OWNER_ID,
        name="SQL18.pdf",
        size_bytes=len(pdf),
        mime_type="application/pdf",
        storage_key=f"users/{OWNER_ID}/vault/SQL18.pdf",
        analysis=None,
    )

    class FakeSession:
        def get(self, _model, file_id):
            return record if str(file_id) == FILE_ID else None

        def scalar(self, _stmt):
            return record

        def close(self):
            pass

    def _db():
        db = FakeSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER_ID)
    app.dependency_overrides[ai_api.get_ai_service] = lambda: FailingProvider()
    original_download = storage_service.download_user_object
    storage_service.download_user_object = lambda *_a, **_k: pdf
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/quiz",
                json={
                    "fileId": FILE_ID,
                    "count": 8,
                    "kind": "exam",
                    "scope": "document",
                    "diagnostics": True,
                },
            )
    finally:
        storage_service.download_user_object = original_download
        app.dependency_overrides = {}
        clear_extraction_cache()

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["questions"]) == 8
    diagnostics = body["diagnostics"]
    assert diagnostics["accepted"] == 8
    assert diagnostics["grounding_rejected"] == 0
    assert diagnostics["provider_calls"]["understanding_failed"] == 1
    assert diagnostics["provider_calls"]["writer_failed"] == 1


# --------------------------------------------------------------------------- #
# Production incident 075eb4af…: deterministic fallback returned 6 of 8.
#
# The provider failed completely (provider_errors=2, zero candidates) and the
# deterministic writer planned 8 slots for this document but could not fill 2
# of them: the misconception true/false for each "X is responsible for Y"
# concept framed a base statement that was verbatim-equal to its evidence, and
# `_true_statement` refused it — so the plan carried two slots the writer had
# to drop, no fresh objective remained for the top-up, and the 8-question
# request came back as a truthful-but-wrong 422 (6 available).
#
# Before the fix this exact document returned HTTP 422 with available=6:
#   attempted=10, returned=6, dropped=4 (all false_statement_not_constructible)
#   plans_created=8, plans_skipped=20 (unsupported_skill:application=6,
#   duplicate_objective=14), provider_errors=2 — the production funnel shape.
# After the fix the same document returns 8/8 with dropped=0.
# --------------------------------------------------------------------------- #
RECOVERY_FIXTURE = (
    "The query optimizer is responsible for choosing the cheapest execution plan.\n"
    "The buffer pool is responsible for caching frequently accessed pages."
)


def test_provider_down_deterministic_recovers_to_full_quiz() -> None:
    """The production-shaped document now yields 8/8 with zero writer drops."""
    result = generate_quiz(
        NoProvider(),
        source_from_text(RECOVERY_FIXTURE, title="SQL18 recovery fixture"),
        count=8,
        question_types=list(ALL_TYPES),
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )

    assert len(result.questions) == 8
    # The two misconception true/false questions are now written (2 true-false
    # in the final set); before the fix they were the false_statement drops.
    assert [q.type for q in result.questions].count("true-false") == 2

    telemetry = result.telemetry
    assert telemetry["deterministic_candidates_dropped"] == 0
    assert telemetry["deterministic_candidates_attempted"] == (
        telemetry["deterministic_candidates_returned"]
        + telemetry["deterministic_candidates_dropped"]
    )
    assert telemetry["deterministic_candidates_returned"] >= 8
    assert telemetry["deterministic_drop_reasons"] == {}
    assert telemetry["provider_errors"] == 2


def test_sql18_shape_provider_down_deterministic_uses_every_plan() -> None:
    """The 32-page SQL18-shaped fixture keeps 8/8 and wastes no planned slot."""
    result = generate_quiz(
        NoProvider(),
        _sql18_source(),
        count=8,
        question_types=list(ALL_TYPES),
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )

    assert len(result.questions) == 8
    telemetry = result.telemetry
    # Before the fix this fixture attempted 15 blueprints and dropped 4
    # (false_statement_not_constructible). The writer-backed veto plans only
    # constructible slots, so every attempt now returns a candidate.
    assert telemetry["deterministic_candidates_dropped"] == 0
    assert telemetry["deterministic_candidates_attempted"] == (
        telemetry["deterministic_candidates_returned"]
        + telemetry["deterministic_candidates_dropped"]
    )
    assert telemetry["deterministic_candidates_returned"] >= 8
    assert telemetry["plans_created"] == 16


def test_misconception_swaps_verbatim_frame_into_a_different_false_claim() -> None:
    """The recovery is a swap, never a reprinted-true statement.

    ``_true_statement`` still refuses the verbatim base for a *true* question
    (the answer would be read off the evidence); only the misconception
    writer may request it, because it immediately replaces the concept with a
    different taught concept, producing a genuinely different, false claim
    that still passes the meaningful-true/false gate downstream.
    """
    from app.services.quiz_deterministic import (
        _blueprint_for_target,
        _false_statement,
        _true_statement,
    )

    understanding = _understanding(RECOVERY_FIXTURE)
    from app.services.quiz_knowledge_targets import build_knowledge_targets

    targets = build_knowledge_targets(understanding)
    misconception = next(
        target
        for target in targets
        if target.cognitive_skill == "misconception" and target.concept_id == "buffer-pool"
    )
    blueprint = _blueprint_for_target(misconception, "true-false")

    # The true path must still refuse a statement that reprints the evidence.
    assert _true_statement(blueprint) is None
    assert _true_statement(blueprint, allow_verbatim=True) == (
        "The buffer pool is responsible for caching frequently accessed pages."
    )

    statement, basis, decoy = _false_statement(blueprint, understanding)
    assert statement == (
        "The query optimizer is responsible for caching frequently accessed pages."
    )
    assert basis == "The buffer pool is responsible for caching frequently accessed pages."
    assert decoy == "query optimizer"
    assert statement != "The buffer pool is responsible for caching frequently accessed pages."


def test_writer_veto_excludes_slots_the_writer_cannot_construct() -> None:
    """The planner veto removes contentless/2-word-clause targets up front.

    These targets pass the old syntactic veto (so the planner committed slots
    for them) but fail the writer's own construction rules; the new veto runs
    the writer's decision procedure, so no planned slot is silently lost and
    the quiz is exactly as long as the document genuinely supports.
    """
    # One solid concept plus one contentless claim ("exists in two forms")
    # and one two-word purpose clause ("responsible for speed").
    text = (
        "The query optimizer is responsible for choosing the cheapest execution plan.\n"
        "The database index exists in two forms.\n"
        "The lock manager is responsible for speed."
    )
    source = source_from_text(text, title="mixed support")
    try:
        result = generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=list(ALL_TYPES),
            difficulty="medium",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the supplied source.",
        )
        telemetry = result.telemetry
    except QuizMaterialError as exc:
        telemetry = exc.telemetry
        assert exc.available < 8  # the document genuinely supports fewer

    # Every planned slot produced a candidate: the unconstructible targets
    # were vetoed at planning time instead of being dropped mid-run.
    assert telemetry["deterministic_candidates_dropped"] == 0
    assert telemetry["deterministic_candidates_attempted"] == (
        telemetry["deterministic_candidates_returned"]
        + telemetry["deterministic_candidates_dropped"]
    )
    # The veto is observable in the plan accounting: the contentless and
    # two-word-clause targets are excluded as unconstructible.
    assert (
        telemetry["plans_skipped_reason"].get("all_types_vetoed_by_writer", 0) >= 1
    )


def test_genuinely_thin_document_still_422s_after_recovery() -> None:
    """A document that truly supports fewer than 8 questions still fails honestly."""
    thin = (
        "A primary key uniquely identifies each row in a table.\n"
        "A foreign key references the primary key of another table.\n"
        "Normalization organizes columns to reduce duplicate data."
    )
    source = source_from_text(thin, title="Thin")
    try:
        generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=list(ALL_TYPES),
            difficulty="medium",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the supplied source.",
        )
        raise AssertionError("expected a QuizMaterialError for a 3-sentence document")
    except QuizMaterialError as exc:
        assert exc.available < 8
        assert exc.available >= 1
        assert exc.telemetry["deterministic_candidates_dropped"] == 0


def test_fill_blank_is_built_from_one_bullet_not_fused_fragments() -> None:
    """A punctless bullet run must not become a two-rule fill-blank prompt.

    Slide text extraction fuses consecutive bullets into one line ("NOT NULL
    A column must always contain a value UNIQUE No two rows may have …").
    Blanking inside such a line previously produced a prompt that stitched two
    unrelated constraints together and an "answer" ("UNIQUE No") spanning a
    bullet boundary. The writer must blank inside the first self-contained
    statement only.
    """
    understanding = _understanding(
        "Integrity rules keep the stored data correct.\n"
        "Indexes speed up reads by keeping a sorted copy of the column values."
    )
    blueprint = _blueprint(
        concept_id="notnull",
        concept="NOT NULL",
        evidence=(
            "NOT NULL A column must always contain a value UNIQUE No two rows "
            "may have the same value in a column"
        ),
        question_type="fill-blank",
        skill="factual_recall",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1, "a blankable first bullet should still produce a fill-blank"
    prompt = written[0]["prompt"]
    answer = written[0]["correct_answer"]
    assert prompt.count("_____") == 1
    # The second fused bullet must be gone from both the prompt and the answer.
    assert "UNIQUE" not in prompt
    assert "No two rows" not in prompt
    assert "UNIQUE" not in answer
    words = answer.split()
    if len(words) > 1:
        assert words[1].lower() not in {
            "no", "not", "each", "every", "all", "any", "some", "both", "a",
            "an", "the", "its", "their", "this", "these", "those", "it",
            "when", "if", "while", "as", "by", "or", "and", "but", "after",
            "before",
        }, f"answer still spans a bullet boundary: {answer!r}"
    # The kept statement is the document's own first bullet, verbatim.
    assert prompt.startswith("Complete this statement about NOT NULL:")
    assert prompt.endswith("must always contain a value.")


def test_true_false_never_asserts_an_interrogative_clause() -> None:
    """An object wh-clause ("how concurrent transactions see each other")
    cannot follow an assertion frame: "X results in how …" is a fragment, and
    asserting it as a true/false claim tests nothing. The writer must decline
    the statement instead of shipping the broken sentence.
    """
    understanding = _understanding(
        "Isolation determines how concurrent transactions see each other.\n"
        "Durability keeps committed changes even after a failure."
    )
    blueprint = _blueprint(
        concept_id="isolation",
        concept="Isolation",
        evidence="Isolation determines how concurrent transactions see each other.",
        question_type="true-false",
        skill="cause_effect",
        facet_kind="effect",
        answer_clause="how concurrent transactions see each other",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    broken = re.compile(
        r"\b(?:results in|is responsible for|is caused by|works by means of|"
        r"depends on|divides into)\s+(?:how|what|why|whether|when|where|which)\b",
        re.IGNORECASE,
    )
    for candidate in written:
        assert not broken.search(candidate["prompt"]), (
            f"assertion frame swallowed an interrogative clause: "
            f"{candidate['prompt']!r}"
        )
    assert not any(
        "results in how" in candidate["prompt"] for candidate in written
    )


def test_true_statement_never_grafts_concept_onto_noun_phrase_clause() -> None:
    """A noun-phrase clause ("changes in the table data") is not a subjectless
    predicate. Framing it as one ("The trigger changes in the table data")
    invents a claim the document never states and keys it True. The cause
    facet's own frame ("is caused by …") must carry the relation instead.
    """
    understanding = _understanding(
        "A trigger runs due to changes in the table data.\n"
        "A stored procedure is program logic stored in the database."
    )
    blueprint = _blueprint(
        concept_id="trigger",
        concept="Trigger",
        evidence="A trigger runs due to changes in the table data.",
        question_type="true-false",
        skill="cause_effect",
        facet_kind="cause",
        answer_clause="changes in the table data",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert written, "a cause facet with a stated clause should write a true/false"
    for candidate in written:
        prompt = candidate["prompt"]
        # The bare-predicate graft would read as a plausible sentence while
        # asserting something the source never says.
        assert not re.match(
            r"^(?:The |A )?Trigger (?:changes|runs due)\b", prompt
        ), f"concept grafted onto a noun-phrase clause: {prompt!r}"
        assert "is caused by changes in the table data" in prompt, prompt
        assert candidate["correct_answer"] == "True"


def test_mcq_answer_that_is_raw_slide_code_is_rejected() -> None:
    """An answer led by a SQL operator or fusing two facts across "; " is
    slide code read as prose: grounded token-for-token, but unparseable as
    "the answer". The candidate must be declined so the pool refills.
    """
    evidence = (
        "WHERE sal > (SELECT AVG(sal) FROM emp); A correlated subquery "
        "references the outer query, so it runs once for every row the outer "
        "query returns."
    )
    text = (
        "A correlated subquery references the outer query.\n"
        "An index is a data structure that speeds up lookups.\n"
        + evidence
    )
    understanding = _understanding(text)
    source = source_from_text(text, title="Doc")
    context = build_quiz_context(source)
    blueprint = _blueprint(
        concept_id="where_sal",
        concept="WHERE sal",
        evidence=evidence,
        question_type="mcq",
        skill="process_order",
        facet_kind="mechanism",
        answer_clause="SELECT AVG(sal) FROM emp)",
    )
    fused_answer = (
        "> (SELECT AVG(sal) FROM emp); A correlated subquery references the "
        "outer query, so it runs once for every row the outer query returns"
    )
    raw = _RawCandidate(
        blueprint_id=blueprint.id,
        type="mcq",
        prompt="How does WHERE sal function?",
        options=[
            fused_answer,
            "a data structure that speeds up lookups",
            "a predicate that filters rows before grouping",
            "a named query stored in the schema",
        ],
        correct_answer=fused_answer,
        explanation=evidence,
        source_pages=[1],
        source_quote=evidence,
        distractor_rationales=[
            "describes an index, not this concept",
            "describes a filter clause, not this concept",
            "describes a view, not this concept",
        ],
    )
    reasons: list[str] = []
    record = normalize_blueprinted_candidate(
        raw,
        index=0,
        blueprints={blueprint.id: blueprint},
        page_count=1,
        included_pages={1},
        page_text=context.page_text,
        vocab=context.vocab,
        reasons=reasons,
    )
    assert record is None, "a code-fragment answer must not ship"
    assert any("code fragment" in reason for reason in reasons), reasons


def test_cause_question_without_a_stated_cause_is_declined() -> None:
    """A cause stem ("What causes X?") answered by what X *does* swaps the
    direction of the relation ("What causes Second normal form to form or
    act?" -> "removes partial dependencies…"). Without a stated cause in the
    evidence, the writer must decline instead of answering with an action.
    """
    understanding = _understanding(
        "Second normal form removes partial dependencies.\n"
        "Third normal form removes transitive dependencies."
    )
    blueprint = _blueprint(
        concept_id="secondnf",
        concept="Second normal form",
        evidence=(
            "Second normal form removes partial dependencies: every non-key "
            "attribute depends on the whole composite key, not on part of it."
        ),
        question_type="short-answer",
        skill="cause_effect",
        facet_kind="cause",
        answer_clause="",
    )

    drop_reasons: dict[str, int] = {}
    written = deterministic_candidates(
        [blueprint], language="en", understanding=understanding, drop_reasons=drop_reasons
    )

    assert written == [], "a cause question without a stated cause must not ship"
    assert drop_reasons.get("cause_effect_clause_unavailable") == 1, drop_reasons


def test_cause_question_is_answered_by_the_stated_cause() -> None:
    """With an empty facet clause, a cause question is answered from the
    evidence's own cause marker ("due to …"), never from a consequence
    clause, and the stem is the plain generic form.
    """
    understanding = _understanding(
        "The page cache stalls due to a full buffer pool.\n"
        "The query planner picks a scan when no index is usable."
    )
    blueprint = _blueprint(
        concept_id="pagecache",
        concept="page cache",
        evidence="The page cache stalls due to a full buffer pool.",
        question_type="short-answer",
        skill="cause_effect",
        facet_kind="cause",
        answer_clause="",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert len(written) == 1
    assert written[0]["prompt"] == "What causes the page cache?"
    assert "full buffer pool" in written[0]["correct_answer"]
    assert "stalls" not in written[0]["correct_answer"]


def test_true_false_declines_anaphor_led_and_colon_elaborated_clauses() -> None:
    """"another: whenever two rows agree on X they must agree on Y" borrows
    its subject from the surrounding sentence and carries an elaboration
    colon. Framed ("X results in another: …") it is a fragment; bare, it is
    unverifiable. The writer must decline rather than ship either form.
    """
    understanding = _understanding(
        "A functional dependency means one attribute determines another.\n"
        "A candidate key is a minimal set of attributes that uniquely identifies a row."
    )
    evidence = (
        "A functional dependency X -> Y means one attribute determines "
        "another: whenever two rows agree on X they must agree on Y."
    )
    blueprint = _blueprint(
        concept_id="fd",
        concept="Functional dependency",
        evidence=evidence,
        question_type="true-false",
        skill="cause_effect",
        facet_kind="effect",
        answer_clause="another: whenever two rows agree on X they must agree on Y",
    )

    written = deterministic_candidates([blueprint], language="en", understanding=understanding)

    assert not any(
        candidate.get("type") == "true-false" and "results in another" in candidate["prompt"]
        for candidate in written
    ), "the anaphor-led clause must never reach an assertion frame"
    for candidate in written:
        assert ": " not in candidate["prompt"].split("?")[0] or candidate.get("type") != "true-false"


def test_misconception_statement_is_one_tight_claim() -> None:
    """A swapped-subject false statement must not carry the base frame's
    trailing consequence ("…, so only the rows that satisfy the condition are
    returned to the user."): the compound sentence reads broken instead of
    merely false. The core misattribution is kept; the basis evidence is
    untouched.
    """
    understanding = _understanding(
        "The WHERE clause filters rows by a predicate, so only the rows that "
        "satisfy the condition are returned to the user.\n"
        "The buffer manager is responsible for caching frequently accessed "
        "pages in memory."
    )
    blueprint = _blueprint(
        concept_id="whereclause",
        concept="WHERE clause",
        evidence=(
            "The WHERE clause filters rows by a predicate, so only the rows "
            "that satisfy the condition are returned to the user."
        ),
        question_type="true-false",
        skill="misconception",
        facet_kind="mechanism",
        answer_clause=(
            "a predicate, so only the rows that satisfy the condition are "
            "returned to the user"
        ),
    )

    drop_reasons: dict[str, int] = {}
    written = deterministic_candidates(
        [blueprint], language="en", understanding=understanding, drop_reasons=drop_reasons
    )

    # The core-claim-only statement ("The buffer manager works by means of a
    # predicate.") no longer carries enough of the evidence's own wording to
    # clear the false-statement grounding floor, so the writer declines the
    # misconception entirely instead of shipping the compound broken sentence.
    # Either way, the trailing-consequence swap must never reach a quiz.
    for candidate in written:
        assert ", so " not in candidate["prompt"], candidate["prompt"]
        assert "so only the rows" not in candidate["prompt"], candidate["prompt"]
    assert drop_reasons.get("false_statement_not_constructible", 0) >= 1 or written == []


def test_mcq_answer_starting_with_an_anaphor_is_rejected() -> None:
    """"another: whenever …" as a correct answer borrows its subject from the
    surrounding sentence; standalone it is an unreadable fragment. The
    candidate gate must decline it like any other non-prose answer.
    """
    evidence = (
        "A functional dependency X -> Y means one attribute determines "
        "another: whenever two rows agree on X they must agree on Y."
    )
    text = "A functional dependency means one attribute determines another.\n" + evidence
    understanding = _understanding(text)
    source = source_from_text(text, title="Doc")
    context = build_quiz_context(source)
    blueprint = _blueprint(
        concept_id="fd",
        concept="Functional dependency",
        evidence=evidence,
        question_type="mcq",
        skill="cause_effect",
        facet_kind="effect",
        answer_clause="another: whenever two rows agree on X they must agree on Y",
    )
    raw = _RawCandidate(
        blueprint_id=blueprint.id,
        type="mcq",
        prompt="What is the primary result or effect of Functional dependency?",
        options=[
            "another: whenever two rows agree on X they must agree on Y",
            "a minimal set of attributes that uniquely identifies a row",
            "a predicate that filters rows before grouping",
            "a named query stored in the schema",
        ],
        correct_answer="another: whenever two rows agree on X they must agree on Y",
        explanation=evidence,
        source_pages=[1],
        source_quote=evidence,
        distractor_rationales=[
            "describes a candidate key, not this concept",
            "describes a filter clause, not this concept",
            "describes a view, not this concept",
        ],
    )
    reasons: list[str] = []
    record = normalize_blueprinted_candidate(
        raw,
        index=0,
        blueprints={blueprint.id: blueprint},
        page_count=1,
        included_pages={1},
        page_text=context.page_text,
        vocab=context.vocab,
        reasons=reasons,
    )
    assert record is None, "an anaphor-led answer must not ship"
    assert any("code fragment" in reason for reason in reasons), reasons


def test_mcq_distractors_exclude_unreadable_pool_claims() -> None:
    """Pool clauses that borrow a subject ("another: whenever …") or carry
    raw slide code must not become distractors: an option that is wrong on
    grammar rather than on knowledge teaches nothing.
    """
    understanding = _understanding(
        "A functional dependency means one attribute determines another.\n"
        "An index is a data structure that speeds up lookups.\n"
        "A view is a named query stored in the schema.\n"
        "A trigger executes automatically in response to a table event."
    )
    blueprint = _blueprint(
        concept_id="index",
        concept="index",
        evidence="An index is a data structure that speeds up lookups.",
        question_type="mcq",
        skill="understanding",
    )
    pool = [
        ("fd", "definition", "another: whenever two rows agree on X they must agree on Y"),
        ("view", "definition", "a named query stored in the schema"),
        ("trigger", "definition", "executes automatically in response to a table event"),
        ("tx", "definition", "a unit of work executed atomically"),
    ]

    chosen = _distractors(blueprint, "a data structure that speeds up lookups", pool)

    assert len(chosen) == 3, chosen
    options = " ".join(chosen)
    assert "another:" not in options
    assert ";" not in options
    # The readable pool claims are used instead.
    assert "a named query stored in the schema" in options
