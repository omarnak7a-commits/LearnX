# --------------------------------------------------------------------------- #
# MSEMAX — constrained LLM phrasing layer for blueprinted questions.
# --------------------------------------------------------------------------- #
#
# WHAT THIS IS
# ------------
# MSEMAX is an *optional* generation layer that sits between the deterministic
# planner and the deterministic validators:
#
#     document understanding  (deterministic, authoritative)
#         -> concepts + evidence + facets
#         -> knowledge targets
#         -> question blueprints        (deterministic, authoritative)
#         -> MSEMAX                     <- THIS MODULE (optional)
#         -> _collect_records / grounding / grammar / dedup gates
#         -> scoring + quality gates
#         -> diversity selection
#         -> final quiz
#
# MSEMAX never decides *what* to ask. The deterministic pipeline has already
# chosen the concept, the cognitive skill, the evidence sentence, the facet, the
# question type and the difficulty. MSEMAX is asked one narrow question:
#
#     "Given THIS evidence sentence and THESE constraints, write the natural
#      language for this exact question."
#
# It therefore cannot introduce a new concept, retarget a skill, or invent a
# relationship: those decisions are made before it is called and re-verified
# after it returns.
#
# WHY A SEPARATE MODULE
# ---------------------
# Keeping MSEMAX out of quiz_deterministic.py preserves the property the rest of
# this rewrite depends on: the deterministic writer remains a complete,
# self-sufficient generator. With MSEMAX disabled the byte-for-byte behaviour of
# the baseline is unchanged, which is what makes A/B comparison meaningful.
#
# NO FAKE BACKEND
# ---------------
# This module has no built-in stub, canned response, or offline imitation mode.
# If MSEMAX is enabled without a usable provider it raises
# ``MsemaxConfigurationError`` rather than silently producing something that
# looks like model output. Deterministic text is never relabelled as MSEMAX
# output.
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_scoring import content_tokens, normalize_question_text

logger = logging.getLogger(__name__)


#: Marks output produced by the MSEMAX layer. Carried on the candidate dict so
#: provenance stays honest end to end: a question is only ever attributed to
#: MSEMAX when a real provider actually wrote it.
MSEMAX_ORIGIN = "msemax"

#: Deterministic writer's origin label, for the same reason.
DETERMINISTIC_ORIGIN = "deterministic"


class MsemaxError(RuntimeError):
    """Base class for MSEMAX failures."""


class MsemaxConfigurationError(MsemaxError):
    """MSEMAX is enabled but cannot run (no provider / no credentials).

    Raised loudly instead of degrading quietly: a caller that asked for MSEMAX
    must be told it is not actually available rather than being handed
    deterministic output wearing an LLM label.
    """


@dataclass(frozen=True)
class MsemaxRejection:
    """A structured generation failure.

    Every unusable generation produces one of these instead of ``None`` so the
    pipeline can log *why* MSEMAX declined and fall back deliberately. This is
    the mechanism that keeps "no silent candidate loss" true for the LLM path.
    """

    blueprint_id: str
    concept_id: str
    cognitive_skill: str
    reason: str
    prompt: str = ""


@dataclass
class MsemaxStats:
    """Per-run counters, surfaced for benchmarking and diagnostics."""

    requested: int = 0
    generated: int = 0
    rejected: int = 0
    provider_errors: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def note_rejection(self, reason: str) -> None:
        self.rejected += 1
        key = reason.split(":", 1)[0].strip()
        self.reasons[key] = self.reasons.get(key, 0) + 1


# --------------------------------------------------------------------------- #
# Output contract
# --------------------------------------------------------------------------- #
#
# The model must return this shape and nothing else. It is deliberately
# minimal: every field the pipeline needs but MSEMAX must NOT choose (concept,
# skill, pages, evidence, difficulty, question type) is supplied by the
# blueprint and re-attached afterwards, so the model has no opportunity to
# change them.
class MsemaxQuestion(BaseModel):
    """Schema-constrained MSEMAX response."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    stem: str = Field(default="", description="The question sentence.")
    options: list[str] = Field(
        default_factory=list,
        description="Answer options for multiple choice; empty for other types.",
    )
    correct_option: int = Field(
        default=0, description="0-based index of the correct option."
    )
    answer: str = Field(
        default="", description="The correct answer for non-multiple-choice types."
    )
    explanation: str = Field(
        default="", description="One sentence justifying the answer from the evidence."
    )


class MsemaxBackend(Protocol):
    """The minimum surface MSEMAX needs from an AI service.

    Matches ``AIService.complete_structured`` so the existing provider stack
    (Gemini primary, Groq fallback, timeouts, retry, JSON extraction) is reused
    rather than duplicated.
    """

    def complete_structured(self, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...


# --------------------------------------------------------------------------- #
# Prompting
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = (
    "You are a question-phrasing assistant for an exam generator. "
    "You do NOT choose what to test: the concept, the evidence, the cognitive "
    "skill and the question type have already been decided. "
    "Your only job is to express that exact question in clear, natural, "
    "grammatical English.\n"
    "\n"
    "Absolute rules:\n"
    "1. Use ONLY information contained in the supplied evidence. Never add a "
    "fact, cause, mechanism, example, number, date, or consequence that is not "
    "written there.\n"
    "2. Never change the concept being tested.\n"
    "3. Never change the cognitive skill. A comparison must ask for a "
    "difference; a cause/effect question must ask for a cause or an effect; a "
    "mechanism question must ask how something works.\n"
    "4. The correct answer must be supported word-for-word in meaning by the "
    "evidence.\n"
    "5. Distractors must be plausible, mutually exclusive, grammatically "
    "parallel with the correct answer, and similar to it in length. They must "
    "be wrong according to the evidence.\n"
    "6. Never mention 'the document', 'the text', 'the passage', or 'the "
    "source'.\n"
    "7. Never restate a source sentence verbatim as the question.\n"
    "8. If the evidence cannot support the requested question, return an empty "
    "stem. Do not invent a substitute."
)


def _requirements_for(skill: str, question_type: str) -> list[str]:
    """Skill-specific phrasing requirements, derived from the blueprint.

    These are constraints on *expression*, not new content: they restate what
    the deterministic planner already decided so the model cannot drift into a
    different kind of question.
    """
    requirements: list[str] = []
    if skill == "comparison":
        requirements.append(
            "Ask how the concept differs from the specific thing it is "
            "contrasted with. The answer must state the difference, not merely "
            "define the concept."
        )
    elif skill == "cause_effect":
        requirements.append(
            "Ask for the cause or the effect that the evidence states."
        )
    elif skill == "process_order":
        requirements.append(
            "Ask how the concept works or in what order its steps occur."
        )
    elif skill == "misconception":
        requirements.append(
            "Write a statement that is FALSE according to the evidence but "
            "sounds plausible. It must be false because it misattributes "
            "something, not because it is nonsense."
        )
    elif skill in {"understanding", "factual_recall"}:
        requirements.append(
            "Ask which statement best describes the concept, or what it is."
        )

    if question_type == "mcq":
        requirements.append(
            "Return exactly 4 options. Exactly one is correct. No option may "
            "repeat another, and no option may be a superset of another."
        )
    elif question_type == "true-false":
        requirements.append(
            "Return exactly the options 'True' and 'False'. Put the statement "
            "in 'stem'."
        )
    elif question_type == "short-answer":
        requirements.append(
            "Return no options. Put the expected answer in 'answer'; keep it "
            "under 25 words."
        )
    elif question_type == "fill-blank":
        requirements.append(
            "The stem must contain a single blank written as ____ and the "
            "answer must be the missing term."
        )
    return requirements


def build_generation_payload(blueprint: QuestionBlueprint) -> dict[str, Any]:
    """The structured request sent to MSEMAX for one blueprint.

    Only blueprint-derived material is included; the raw document is never
    sent. The model sees the single evidence sentence the planner selected and
    nothing else, which is what makes ungrounded output detectable: anything
    outside this payload is, by construction, unsupported.
    """
    forbidden = [
        "information not present in the evidence",
        "references to 'the document', 'the text', 'the passage' or 'the source'",
        "invented examples, numbers, dates, causes or consequences",
    ]
    payload: dict[str, Any] = {
        "concept": blueprint.concept,
        "skill": blueprint.cognitive_skill,
        "question_type": blueprint.question_type,
        "difficulty": blueprint.difficulty,
        "evidence": blueprint.evidence,
        "knowledge_target": blueprint.knowledge_target,
        "requirements": _requirements_for(
            blueprint.cognitive_skill, blueprint.question_type
        ),
        "forbidden_content": forbidden,
    }
    if blueprint.facet_kind:
        payload["relationship_type"] = blueprint.facet_kind
    if blueprint.answer_clause:
        # For a contrast this holds the other side of the comparison; for other
        # facets it is the source's own wording of the answer.
        payload["answer_basis"] = blueprint.answer_clause
    return payload


def build_user_prompt(payload: dict[str, Any]) -> str:
    lines = [
        f"Concept: {payload['concept']}",
        f"Cognitive skill: {payload['skill']}",
        f"Question type: {payload['question_type']}",
        f"Difficulty: {payload['difficulty']}",
    ]
    if payload.get("relationship_type"):
        lines.append(f"Relationship being tested: {payload['relationship_type']}")
    if payload.get("answer_basis"):
        lines.append(f"The answer must be based on: {payload['answer_basis']}")
    lines.append(f"What this question must assess: {payload['knowledge_target']}")
    lines.append("")
    lines.append("EVIDENCE (the only permitted source of facts):")
    lines.append(f'"{payload["evidence"]}"')
    lines.append("")
    lines.append("Requirements:")
    lines.extend(f"- {item}" for item in payload["requirements"])
    lines.append("")
    lines.append("Never include:")
    lines.extend(f"- {item}" for item in payload["forbidden_content"])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Grounding checks applied to MSEMAX output
# --------------------------------------------------------------------------- #
#
# These run *before* the shared pipeline validators. They are not a replacement
# for them -- every MSEMAX candidate still goes through _collect_records,
# grounding scoring, grammar checks, dedup and the quality gates. They exist to
# catch LLM-specific failure modes early and to attribute the rejection
# precisely, so a benchmark can tell "the model hallucinated" apart from "the
# question scored slightly too low".

#: Referring to the artefact instead of the subject matter. Banned as exam
#: style and already rejected by the prompt gate downstream.
_META_REFERENCE = re.compile(
    r"\b(?:the\s+)?(?:document|text|passage|source|article|chapter|excerpt|"
    r"author|writer)\b",
    re.IGNORECASE,
)

#: Tokens that carry no subject matter, so their presence outside the evidence
#: is not evidence of hallucination.
_FUNCTION_WORDS = frozenset(
    """a an the of in on at to for with by from into onto over under and or but
    nor so yet is are was were be been being do does did has have had can could
    may might must shall should will would this that these those it its their
    his her our your which who whom whose what when where why how not no than
    then there here as if because while during about between among within
    across after before since until such more most less least other another
    each every both all any some one two three first second next last also
    only very much many few several does statement best describes explain
    following true false correct incorrect""".split()
)


def _unsupported_tokens(text: str, evidence: str) -> set[str]:
    """Content words in ``text`` that do not occur in ``evidence``.

    Morphology-tolerant: a token counts as supported when the evidence contains
    it or a shared stem, so "partitions" is supported by "partition". This is
    deliberately generous -- the goal is to catch invented facts, not to punish
    natural rephrasing, which is the whole point of using a model here.
    """
    evidence_tokens = content_tokens(evidence)
    evidence_stems = {token[:5] for token in evidence_tokens if len(token) >= 5}
    unsupported: set[str] = set()
    for token in content_tokens(text):
        if token in _FUNCTION_WORDS or len(token) < 4:
            continue
        if token in evidence_tokens:
            continue
        if len(token) >= 5 and token[:5] in evidence_stems:
            continue
        if any(token.startswith(stem) or stem.startswith(token) for stem in evidence_tokens):
            continue
        unsupported.add(token)
    return unsupported


def _shares_concept(text: str, concept: str) -> bool:
    """Does the stem actually mention the concept it is supposed to test?"""
    concept_tokens = {
        token for token in content_tokens(concept) if token not in _FUNCTION_WORDS
    }
    if not concept_tokens:
        return True
    text_tokens = content_tokens(text)
    return bool(concept_tokens & text_tokens) or any(
        any(token.startswith(part[:5]) for token in text_tokens)
        for part in concept_tokens
        if len(part) >= 5
    )


def _skill_is_honoured(stem: str, skill: str) -> bool:
    """Cheap check that the phrasing matches the requested cognitive skill.

    A model asked for a comparison sometimes returns a definition. That is a
    silent skill swap: the question would still be grounded and well formed, so
    no other gate would catch it, yet the quiz would lose its comparison slot.
    """
    lowered = stem.casefold()
    if skill == "comparison":
        return bool(
            re.search(
                r"\bdiffer|\bdifference|\bcontrast|\bunlike|\bcompared\b|"
                r"\bdistinguish|\bwhereas\b|\brather than\b",
                lowered,
            )
        )
    if skill == "cause_effect":
        return bool(
            re.search(r"\bwhy\b|\bcause|\bresult|\bleads?\s+to\b|\beffect|\bbecause\b", lowered)
        )
    if skill == "process_order":
        return bool(
            re.search(r"\bhow\b|\bmechanism\b|\bprocess\b|\bstep|\border\b|\boccur", lowered)
        )
    return True


def validate_generation(
    value: MsemaxQuestion, blueprint: QuestionBlueprint
) -> str | None:
    """Return a rejection reason, or ``None`` when the generation is usable.

    Ordered cheapest-first, and every branch names the specific violation so
    failures are attributable rather than lumped into one bucket.
    """
    stem = (value.stem or "").strip()
    if not stem:
        return "empty stem: model declined or returned nothing"
    if len(stem.split()) < 3:
        return "stem too short to be a question"
    if _META_REFERENCE.search(stem):
        return "stem refers to the document instead of the subject matter"

    evidence = blueprint.evidence
    normalized_stem = normalize_question_text(stem)
    if normalized_stem and normalized_stem in normalize_question_text(evidence):
        return "stem copies a source sentence verbatim"

    if not _shares_concept(stem, blueprint.concept):
        return f"stem does not mention the planned concept {blueprint.concept!r}"

    if not _skill_is_honoured(stem, blueprint.cognitive_skill):
        return (
            f"stem does not express the planned skill "
            f"{blueprint.cognitive_skill!r}"
        )

    unsupported = _unsupported_tokens(stem, evidence)
    if unsupported:
        return f"stem introduces unsupported content: {sorted(unsupported)[:4]}"

    question_type = blueprint.question_type
    if question_type == "mcq":
        options = [option.strip() for option in value.options if option.strip()]
        if len(options) != 4:
            return f"expected 4 options, received {len(options)}"
        if len({option.casefold() for option in options}) != len(options):
            return "duplicate options"
        if not 0 <= value.correct_option < len(options):
            return "correct_option out of range"
        answer = options[value.correct_option]
        unsupported_answer = _unsupported_tokens(answer, evidence)
        if unsupported_answer:
            return (
                "correct answer introduces unsupported content: "
                f"{sorted(unsupported_answer)[:4]}"
            )
        lengths = sorted(len(option.split()) for option in options)
        # A correct answer that is far longer than every distractor is a
        # giveaway even when it is perfectly grounded.
        if lengths[-1] >= 2 * max(lengths[0], 1) and len(answer.split()) == lengths[-1]:
            return "answer length giveaway"
    elif question_type == "true-false":
        options = [option.strip().casefold() for option in value.options]
        if sorted(options) != ["false", "true"]:
            return "true/false question must offer exactly True and False"
        answer = (value.answer or "").strip().casefold()
        if answer not in {"true", "false"}:
            return "true/false answer must be 'True' or 'False'"
    else:
        answer = (value.answer or "").strip()
        if not answer:
            return "missing answer"
        if len(answer.split()) > 40:
            return "answer too long"
        unsupported_answer = _unsupported_tokens(answer, evidence)
        if unsupported_answer:
            return (
                "answer introduces unsupported content: "
                f"{sorted(unsupported_answer)[:4]}"
            )

    explanation = (value.explanation or "").strip()
    if explanation and _META_REFERENCE.search(explanation):
        return "explanation refers to the document instead of the subject matter"
    if explanation:
        unsupported_explanation = _unsupported_tokens(explanation, evidence)
        if unsupported_explanation:
            return (
                "explanation introduces unsupported content: "
                f"{sorted(unsupported_explanation)[:4]}"
            )
    return None


def _to_candidate(
    value: MsemaxQuestion, blueprint: QuestionBlueprint
) -> dict[str, Any]:
    """Convert validated MSEMAX output into the pipeline's candidate shape.

    Everything the pipeline uses for provenance and grounding -- id, type,
    difficulty, pages, source quote -- is taken from the blueprint, never from
    the model. The model contributes prose only.
    """
    candidate: dict[str, Any] = {
        "id": f"msemax-{blueprint.id}",
        "blueprint_id": blueprint.id,
        "type": blueprint.question_type,
        "difficulty": blueprint.difficulty,
        "source_pages": list(blueprint.pages),
        "source_quote": blueprint.evidence,
        "prompt": value.stem.strip(),
        "explanation": value.explanation.strip(),
        "origin": MSEMAX_ORIGIN,
    }
    if blueprint.question_type == "mcq":
        options = [option.strip() for option in value.options if option.strip()]
        candidate["options"] = options
        candidate["correct_answer"] = options[value.correct_option]
    elif blueprint.question_type == "true-false":
        candidate["options"] = ["True", "False"]
        candidate["correct_answer"] = value.answer.strip().capitalize()
    else:
        candidate["correct_answer"] = value.answer.strip()
    return candidate


def generate_candidate(
    blueprint: QuestionBlueprint,
    *,
    backend: MsemaxBackend,
    system_prompt: str = _SYSTEM_PROMPT,
    temperature: float = 0.2,
) -> tuple[dict[str, Any] | None, MsemaxRejection | None]:
    """Ask MSEMAX to phrase one blueprint.

    Returns ``(candidate, None)`` on success or ``(None, rejection)`` on any
    failure -- provider error, malformed output, or a constraint violation.
    Never raises for a single bad generation: one unusable question must not
    abort the quiz, it must fall back to the deterministic writer.
    """
    payload = build_generation_payload(blueprint)
    try:
        completion = backend.complete_structured(
            response_model=MsemaxQuestion,
            system_prompt=system_prompt,
            user_prompt=build_user_prompt(payload),
            temperature=temperature,
            max_tokens=900,
        )
    except Exception as exc:  # provider error, timeout, malformed JSON
        logger.warning(
            "MSEMAX provider failure for blueprint %s: %s", blueprint.id, exc
        )
        return None, MsemaxRejection(
            blueprint_id=blueprint.id,
            concept_id=blueprint.concept_id,
            cognitive_skill=blueprint.cognitive_skill,
            reason=f"provider error: {type(exc).__name__}: {exc}",
        )

    value = getattr(completion, "value", completion)
    if not isinstance(value, MsemaxQuestion):
        return None, MsemaxRejection(
            blueprint_id=blueprint.id,
            concept_id=blueprint.concept_id,
            cognitive_skill=blueprint.cognitive_skill,
            reason="malformed output: response did not match the MSEMAX schema",
        )

    reason = validate_generation(value, blueprint)
    if reason is not None:
        return None, MsemaxRejection(
            blueprint_id=blueprint.id,
            concept_id=blueprint.concept_id,
            cognitive_skill=blueprint.cognitive_skill,
            reason=reason,
            prompt=(value.stem or "").strip(),
        )
    return _to_candidate(value, blueprint), None


def msemax_candidates(
    blueprints: list[QuestionBlueprint],
    *,
    backend: MsemaxBackend,
    stats: MsemaxStats | None = None,
) -> tuple[dict[str, dict[str, Any]], list[MsemaxRejection]]:
    """Phrase every blueprint MSEMAX can handle.

    Returns a ``{blueprint_id: candidate}`` map plus one rejection per failure.
    The map is keyed by blueprint so the caller can merge MSEMAX prose with
    deterministic output per slot: any blueprint MSEMAX declines simply keeps
    its deterministic candidate, so enabling MSEMAX can never reduce coverage.
    """
    tracker = stats if stats is not None else MsemaxStats()
    written: dict[str, dict[str, Any]] = {}
    rejections: list[MsemaxRejection] = []
    for blueprint in blueprints:
        tracker.requested += 1
        candidate, rejection = generate_candidate(blueprint, backend=backend)
        if candidate is not None:
            tracker.generated += 1
            written[blueprint.id] = candidate
            continue
        assert rejection is not None
        if rejection.reason.startswith("provider error"):
            tracker.provider_errors += 1
        tracker.note_rejection(rejection.reason)
        rejections.append(rejection)
    return written, rejections


def resolve_backend(settings: Any, service: Any = None) -> MsemaxBackend:
    """Return a usable MSEMAX backend or raise ``MsemaxConfigurationError``.

    There is no offline mode. MSEMAX is a real-provider feature: if no provider
    key is configured, enabling it is a configuration error, reported as such.
    """
    gemini = (getattr(settings, "gemini_api_key", "") or "").strip()
    groq = (getattr(settings, "groq_api_key", "") or "").strip()
    if not gemini and not groq:
        raise MsemaxConfigurationError(
            "MSEMAX_ENABLED is true but no AI provider credentials are "
            "configured. Set GEMINI_API_KEY or GROQ_API_KEY, or disable MSEMAX "
            "with MSEMAX_ENABLED=false."
        )
    if service is None:
        raise MsemaxConfigurationError(
            "MSEMAX_ENABLED is true but no AI service instance was supplied."
        )
    if not hasattr(service, "complete_structured"):
        raise MsemaxConfigurationError(
            "MSEMAX requires an AI service exposing complete_structured()."
        )
    return service
