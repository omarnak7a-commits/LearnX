"""Semantic quality gate for grounded quiz candidates.

Grounding already proves a candidate is supported by the PDF. This module
asks whether it is also an *exam-worthy* question. The judge is advisory in
one sense only: if the provider judge fails, heuristic verdicts still apply
and the pipeline continues. Grounding and final validation stay mandatory.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import AIQuizQuestion
from app.services.ai_service import AIServiceError
from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_grounding import is_layout_detail
from app.services.quiz_scoring import (
    content_jaccard,
    content_tokens,
    is_trivial_question,
    normalize_question_text,
)

logger = logging.getLogger(__name__)

_JUDGE_BATCH = 8


class _JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    blueprint_id: str = ""
    accept: bool = True
    reason: str = ""
    correctness: float = 1.0
    clarity: float = 1.0
    educational_value: float = 1.0
    difficulty: float = 1.0
    specificity: float = 1.0
    unambiguity: float = 1.0
    answer_quality: float = 1.0
    distractor_quality: float = 1.0
    source_support: float = 1.0


class _RawQualityJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    verdicts: list[_JudgeVerdict] = Field(default_factory=list)


def heuristic_quality_issues(
    question: AIQuizQuestion,
    blueprint: QuestionBlueprint,
) -> list[str]:
    """Return concise, student-safe reasons this question is not exam-worthy."""
    issues: list[str] = []
    prompt = question.prompt.strip()
    if is_trivial_question(prompt) or is_layout_detail(prompt):
        issues.append("question tests slide metadata rather than the subject")
    if normalize_question_text(prompt) == normalize_question_text(blueprint.evidence):
        issues.append("question merely restates source text")
    words = prompt.split()
    if len(words) < 5:
        issues.append("awkward wording")
    if question.type == "true-false" and len(words) < 6:
        issues.append("trivial true/false statement")
    if question.type == "mcq":
        issues.extend(_mcq_quality_issues(question))
    if question.type == "fill-blank":
        answer = normalize_question_text(question.correct_answer)
        if answer in {"it", "this", "that", "they", "process", "system"}:
            issues.append("fill-blank answer is not specific")
    if question.type == "short-answer":
        if prompt.rstrip().endswith("?") is False and len(words) < 8:
            issues.append("short answer does not ask for explanation or recall")
    return issues


def _mcq_quality_issues(question: AIQuizQuestion) -> list[str]:
    issues: list[str] = []
    options = [value.strip() for value in (question.options or []) if value.strip()]
    if len(options) != 4:
        issues.append("MCQ does not have four options")
        return issues
    correct = normalize_question_text(question.correct_answer)
    overlaps: list[str] = []
    for option in options:
        key = normalize_question_text(option)
        if key == correct:
            continue
        # Near-identical option pairs make more than one choice defensible.
        if content_tokens(option) and content_tokens(option) == content_tokens(
            question.correct_answer
        ):
            overlaps.append(option)
        if key and (key in correct or correct in key):
            overlaps.append(option)
        if content_jaccard(option, question.correct_answer) >= 0.8:
            overlaps.append(option)
    if overlaps:
        issues.append("option may also be correct / ambiguous MCQ")
    return issues


def build_judge_prompt(items: list[tuple[AIQuizQuestion, QuestionBlueprint]]) -> str:
    lines = [
        "Judge whether each candidate is a high-quality exam question.",
        "Every item is already source-grounded. Reject nonsense, awkward wording,",
        "trivial recall of slide furniture, ambiguous stems, multiple-correct MCQs,",
        "weak distractors, and questions that need outside knowledge.",
        "Return one verdict per blueprint_id. Keep reasons short.",
        "",
    ]
    for question, blueprint in items:
        lines.append(f"[{blueprint.id}] type={question.type} skill={blueprint.cognitive_skill}")
        lines.append(f"  prompt: {question.prompt}")
        if question.options:
            lines.append(f"  options: {question.options}")
        lines.append(f"  answer: {question.correct_answer}")
        lines.append(f"  explanation: {question.explanation[:240]}")
        lines.append("")
    return "\n".join(lines)


def judge_records(
    records: list[Any],
    *,
    service: Any | None,
    system_prompt: str,
    funnel: dict[str, Any] | None = None,
) -> tuple[list[Any], list[tuple[Any, str]]]:
    """Split records into accepted vs quality-rejected.

    Provider judging is batched and non-blocking: a judge outage keeps every
    candidate that already passed the heuristic.
    """
    kept: list[Any] = []
    rejected: list[tuple[Any, str]] = []
    pending_provider: list[Any] = []

    for record in records:
        issues = heuristic_quality_issues(record.question, record.blueprint)
        if issues:
            rejected.append((record, issues[0]))
            continue
        pending_provider.append(record)

    if funnel is not None:
        funnel["quality_judge_attempts"] = funnel.get("quality_judge_attempts", 0) + len(records)

    provider_reject: dict[str, str] = {}
    if service is not None and pending_provider:
        try:
            provider_reject = _provider_judge(
                pending_provider, service=service, system_prompt=system_prompt
            )
        except AIServiceError:
            logger.info("quality judge provider unavailable; keeping heuristic-pass candidates")
        except Exception:
            logger.info("quality judge failed; keeping heuristic-pass candidates")

    for record in pending_provider:
        reason = provider_reject.get(record.blueprint.id, "")
        if reason:
            rejected.append((record, reason))
        else:
            kept.append(record)

    if funnel is not None:
        funnel["quality_judge_passed"] = funnel.get("quality_judge_passed", 0) + len(kept)
        funnel["quality_judge_rejected"] = funnel.get("quality_judge_rejected", 0) + len(rejected)
    return kept, rejected


def _provider_judge(
    records: list[Any],
    *,
    service: Any,
    system_prompt: str,
) -> dict[str, str]:
    rejected: dict[str, str] = {}
    items = [(record.question, record.blueprint) for record in records]
    for start in range(0, len(items), _JUDGE_BATCH):
        batch = items[start : start + _JUDGE_BATCH]
        completion = service.complete_structured(
            response_model=_RawQualityJudgement,
            system_prompt=system_prompt,
            user_prompt=build_judge_prompt(batch),
            temperature=0.0,
            max_tokens=3000,
        )
        for verdict in completion.value.verdicts:
            if verdict.accept:
                continue
            reason = (verdict.reason or "poor educational quality").strip()
            if verdict.blueprint_id:
                rejected[verdict.blueprint_id] = reason[:180]
    return rejected
