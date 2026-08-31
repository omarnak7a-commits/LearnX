"""Provider recovery must re-plan NEW objectives, not retry declined ones.

Production reproduction (file 075eb4af-..., SQL18.pdf, 32 pages / 30 text /
2 image-only, 8 requested) returned:

    HTTP 422 "LearnX could only verify 6 of 8 questions. 2 page(s) are images
    or scans with no extractable text..."

with the funnel showing ``provider_topup_calls = 2``,
``deterministic_candidates_returned = 0`` and top-up rounds ending in
``no_new_objectives`` -- while the study map held 25 concepts, nineteen of
which were never offered to the provider at all.

The cause was structural, not a threshold: provider recovery could only retry
the *original* blueprints. An objective the writer cannot express produces the
same rejection every retry, so the only route to new material was the
deterministic writer, and a real slide deck of SQL listings gives that writer
very little. These tests pin the fix -- recovery re-plans uncovered knowledge
targets and sends them through the identical gates -- and pin that nothing
else moved: no gate is relaxed, the deterministic fallback still works, and a
genuinely thin document still fails truthfully.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.services.quiz_pipeline as quiz_pipeline
from app.services.ai_documents import _extract_pdf_uncached, source_from_text
from app.services.ai_service import AIServiceError, AIStructuredCompletion
from app.services.quiz_pipeline import (
    QuizContentError,
    QuizMaterialError,
    _RawQuizPool,
    generate_quiz,
)
from app.services.quiz_quality_judge import _RawQualityJudgement
from app.services.quiz_understanding import _RawUnderstanding
from tests.quiz_fakes import FakeQuizService

FIXTURE = Path(__file__).parent / "fixtures" / "sql18_shaped_32_pages.pdf"
PRODUCTION_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]
RECOVERY_PREFIX = "prov-recovery"


def sql18_source():
    """The production request shape: whole 32-page document, nothing excluded."""
    return _extract_pdf_uncached(
        FIXTURE.read_bytes(),
        file_id="075eb4af-5813-41d0-9602-23065c1e4ddf",
        title="SQL18.pdf",
        max_characters=100_000,
        allowed_pages=None,
    )


def run(service, source, count=8, language="en"):
    return generate_quiz(
        service,
        source,
        count=count,
        question_types=list(PRODUCTION_TYPES),
        difficulty="mixed",
        kind="exam",
        language=language,
        seed=20260824,
        previous_questions=[],
        system_prompt="You are LearnX.",
    )


@pytest.fixture
def offline_writer_silent(monkeypatch):
    """Model a deck the deterministic writer cannot author from.

    Production's funnel showed ``deterministic_candidates_returned = 0`` on a
    32-page SQL deck: code listings and result tables are not the declarative
    prose the offline writer needs. Without this fixture the deterministic
    safety net masks the provider-side gap these tests exist to pin.
    """
    monkeypatch.setattr(quiz_pipeline, "deterministic_candidates", lambda *a, **k: [])


class _WriterBase:
    """Understanding and quality judging are healthy; only writing is shaped."""

    def __init__(self, title: str = "cell") -> None:
        self.inner = FakeQuizService(title=title)
        self.writer_calls = 0
        self.recovery_blueprint_ids: list[str] = []

    def complete_structured(self, **kwargs):
        model = kwargs["response_model"]
        if model is _RawUnderstanding or model is _RawQualityJudgement:
            return self.inner.complete_structured(**kwargs)
        self.writer_calls += 1
        full = self.inner.complete_structured(**kwargs)
        questions = self.shape(list(full.value.questions))
        self.recovery_blueprint_ids.extend(
            q.blueprint_id for q in questions if q.blueprint_id.startswith(RECOVERY_PREFIX)
        )
        return AIStructuredCompletion(
            value=_RawQuizPool(questions=questions),
            provider="gemini",
            model="gemini-test",
            fallback_used=False,
        )

    def shape(self, questions):  # pragma: no cover - overridden
        return questions


class DeclinesSomeObjectives(_WriterBase):
    """Writes for at most ``cap`` of the originally planned objectives.

    The exact production shape: the provider answers for most of the plan and
    simply never produces an acceptable candidate for the rest, no matter how
    often those slots are retried. Freshly planned recovery objectives are
    answerable -- the material exists, it was just never requested.
    """

    def __init__(self, cap: int) -> None:
        super().__init__()
        self.cap = cap
        self.answered: list[str] = []

    def shape(self, questions):
        kept = []
        for question in questions:
            blueprint_id = question.blueprint_id
            if blueprint_id.startswith(RECOVERY_PREFIX) or blueprint_id in self.answered:
                kept.append(question)
                continue
            if len(self.answered) < self.cap:
                self.answered.append(blueprint_id)
                kept.append(question)
        return kept


class MalformedFirstBatch(_WriterBase):
    """The first writer response is unusable (no answer, no options, no pages).

    Models a provider that returns structurally broken output for a batch. The
    gates must reject all of it -- never repair it into the quiz -- and the
    bounded recovery rounds must then rebuild the pool to the requested count.
    """

    def shape(self, questions):
        if self.writer_calls > 1:
            return questions
        shaped = []
        for question in questions:
            broken = question.model_copy(deep=True)
            broken.options = []
            broken.correct_answer = ""
            broken.source_pages = []
            shaped.append(broken)
        return shaped


class DuplicatesForOriginalPlan(_WriterBase):
    """Repeats one candidate for every original slot (a real provider failure)."""

    def shape(self, questions):
        originals = [q for q in questions if not q.blueprint_id.startswith(RECOVERY_PREFIX)]
        recovery = [q for q in questions if q.blueprint_id.startswith(RECOVERY_PREFIX)]
        if not originals:
            return recovery
        first = originals[0]
        cloned = []
        for question in originals:
            copy = first.model_copy(deep=True)
            copy.blueprint_id = question.blueprint_id
            cloned.append(copy)
        return [*cloned, *recovery]


class JudgeRejectsOriginalPlan(_WriterBase):
    """Healthy writer; the quality judge vetoes every original-plan candidate.

    Exercises the quality gate as the limiting stage rather than grounding:
    the vetoes must be replaced with new material, never admitted anyway.
    """

    def __init__(self) -> None:
        super().__init__()
        self.seen_original: set[str] = set()

    def complete_structured(self, **kwargs):
        if kwargs["response_model"] is _RawQualityJudgement:
            verdicts = [
                {
                    "blueprint_id": blueprint_id,
                    "accept": not self._is_original(blueprint_id),
                    "reason": "" if not self._is_original(blueprint_id) else "ambiguous stem",
                }
                for blueprint_id in self._prompt_ids(kwargs["user_prompt"])
            ]
            return AIStructuredCompletion(
                value=_RawQualityJudgement.model_validate({"verdicts": verdicts}),
                provider="gemini",
                model="gemini-test",
                fallback_used=False,
            )
        return super().complete_structured(**kwargs)

    @staticmethod
    def _prompt_ids(prompt: str) -> list[str]:
        ids = []
        for line in prompt.splitlines():
            if line.startswith("[") and "]" in line:
                ids.append(line[1 : line.index("]")])
        return ids

    @staticmethod
    def _is_original(blueprint_id: str) -> bool:
        return not blueprint_id.startswith(RECOVERY_PREFIX)


class TotallyUnavailable:
    def complete_structured(self, **kwargs):
        raise AIServiceError("provider unavailable")


# ── The production failure ──────────────────────────────────────────────────


def test_provider_that_declines_two_objectives_no_longer_caps_the_quiz_at_six(
    offline_writer_silent,
):
    """The reported 422: 8 requested, 6 verified. Must now be 8/8."""
    writer = DeclinesSomeObjectives(cap=6)
    result = run(writer, sql18_source())

    assert len(result.questions) == 8
    telemetry = result.telemetry
    # Recovery reached NEW material instead of retrying declined slots.
    assert telemetry["provider_replan_calls"] >= 1
    assert telemetry["provider_recovery_objectives_planned"] >= 2
    assert any(
        round_.get("replanned") and round_.get("added", 0) > 0
        for round_ in telemetry["provider_recovery_rounds"]
    )
    # No gate was bypassed to get there: everything accepted was scored.
    assert telemetry["provider_candidates_accepted"] <= telemetry[
        "provider_candidates_received"
    ]


def test_the_pre_fix_behaviour_is_the_one_that_regressed(offline_writer_silent):
    """Without re-planning, the identical scenario stops at six.

    Pins the diagnosis itself: with the re-planning budget removed the
    pipeline reproduces production's "could only verify 6 of 8" exactly, so a
    future refactor that quietly drops the budget fails here.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(quiz_pipeline, "_PROVIDER_REPLAN_CALLS", 0)
        with pytest.raises(QuizMaterialError) as excinfo:
            run(DeclinesSomeObjectives(cap=6), sql18_source())
    assert excinfo.value.available == 6
    assert "6 of 8" in str(excinfo.value)


def test_replanned_objectives_are_never_ones_already_attempted(offline_writer_silent):
    """Recovery must ask for new material, not re-ask what already failed."""
    writer = DeclinesSomeObjectives(cap=6)
    result = run(writer, sql18_source())

    recovery_ids = [
        blueprint.id
        for blueprint in result.blueprints
        if blueprint.id.startswith(RECOVERY_PREFIX)
    ]
    assert recovery_ids, "recovery planned no new blueprints"
    original_objectives = {
        blueprint.objective_key
        for blueprint in result.blueprints
        if not blueprint.id.startswith(RECOVERY_PREFIX)
    }
    recovery_objectives = [
        blueprint.objective_key
        for blueprint in result.blueprints
        if blueprint.id.startswith(RECOVERY_PREFIX)
    ]
    assert not original_objectives.intersection(recovery_objectives)
    assert len(set(recovery_objectives)) == len(recovery_objectives)


# ── Other failure modes recovery has to survive ─────────────────────────────


def test_malformed_provider_candidates_are_dropped_and_replaced(offline_writer_silent):
    result = run(MalformedFirstBatch(), sql18_source())
    assert len(result.questions) == 8
    # The malformed batch was rejected, not repaired into the quiz.
    assert result.telemetry["grounding_rejected"] > 0
    for question in result.questions:
        assert question.correct_answer.strip()
        assert question.source_pages


def test_duplicate_provider_candidates_are_deduped_and_replaced(offline_writer_silent):
    result = run(DuplicatesForOriginalPlan(), sql18_source())
    assert len(result.questions) == 8
    prompts = [question.prompt.strip().lower() for question in result.questions]
    assert len(set(prompts)) == len(prompts)


def test_quality_judge_rejections_are_replaced_not_admitted():
    """Vetoed candidates are replaced from other material, never admitted.

    The deterministic writer stays enabled here: the point is that a quality
    veto costs the quiz nothing, whichever recovery route refills the slot.
    """
    writer = JudgeRejectsOriginalPlan()
    result = run(writer, sql18_source())
    assert len(result.questions) == 8
    telemetry = result.telemetry
    assert telemetry["quality_judge_rejected"] > 0
    # Every veto is recorded with its reason, and the quiz was refilled rather
    # than shortened. (Deterministic top-up questions are gated by the scoring
    # heuristics rather than the provider judge, so the assertion is about the
    # count contract holding despite the vetoes, not about text identity.)
    assert [note for note in result.rejections if note.stage == "quality_judge"]


def test_provider_completely_unavailable_still_uses_deterministic_fallback():
    """The offline safety net is untouched by the provider-side change."""
    result = run(TotallyUnavailable(), sql18_source())
    assert len(result.questions) == 8
    assert result.telemetry["final_questions_by_origin"] == {"deterministic": 8}
    # A dead provider is never asked to recover.
    assert result.telemetry["provider_replan_calls"] == 0


def test_non_text_pages_do_not_block_a_quiz_the_text_pages_support():
    """30 text pages of 32 must be enough; the 2 image pages are not fatal."""
    source = sql18_source()
    assert sum(1 for page in source.pages if not page.text_available) >= 1
    result = run(DeclinesSomeObjectives(cap=6), source)
    assert len(result.questions) == 8
    used_pages = {page for question in result.questions for page in question.source_pages}
    text_pages = {page.page for page in source.pages if page.text_available}
    assert used_pages.issubset(text_pages)


# ── The exact-count contract is unchanged ───────────────────────────────────


def test_a_genuinely_thin_source_still_fails_truthfully(offline_writer_silent):
    """Recovery must not invent questions a document cannot support."""
    source = source_from_text(
        "Normalization removes redundancy from a relational schema.",
        "Tiny note",
    )
    with pytest.raises((QuizMaterialError, QuizContentError)) as excinfo:
        run(DeclinesSomeObjectives(cap=0), source, count=8)
    error = excinfo.value
    if isinstance(error, QuizMaterialError):
        assert error.available < 8
        assert "8" in str(error)


def test_recovery_is_bounded_so_a_thin_document_fails_fast(offline_writer_silent):
    """A writer that never produces anything must not loop indefinitely."""

    class NeverWrites(_WriterBase):
        def shape(self, questions):
            return []

    writer = NeverWrites()
    with pytest.raises((QuizMaterialError, quiz_pipeline.AIUnavailableError)):
        run(writer, sql18_source())
    # initial batches + bounded topup + bounded replan, and nothing beyond.
    assert writer.writer_calls <= 8
