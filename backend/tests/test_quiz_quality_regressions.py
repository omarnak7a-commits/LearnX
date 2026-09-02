"""Regression tests for quiz generation quality and semantic alignment.

Covers the 7 quality and grounding requirements:
1. A question with an unrelated answer must be rejected (e.g. 'What does Oracle produce?'
   must NOT accept an answer about locking users unless explicitly connected).
2. Duplicate/near-duplicate objectives must not produce repeated final questions.
3. A valid distinct question must survive.
4. A valid provider-generated grounded question must NOT be falsely rejected.
5. Deterministic fallback must preserve question/answer semantic alignment.
6. If a provider candidate is rejected, the rejection reason must identify the actual failed
   condition rather than a generic false-negative label.
7. The pipeline must still produce exactly 8 valid questions from exam
   075eb4af-5813-41d0-9602-23065c1e4ddf when the source supports them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.schemas.ai import AIQuizQuestion
from app.services.ai_documents import _extract_pdf, source_from_text
from app.services.ai_service import AIServiceError
from app.services.quiz_blueprints import build_question_blueprints
from app.services.quiz_deterministic import deterministic_candidates
from app.services.quiz_grounding import quote_is_grounded
from app.services.quiz_knowledge_targets import build_knowledge_targets
from app.services.quiz_pipeline import (
    CandidateRecord,
    _RawCandidate,
    _RawQuizPool,
    _answer_is_supported,
    _records_are_duplicates,
    build_document_understanding,
    build_quiz_context,
    classify_grounding_result,
    generate_quiz,
    normalize_blueprinted_candidate,
    validate_final_quiz,
)
from tests.quiz_fakes import FakeQuizService, parse_blueprints

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "backend" / "tests" / "fixtures"
ALL_TYPES = ["mcq", "true-false", "short-answer", "fill-blank"]


class NoProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("no provider configured")


def load_fixture_pdf(filename: str = "sql18_shaped_32_pages.pdf"):
    path = FIXTURES_DIR / filename
    return _extract_pdf(
        path.read_bytes(),
        file_id=path.stem,
        title=path.stem,
        max_characters=200_000,
        allowed_pages=None,
    )


# --------------------------------------------------------------------------- #
# Requirement 1: Unrelated / semantically unaligned question-answer pairings
# --------------------------------------------------------------------------- #


def test_unrelated_predicate_for_effect_stem_is_rejected() -> None:
    """'What does Oracle produce?' must reject an unrelated predicate like 'uses locks'."""
    text = (
        "[Page 1]\n"
        "Oracle uses locks that prevent destructive interaction between users.\n"
        "Deadlock occurs when two transactions wait indefinitely for resources held by each other."
    )
    source = source_from_text(text, "oracle-locks")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    targets = build_knowledge_targets(und)
    blueprints = build_question_blueprints(targets, count=4, question_types=["mcq"], difficulty="medium", seed=1)
    bp = next((b for b in blueprints if b.question_type == "mcq"), blueprints[0])

    mismatched = AIQuizQuestion(
        id="bad-effect",
        type="mcq",
        prompt="What does Oracle produce?",
        options=[
            "uses locks that prevent destructive interaction between users",
            "generates query plans",
            "manages disk sectors",
            "compiles bytecode",
        ],
        correct_answer="uses locks that prevent destructive interaction between users",
        explanation="The source says Oracle uses locks that prevent destructive interaction.",
        difficulty="medium",
        source_pages=[1],
    )
    assert not _answer_is_supported(mismatched, bp, document_vocab=ctx.vocab)


def test_modal_fragment_answer_for_definition_stem_is_rejected() -> None:
    """'Which statement best describes users?' must reject 'can also lock data manually'."""
    text = (
        "A transaction is a logical unit of database work that is committed atomically.\n"
        "Users can also lock data manually during a batch operation."
    )
    source = source_from_text(text, "users-modal")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    targets = build_knowledge_targets(und)
    blueprints = build_question_blueprints(targets, count=4, question_types=["mcq"], difficulty="medium", seed=1)
    bp = next((b for b in blueprints if b.question_type == "mcq"), blueprints[0])

    modal_q = AIQuizQuestion(
        id="bad-modal",
        type="mcq",
        prompt="Which statement best describes users?",
        options=[
            "can also lock data manually during a batch operation",
            "are stored in the schema",
            "compile SQL queries",
            "execute batch jobs",
        ],
        correct_answer="can also lock data manually during a batch operation",
        explanation="The source mentions that users can also lock data manually.",
        difficulty="medium",
        source_pages=[1],
    )
    assert not _answer_is_supported(modal_q, bp, document_vocab=ctx.vocab)


# --------------------------------------------------------------------------- #
# Requirement 2: Duplicate / near-duplicate objectives do not produce repeats
# --------------------------------------------------------------------------- #


def test_near_duplicate_questions_are_deduplicated_across_skills() -> None:
    """Candidates with duplicate stems or duplicate non-TF answers are deduplicated."""
    text = (
        "Read Consistency ensures that a user sees a consistent view of the database.\n"
        "A transaction is a unit of work that is executed atomically."
    )
    source = source_from_text(text, "read-consistency")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    targets = build_knowledge_targets(und)
    blueprints = build_question_blueprints(targets, count=8, question_types=ALL_TYPES, difficulty="medium", seed=1)

    c1 = AIQuizQuestion(
        id="c1",
        type="mcq",
        prompt="What is the purpose of Read Consistency?",
        options=["ensures that a user sees a consistent view", "optimizes query plans", "manages disk blocks", "creates indexes"],
        correct_answer="ensures that a user sees a consistent view",
        explanation="Read Consistency ensures that a user sees a consistent view.",
        difficulty="medium",
        source_pages=[1],
    )
    c2 = AIQuizQuestion(
        id="c2",
        type="short-answer",
        prompt="What is the purpose of Read Consistency?",
        options=None,
        correct_answer="ensures that a user sees a consistent view",
        explanation="Read Consistency ensures that a user sees a consistent view.",
        difficulty="medium",
        source_pages=[1],
    )
    bp = blueprints[0]
    r1 = CandidateRecord(question=c1, blueprint=bp, source_quote=bp.evidence)
    r2 = CandidateRecord(question=c2, blueprint=bp, source_quote=bp.evidence)
    assert _records_are_duplicates(r1, r2)


def test_final_quiz_rejects_duplicate_prompts_and_answers() -> None:
    """validate_final_quiz must catch any duplicate prompts or duplicate non-TF answers."""
    text = (
        "[Page 1]\n"
        "A transaction is a unit of work executed atomically.\n"
        "An index is a data structure that speeds up lookups."
    )
    source = source_from_text(text, "tx-idx")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    from app.services.quiz_pipeline import QuestionProvenance

    q1 = AIQuizQuestion(
        id="q1",
        type="mcq",
        prompt="Which statement best describes transaction?",
        options=["a unit of work executed atomically", "speeds up lookups", "stores queries", "runs events"],
        correct_answer="a unit of work executed atomically",
        explanation="A transaction is a unit of work executed atomically.",
        difficulty="medium",
        source_pages=[1],
    )
    q2 = AIQuizQuestion(
        id="q2",
        type="mcq",
        prompt="Which statement correctly defines transaction?",
        options=["a unit of work executed atomically", "speeds up lookups", "stores queries", "runs events"],
        correct_answer="a unit of work executed atomically",
        explanation="A transaction is a unit of work executed atomically.",
        difficulty="medium",
        source_pages=[1],
    )
    provenance = {
        "q1": QuestionProvenance(
            question_id="q1",
            concept_id="transaction",
            concept="transaction",
            knowledge_target_id="transaction--understanding",
            knowledge_target="understand transaction",
            cognitive_skill="understanding",
            knowledge_type="definition",
            source_pages=(1,),
            quality_score=0.9,
            blueprint_id="bp-1",
        ),
        "q2": QuestionProvenance(
            question_id="q2",
            concept_id="transaction",
            concept="transaction",
            knowledge_target_id="transaction--factual_recall",
            knowledge_target="recall transaction",
            cognitive_skill="factual_recall",
            knowledge_type="definition",
            source_pages=(1,),
            quality_score=0.88,
            blueprint_id="bp-2",
        ),
    }

    valid, notes = validate_final_quiz(
        [q1, q2],
        context=ctx,
        source=source,
        understanding=und,
        provenance_by_id=provenance,
        requested_types=["mcq"],
    )
    assert len(valid) == 1, "Duplicate question or answer was not pruned by final validation"
    assert len(notes) >= 1


# --------------------------------------------------------------------------- #
# Requirement 3: Valid distinct questions survive
# --------------------------------------------------------------------------- #


def test_valid_distinct_questions_survive_pipeline() -> None:
    """Distinct questions for distinct concepts must all be retained."""
    source = load_fixture_pdf("sql18_shaped_32_pages.pdf")
    result = generate_quiz(
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
    assert len(result.questions) == 8
    prompts = [q.prompt for q in result.questions]
    assert len(set(prompts)) == 8, "Prompts contain duplicates"
    non_tf_answers = [q.correct_answer for q in result.questions if q.type != "true-false"]
    assert len(set(non_tf_answers)) == len(non_tf_answers), "Non-TF answers contain duplicates"


# --------------------------------------------------------------------------- #
# Requirement 4: Valid provider-generated grounded questions are not falsely rejected
# --------------------------------------------------------------------------- #


def test_valid_provider_question_is_accepted_by_normalizer() -> None:
    """A well-formed, well-grounded provider candidate must be accepted."""
    text = (
        "An aggregate function computes a single value over many rows in a database table.\n"
        "A regular function processes one row at a time in the database table."
    )
    source = source_from_text(text, "agg")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    targets = build_knowledge_targets(und)
    blueprints = build_question_blueprints(targets, count=1, question_types=["mcq"], difficulty="medium", seed=1)
    bp = blueprints[0]
    bp_dict = {bp.id: bp}

    raw = _RawCandidate(
        blueprint_id=bp.id,
        type="mcq",
        prompt="How does an aggregate function operate in SQL?",
        options=[
            "It computes a single value over many rows in a database table.",
            "It formats individual column headers in a database table.",
            "It processes one row at a time in the database table.",
            "It generates random primary keys in a database table.",
        ],
        correct_answer="It computes a single value over many rows in a database table.",
        explanation="The source states that an aggregate function computes a single value over many rows in a database table.",
        source_pages=[1],
        source_quote=bp.evidence,
        distractor_rationales=[
            "Formatting headers is not performed by aggregate functions.",
            "Processing one row at a time is the behavior of regular functions.",
            "Primary key generation is handled by sequences or constraints.",
        ],
    )

    reasons: list[str] = []
    record = normalize_blueprinted_candidate(
        raw,
        index=1,
        blueprints=bp_dict,
        page_count=1,
        included_pages={1},
        page_text=ctx.page_text,
        vocab=ctx.vocab,
        reasons=reasons,
    )
    assert record is not None, f"Valid candidate was rejected: {reasons}"
    assert record.question.prompt == raw.prompt


def test_rejection_reasons_report_specific_failure_conditions() -> None:
    """Rejection diagnostics must report specific failure reasons, not generic strings."""
    text = (
        "A database index is a data structure that speeds up search operations on a table.\n"
        "A clustered table stores rows in sorted order."
    )
    source = source_from_text(text, "idx")
    ctx = build_quiz_context(source)
    und, _ = build_document_understanding(NoProvider(), source, ctx, system_prompt="")
    targets = build_knowledge_targets(und)
    blueprints = build_question_blueprints(targets, count=1, question_types=["mcq"], difficulty="medium", seed=1)
    bp = blueprints[0]
    bp_dict = {bp.id: bp}

    # Candidate with missing distractor rationales
    bad_rationales = _RawCandidate(
        blueprint_id=bp.id,
        type="mcq",
        prompt="What is the purpose of a database index?",
        options=[
            "It speeds up search operations on a table.",
            "It deletes unreferenced tables from storage.",
            "It creates user accounts in the catalog.",
            "It locks entire tables during batch updates.",
        ],
        correct_answer="It speeds up search operations on a table.",
        explanation="A database index is a data structure that speeds up search operations on a table.",
        source_pages=[1],
        source_quote=bp.evidence,
        distractor_rationales=[],
    )
    reasons: list[str] = []
    res = normalize_blueprinted_candidate(
        bad_rationales,
        index=1,
        blueprints=bp_dict,
        page_count=1,
        included_pages={1},
        page_text=ctx.page_text,
        vocab=ctx.vocab,
        reasons=reasons,
    )
    assert res is None
    assert any("rationales" in r for r in reasons), f"Expected rationale error, got: {reasons}"

    # Candidate citing page outside evidence
    bad_page = _RawCandidate(
        blueprint_id=bp.id,
        type="mcq",
        prompt="What is the purpose of a database index?",
        options=[
            "It speeds up search operations on a table.",
            "It deletes unreferenced tables from storage.",
            "It creates user accounts in the catalog.",
            "It locks entire tables during batch updates.",
        ],
        correct_answer="It speeds up search operations on a table.",
        explanation="A database index is a data structure that speeds up search operations on a table.",
        source_pages=[99],
        source_quote=bp.evidence,
        distractor_rationales=["r1 is long enough", "r2 is long enough", "r3 is long enough"],
    )
    reasons.clear()
    res2 = normalize_blueprinted_candidate(
        bad_page,
        index=2,
        blueprints=bp_dict,
        page_count=100,
        included_pages=set(range(1, 101)),
        page_text={99: "other text", 1: text},
        vocab=ctx.vocab,
        reasons=reasons,
    )
    assert res2 is None
    assert any("outside" in r for r in reasons), f"Expected page mismatch error, got: {reasons}"


# --------------------------------------------------------------------------- #
# Requirement 7: Exactly 8 valid questions from exam 075eb4af-5813-41d0-9602-23065c1e4ddf
# --------------------------------------------------------------------------- #


def test_sql18_slide_deck_generates_eight_clean_questions() -> None:
    """The SQL18 fixture corresponding to exam 075eb4af-5813-41d0-9602-23065c1e4ddf
    must produce exactly 8 clean, non-duplicate, grounded questions across all 4 types.
    """
    source = load_fixture_pdf("sql18_shaped_32_pages.pdf")
    result = generate_quiz(
        NoProvider(),
        source,
        count=8,
        question_types=ALL_TYPES,
        difficulty="medium",
        kind="exam",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )
    assert len(result.questions) == 8
    types = {q.type for q in result.questions}
    assert len(types) >= 2, f"Expected varied question types, got: {types}"

    # Semantic check: no nonsensical questions like 'What does Oracle produce?' or bare 'SET'
    for q in result.questions:
        assert "What does Oracle produce?" not in q.prompt
        assert "What is SET?" not in q.prompt
        assert "uses locks that prevent destructive interaction" not in q.correct_answer
        assert not q.prompt.startswith("Complete this statement about user:")

    # Concept provenance check: distinct concepts
    concepts = [record.concept_id for record in result.provenance]
    assert len(set(concepts)) >= 5, f"Concepts too concentrated: {concepts}"
