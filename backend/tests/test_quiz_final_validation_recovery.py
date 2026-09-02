"""Regression tests: final-validation kills must be replaced, not strand the quiz.

Production incident (exam 075eb4af-5813-41d0-9602-23065c1e4ddf, "SQL18.pdf"):
the real 32-page deck is thin in the way that matters — 12 concepts share
~15 evidence sentences, so several concepts carry the SAME facet clause read
off the same page. Candidates for those concepts pass every objective gate
(different concepts, different prompts) and carry verbatim-identical correct
answers. Selection's ``claim_similarity`` preference is relaxable by design and
ships both; the PR that added the final duplicate-answer audit then rejected
one of the pair AFTER selection — the one stage with no replacement path — and
the quiz stranded short (production: "could only verify 1 of 8").

These tests pin the repaired contract:

1. a candidate whose correct answer duplicates another selected candidate is
   dropped BEFORE selection, recorded with the audit's own reason, and the slot
   is refilled from knowledge targets the quiz has not used — through the
   identical grounding and validation gates;
2. no duplicate correct answer ever ships;
3. a facet target whose clause is too short to stand alone is still written
   from the source's own claim (the removed ``_claim`` last resort), so the
   deterministic writer regains the yield the fallback-recovery design relies
   on; genuine stem/answer mismatches stay rejected;
4. a document that genuinely supports fewer than 8 distinct questions still
   fails honestly.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from app.services.ai_documents import source_from_text
from app.services.ai_service import AIServiceError
from app.services.quiz_blueprints import build_question_blueprints
from app.services.quiz_deterministic import (
    deterministic_candidates,
    replan_unsafe_mcq_blueprints,
    writer_writable_types,
)
from app.services.quiz_knowledge_targets import build_knowledge_targets
from app.services.quiz_pipeline import (
    _RawCandidate,
    _RawQuizPool,
    _collect_records,
    _dedupe_scored,
    _new_funnel,
    _preflight_and_refill_pool,
    _score_and_filter,
    build_candidate_prompt,
    build_document_understanding,
    build_quiz_context,
    generate_quiz,
    RejectionNote,
)
from app.services.quiz_quality_judge import _RawQualityJudgement
from app.services.quiz_understanding import _RawUnderstanding
from tests.quiz_fakes import FakeQuizService, parse_blueprints

ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]

#: A document in the incident shape: several clean one-concept sentences plus a
#: duplicated "X is responsible for Y" sentence under two concept names, whose
#: facet clauses are identical.
INCIDENT_SHAPE_TEXT = """[Page 1]
The buffer manager is responsible for caching frequently accessed pages in memory.
The query optimizer is responsible for choosing execution plans.
The log writer is responsible for writing the redo log.
Deadlock occurs when two transactions wait indefinitely for resources held by each other.
A primary key is a column that uniquely identifies each row in a table.
An aggregate function computes a single value over many rows.
A subquery is a query nested inside another query.
A view is a named query stored in the schema.
Isolation determines how concurrent transactions see each other.
Durability means committed changes survive failure.
An inner join returns rows matching in both tables.
First normal form requires every attribute to be atomic.
Second normal form removes partial dependencies on a composite key.
Third normal form removes transitive dependencies.
The redo log records every change to the database.
Oracle uses locks that prevent destructive interaction between users.
Two-phase locking guarantees conflict serializability.
"""


class NoProvider:
    def complete_structured(self, **_kwargs):
        raise AIServiceError("no provider configured")


def _mcq_candidate(
    *, blueprint: dict[str, Any], prompt: str, answer: str, distractors: list[str]
) -> _RawCandidate:
    evidence = blueprint["evidence"]
    return _RawCandidate(
        id=f"prov-{blueprint['id']}",
        blueprint_id=blueprint["id"],
        type="mcq",
        prompt=prompt,
        options=[answer, *distractors],
        correct_answer=answer,
        explanation=f"The source states that the answer is that {answer}.",
        source_pages=list(blueprint["pages"]),
        source_quote=evidence,
        distractor_rationales=[
            "The source attributes this to a different component.",
            "This names a different database concept.",
            "This describes an unrelated mechanism.",
        ],
    )


class DuplicateAnswerProvider(FakeQuizService):
    """A cooperative provider whose first two concept blueprints receive the
    same verbatim correct answer (the shared-evidence shape).

    Everything else about its candidates is exactly what the writer prompt
    demands, so every candidate that is not the duplicate passes every gate.
    """

    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawQualityJudgement:
            # Judge accepts everything (empty verdicts keep all candidates).
            return FakeCompletion(_RawQualityJudgement(verdicts=[]))
        return super().complete_structured(**kwargs)

    def _write(self, prompt: str) -> _RawQuizPool:
        plan = parse_blueprints(prompt)
        questions: list[_RawCandidate] = []
        for index, blueprint in enumerate(plan):
            concept = blueprint["concept"]
            if index == 0:
                questions.append(
                    _mcq_candidate(
                        blueprint=blueprint,
                        prompt=f"Which statement best describes the {concept}?",
                        answer="responsible for caching frequently accessed pages in memory",
                        distractors=[
                            "responsible for choosing execution plans",
                            "responsible for writing the redo log",
                            "responsible for parsing SQL statements",
                        ],
                    )
                )
            elif index == 1:
                # Same verbatim answer as index 0, different concept/prompt:
                # every objective gate passes, the answer collides.
                questions.append(
                    _mcq_candidate(
                        blueprint=blueprint,
                        prompt=f"Why is the {concept} important for the database?",
                        answer="responsible for caching frequently accessed pages in memory",
                        distractors=[
                            "important for choosing execution plans",
                            "important for writing the redo log",
                            "important for parsing SQL statements",
                        ],
                    )
                )
            else:
                evidence = blueprint["evidence"]
                answer = evidence.rstrip(".").split(".", 1)[0]
                for lead in (
                    "A ",
                    "An ",
                    "The ",
                    "A primary key is a column that ",
                ):
                    if answer.startswith(lead):
                        answer = answer[len(lead):]
                        break
                answer = answer[0].lower() + answer[1:] if answer else answer
                questions.append(
                    _mcq_candidate(
                        blueprint=blueprint,
                        prompt=f"Which statement best describes the {concept}?",
                        answer=answer,
                        distractors=[
                            "a different database mechanism",
                            "an unrelated storage structure",
                            "a scheduling artifact",
                        ],
                    )
                )
        return _RawQuizPool(questions=questions)


class FakeCompletion:
    def __init__(self, value):
        self.value = value
        self.provider = "gemini"
        self.model = "gemini-test"
        self.fallback_used = False


# --------------------------------------------------------------------------- #
# 1 + 2: the duplicate answer is pruned before selection and the slot is
# refilled from new material — the quiz still reaches 8 without shipping it.
# --------------------------------------------------------------------------- #


def test_duplicate_answer_is_pruned_and_replaced_not_shipped() -> None:
    source = source_from_text(INCIDENT_SHAPE_TEXT, title="SQL18")
    result = generate_quiz(
        DuplicateAnswerProvider(title="SQL18"),
        source,
        count=8,
        question_types=list(ALL_TYPES),
        difficulty="mixed",
        kind="exam",
        language="en",
        seed=20260824,
        previous_questions=[],
        system_prompt="You are LearnX.",
    )

    assert len(result.questions) == 8, (
        "the pipeline should refill a preflight-killed slot, not strand short"
    )

    # No duplicate correct answer ever ships.
    non_tf = [q.correct_answer for q in result.questions if q.type != "true-false"]
    normalized = [
        normalize(q) for q in non_tf
    ]
    assert len(set(normalized)) == len(normalized), f"duplicate answers shipped: {non_tf}"

    # The kill is recorded with the audit's own reason, while it could still
    # be replaced (stage telemetry shows the preflight, not a post-selection
    # strand).
    duplicate_kills = [
        note
        for note in result.rejections
        if note.stage == "final_validation"
        and "duplicate correct answer" in note.reason
    ]
    assert duplicate_kills, "the duplicate-answer kill was not recorded"
    assert result.telemetry.get("pool_preflight_rejected", 0) >= 1

    # The surviving quiz is still fully provenanced.
    assert len(result.provenance) == 8


def normalize(text: str) -> str:
    from app.services.quiz_scoring import normalize_question_text

    return normalize_question_text(text)


# --------------------------------------------------------------------------- #
# 1b: when the preflight kill leaves the pool short, the freed slot is refilled
# from new knowledge targets before selection — the exact production shape
# (shared-evidence concepts on a thin deck), end to end.
# --------------------------------------------------------------------------- #


class SharedEvidenceProvider(FakeQuizService):
    """Answers exactly one writer batch with its own concepts' facet clauses.

    Two concepts in the document share the same clause ("... is responsible
    for caching frequently accessed pages in memory"), so the pool this
    provider produces holds a verbatim-duplicate answer pair whose prompts and
    objectives are fully distinct. The provider then fails, so the pool is
    exactly one batch and the preflight kill strands it one short unless the
    refill plans new material.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.writer_calls = 0

    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawQualityJudgement:
            return FakeCompletion(_RawQualityJudgement(verdicts=[]))
        if kwargs["response_model"] is not _RawUnderstanding:
            self.writer_calls += 1
            if self.writer_calls > 1:
                # Still reachable, but declines to write more: the pool stays
                # at exactly one batch, so only the refill can restore the
                # requested count after the preflight kill.
                return FakeCompletion(_RawQuizPool(questions=[]))
        return super().complete_structured(**kwargs)

    def _write(self, prompt: str) -> _RawQuizPool:
        plan = parse_blueprints(prompt)

        def clause_of(evidence: str) -> str:
            sentence = evidence.split(". ", 1)[0].strip().rstrip(".")
            for marker in (" is responsible for ", " occurs when ", " is a column that "):
                if marker in sentence:
                    return sentence.split(marker, 1)[1].strip()
            lowered = sentence.lower()
            for lead in (
                "an aggregate function ",
                "a view ",
                "isolation ",
                "durability ",
            ):
                if lowered.startswith(lead):
                    return sentence[len(lead):].strip()
            return sentence

        clauses: dict[str, str] = {}
        sentences: dict[str, str] = {}
        for blueprint in plan:
            key = normalize(blueprint["concept"])
            clauses.setdefault(key, clause_of(blueprint["evidence"]))
            sentences.setdefault(
                key, blueprint["evidence"].split(". ", 1)[0].strip().rstrip(".")
            )

        def build(blueprint: dict[str, Any]) -> _RawCandidate | None:
            key = normalize(blueprint["concept"])
            question_type = blueprint.get("type", "mcq")
            if question_type == "true-false":
                return _RawCandidate(
                    blueprint_id=blueprint["id"],
                    type="true-false",
                    prompt=f"{sentences[key]} as the source explains it.",
                    correct_answer="True",
                    explanation=f"The source states that {sentences[key]}.",
                    source_pages=list(blueprint["pages"]),
                    source_quote=blueprint["evidence"],
                )
            answer = clauses.get(key, "")
            if question_type == "short-answer":
                target = blueprint.get("target", "")
                if "apply" in target or "predict" in target:
                    sa_prompt = (
                        f"When pages are accessed frequently, what does the "
                        f"{blueprint['concept']} do?"
                    )
                else:
                    sa_prompt = f"What does the source say about the {blueprint['concept']}?"
                return _RawCandidate(
                    blueprint_id=blueprint["id"],
                    type="short-answer",
                    prompt=sa_prompt,
                    correct_answer=answer,
                    explanation=f"The source states that {sentences[key]}.",
                    source_pages=list(blueprint["pages"]),
                    source_quote=blueprint["evidence"],
                )
            seen: set[str] = {normalize(answer)}
            distractors: list[str] = []
            for other_key in clauses:
                clause = clauses[other_key]
                if not clause or normalize(clause) in seen:
                    continue
                seen.add(normalize(clause))
                distractors.append(clause)
            if len(distractors) < 3:
                distractors += [
                    "a different database mechanism",
                    "an unrelated storage structure",
                    "a scheduling artifact",
                ]
            return _mcq_candidate(
                blueprint=blueprint,
                prompt=f"Which statement best describes the {blueprint['concept']}?",
                answer=answer,
                distractors=distractors[:3],
            )

        questions = [raw for raw in (build(bp) for bp in plan) if raw is not None]
        return _RawQuizPool(questions=questions)


SHARED_EVIDENCE_TEXT = """[Page 1]
The buffer manager is responsible for caching frequently accessed pages in memory.
The page cache is responsible for caching frequently accessed pages in memory.
The query optimizer is responsible for choosing execution plans.
Deadlock occurs when two transactions wait indefinitely for resources held by each other.
A primary key is a column that uniquely identifies each row in a table.
"""


def test_preflight_kill_leaving_pool_short_is_refilled_to_full_count() -> None:
    """A pool one short after the duplicate-answer prune is topped back up.

    Mirrors the production shape directly: the provider wrote one batch, two
    of its candidates carry the same verbatim answer, and after the preflight
    prune the pool holds 7 candidates for a request of 8. The refill must plan
    NEW objectives (not the killed ones), write them through the deterministic
    writer, preflight the additions, and hand selection a full pool.
    """
    source = source_from_text(SHARED_EVIDENCE_TEXT, title="SQL18")
    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    context.understanding = understanding
    context.knowledge_targets = build_knowledge_targets(understanding)

    # Build the real blueprint plan, then keep only the first batch's worth of
    # gate-passing provider candidates, with the shared-evidence pair intact.
    blueprints = build_question_blueprints(
        context.knowledge_targets,
        count=8,
        question_types=list(ALL_TYPES),
        difficulty="mixed",
        seed=20260824,
    )
    blueprints = replan_unsafe_mcq_blueprints(
        blueprints,
        selected_question_types=list(ALL_TYPES),
        understanding=understanding,
    )
    blueprint_by_id = {bp.id: bp for bp in blueprints}

    provider = SharedEvidenceProvider(title="SQL18")
    # First writer batch, as the pipeline would send it.
    from app.services.quiz_pipeline import build_candidate_prompt

    batch = blueprints[:8]
    writer_prompt = build_candidate_prompt(
        understanding=understanding,
        blueprints=batch,
        knowledge_targets=context.knowledge_targets,
        count=8,
        candidate_count=12,
        kind="exam",
        difficulty="mixed",
        previous_questions=[],
    )
    pool_raw = provider._write(writer_prompt)

    records = _collect_records(
        pool_raw.questions,
        context=context,
        source=source,
        blueprint_by_id=blueprint_by_id,
        previous_questions=[],
        rejections=[],
        candidates_by_type=Counter(),
    )
    scored, scores = _score_and_filter(
        records,
        context=context,
        difficulty="mixed",
        previous_questions=[],
        quality_threshold=0.55,
        rejections=[],
    )
    scored = _dedupe_scored(scored)
    assert len(scored) >= 7, f"fixture pool too small: {len(scored)}"
    assert len(scored) < 8, "fixture must start short of the requested count"

    rejections: list[RejectionNote] = []
    funnel = _new_funnel(len(blueprints))
    survivors = _preflight_and_refill_pool(
        scored,
        scores,
        context=context,
        source=source,
        understanding=understanding,
        blueprint_by_id=blueprint_by_id,
        count=8,
        question_types=list(ALL_TYPES),
        difficulty="mixed",
        language="en",
        seed=20260824,
        previous_questions=[],
        quality_threshold=0.55,
        rejections=rejections,
        funnel=funnel,
        candidates_by_type=Counter(),
    )

    assert len(survivors) >= 8, (
        f"refill failed to restore the pool: {len(survivors)}"
    )
    assert funnel.get("pool_preflight_rejected", 0) >= 1
    # Every survivor passes the final audit for its own provenance.
    non_tf = [
        normalize(candidate.question.correct_answer)
        for candidate in survivors
        if candidate.question.type != "true-false"
    ]
    assert len(set(non_tf)) == len(non_tf), "duplicate answers survived the preflight"
    refill_kills = [
        note for note in rejections if "duplicate correct answer" in note.reason
    ]
    assert refill_kills, "the duplicate was not recorded"


# --------------------------------------------------------------------------- #
# 3: the facet ``_claim`` last resort — short facet clauses are answered by the
# source's own claim; nothing ungrounded is introduced.
# --------------------------------------------------------------------------- #


def test_short_facet_clause_still_writes_from_source_claim() -> None:
    text = (
        "A long transaction leads to lock contention.\n"
        "Lock contention reduces concurrency.\n"
        "A deadlock occurs when two transactions wait indefinitely for resources "
        "held by each other.\n"
        "A primary key is a column that uniquely identifies each row in a table.\n"
        "An aggregate function computes a single value over many rows.\n"
        "A view is a named query stored in the schema.\n"
        "Isolation determines how concurrent transactions see each other.\n"
        "Durability means committed changes survive failure.\n"
        "First normal form requires every attribute to be atomic.\n"
        "The redo log records every change to the database.\n"
    )
    source = source_from_text(text, title="short-clause")
    try:
        result = generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=list(ALL_TYPES),
            difficulty="mixed",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the supplied source.",
        )
        telemetry = result.telemetry
    except Exception as exc:  # noqa: BLE001 - shortfall must still be honest
        telemetry = getattr(exc, "telemetry", None)
        raise AssertionError(
            "the short-clause document should not lose writer yield"
        ) from exc

    # Every planned slot produced a candidate: no silent mid-run drops.
    assert telemetry["deterministic_candidates_dropped"] == 0
    assert telemetry["deterministic_candidates_returned"] == (
        telemetry["deterministic_candidates_attempted"]
    )


def test_writer_writable_types_covers_short_clause_facet_targets() -> None:
    text = (
        "A long transaction leads to lock contention.\n"
        "Lock contention reduces concurrency.\n"
        "A deadlock occurs when two transactions wait indefinitely for resources "
        "held by each other.\n"
    )
    source = source_from_text(text, title="short-clause")
    from app.services.quiz_pipeline import build_quiz_context, build_document_understanding

    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    from app.services.quiz_knowledge_targets import build_knowledge_targets

    targets = build_knowledge_targets(understanding)
    facet_targets = [t for t in targets if t.facet_kind]
    assert facet_targets, "expected facet-backed targets from the causal sentences"
    types = ["mcq", "true-false", "fill-blank", "short-answer"]
    writable = [
        (t, writer_writable_types(t, types, understanding=understanding))
        for t in facet_targets
    ]
    # The facet targets whose clause is too short to stand alone are still
    # constructible from the source's own claim.
    assert any(w for _, w in writable), (
        "short-clause facet targets lost constructibility: "
        f"{[(t.target_id, w) for t, w in writable]}"
    )


def test_short_clause_answer_is_grounded_in_source() -> None:
    text = (
        "A long transaction leads to lock contention.\n"
        "Lock contention reduces concurrency.\n"
    )
    source = source_from_text(text, title="short-clause")
    from app.services.quiz_pipeline import build_quiz_context, build_document_understanding
    from app.services.quiz_knowledge_targets import build_knowledge_targets
    from app.services.quiz_blueprints import build_question_blueprints
    from app.services.quiz_deterministic import (
        SUPPORTED_SKILLS,
        replan_unsafe_mcq_blueprints,
        writer_type_veto,
        writable_question_types,
    )

    context = build_quiz_context(source)
    understanding, _ = build_document_understanding(
        NoProvider(), source, context, system_prompt=""
    )
    targets = build_knowledge_targets(understanding)
    types = ["mcq", "true-false", "fill-blank", "short-answer"]
    planned = build_question_blueprints(
        targets,
        count=8,
        question_types=writable_question_types(types, understanding),
        difficulty="mixed",
        seed=7,
        allowed_skills=SUPPORTED_SKILLS,
        type_filter=writer_type_veto(understanding),
    )
    planned = replan_unsafe_mcq_blueprints(
        planned, selected_question_types=types, understanding=understanding
    )
    written = deterministic_candidates(
        planned, language="en", understanding=understanding
    )
    assert written
    for item in written:
        # Every answer must be the document's own words.
        assert item["correct_answer"] in item["source_quote"] or all(
            token in item["source_quote"].lower()
            for token in item["correct_answer"].lower().split()[:4]
        ), f"ungrounded answer: {item['correct_answer']!r}"


# --------------------------------------------------------------------------- #
# 4: a document that genuinely supports fewer than 8 distinct questions still
# fails honestly (no padding, no forced count).
# --------------------------------------------------------------------------- #


def test_genuinely_thin_document_still_fails_honestly() -> None:
    thin = (
        "A primary key is a column that uniquely identifies each row in a table.\n"
        "A foreign key references the primary key of another table.\n"
    )
    source = source_from_text(thin, title="Thin")
    with pytest.raises(Exception) as excinfo:
        generate_quiz(
            NoProvider(),
            source,
            count=8,
            question_types=list(ALL_TYPES),
            difficulty="mixed",
            kind="exam",
            language="en",
            seed=1,
            previous_questions=[],
            system_prompt="Use only the supplied source.",
        )
    assert getattr(excinfo.value, "available", None) is not None
    assert excinfo.value.available < 8
