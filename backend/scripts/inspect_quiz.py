"""Inspect the full understanding-first quiz pipeline against a real PDF.

Usage (from the repository root):

    python backend/scripts/inspect_quiz.py public/demo-files/cell-biology-ch3.pdf --seed 7

Prints, in pipeline order:
    1. document summary
    2. main topics
    3. important concepts (with importance signals)
    4. knowledge targets
    5. quiz blueprint
    6. selected questions with concept/target/pages/skill/quality score

With no provider credentials configured, the deterministic study map and the
deterministic writer are exercised.  Set GEMINI_API_KEY / GROQ_API_KEY to run
the real provider path.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ai_documents import _extract_pdf  # noqa: E402
from app.services.ai_service import AIUnavailableError, AIService  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.quiz_blueprints import target_tier
from app.services.quiz_pipeline import generate_quiz  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument(
        "--types",
        default="mcq,true-false,fill-blank,short-answer",
        help="comma-separated question types",
    )
    args = parser.parse_args()

    data = Path(args.pdf).read_bytes()
    source = _extract_pdf(
        data,
        file_id="inspect",
        title=Path(args.pdf).stem,
        max_characters=100_000,
        allowed_pages=None,
    )
    print(f"SOURCE: {source.title} — {source.page_count} pages, {len(source.text)} chars")

    settings = Settings(_env_file=None)
    has_provider = bool(settings.gemini_api_key or settings.groq_api_key)
    print(f"PROVIDER CREDENTIALS CONFIGURED: {has_provider}")
    service = AIService(settings)

    try:
        result = generate_quiz(
            service,
            source,
            count=args.count,
            question_types=[value.strip() for value in args.types.split(",") if value.strip()],
            difficulty="mixed",
            kind="practice",
            language="en",
            seed=args.seed,
            previous_questions=[],
            system_prompt="You are LearnX, an accurate educational AI assistant.",
        )
    except AIUnavailableError as exc:
        print(f"\nAI QUIZ GENERATION UNAVAILABLE: {exc}")
        return 1

    understanding = result.understanding
    assert understanding is not None

    print("\n" + "=" * 78)
    print("1. DOCUMENT SUMMARY")
    print("=" * 78)
    print(f"subject: {understanding.subject}")
    print(f"study-map source: {understanding.source}")
    print(understanding.summary)

    print("\n" + "=" * 78)
    print("2. MAIN TOPICS")
    print("=" * 78)
    for topic in understanding.main_topics:
        print(f"- {topic.name}  pages={list(topic.pages)}  concepts={len(topic.concept_ids)}")
        for subtopic in topic.subtopics:
            print(f"    · {subtopic}")

    print("\n" + "=" * 78)
    print("3. IMPORTANT CONCEPTS (ranked by educational importance)")
    print("=" * 78)
    for concept in understanding.important_concepts(limit=20):
        print(
            f"- [{concept.concept_id}] {concept.name}\n"
            f"    type={concept.knowledge_type}  importance={concept.importance:.3f}  "
            f"pages={list(concept.source_pages)}  mentions={concept.mention_count}\n"
            f"    signals={concept.signals}\n"
            f"    evidence: {concept.primary_evidence[:150]}"
        )

    print("\n" + "=" * 78)
    print("4. KNOWLEDGE TARGETS")
    print("=" * 78)
    for target in result.knowledge_targets:
        print(
            f"- [{target.target_id}] {target.statement}  (skill={target.cognitive_skill}, "
            f"pages={list(target.pages)})"
        )

    print("\n" + "=" * 78)
    print("5. QUIZ BLUEPRINT")
    print("=" * 78)
    for index, blueprint in enumerate(result.blueprints, start=1):
        print(
            f"Q{index} [{blueprint.id}] {blueprint.slot_label}: concept={blueprint.concept} "
            f"target={blueprint.knowledge_target_id} skill={blueprint.cognitive_skill} "
            f"type={blueprint.question_type} difficulty={blueprint.difficulty} "
            f"pages={list(blueprint.pages)}"
        )

    print("\n" + "=" * 78)
    print("6. SELECTED QUESTIONS")
    print("=" * 78)
    print(f"provider={result.provider} model={result.model} fallback_used={result.fallback_used}")
    provenance = {item.question_id: item for item in result.provenance}
    for index, question in enumerate(result.questions, start=1):
        trace = provenance.get(question.id)
        print(f"\nQ{index} [{question.type}, {question.difficulty}] {question.prompt}")
        for option in question.options or []:
            marker = "*" if option == question.correct_answer else " "
            print(f"   {marker} {option}")
        if not question.options:
            print(f"   answer: {question.correct_answer}")
        print(f"   explanation: {question.explanation}")
        if trace:
            print(
                f"   concept_id={trace.concept_id}  knowledge_target_id={trace.knowledge_target_id}"
                f"  cognitive_skill={trace.cognitive_skill}  source_pages={list(trace.source_pages)}"
                f"  quality_score={trace.quality_score:.3f}"
            )

    concepts = {item.concept_id for item in result.provenance}
    skills = {item.cognitive_skill for item in result.provenance}

    # Tier mix: how much of the exam is reasoning versus terminology. An exam
    # that is mostly tier 3 is eight definitions wearing different wording,
    # which is the failure mode this pipeline exists to prevent.
    target_by_id = {target.target_id: target for target in result.knowledge_targets}
    tiers = {1: 0, 2: 0, 3: 0}
    for item in result.provenance:
        target = target_by_id.get(item.knowledge_target_id)
        if target is not None:
            tiers[target_tier(target)] += 1

    print("\n" + "=" * 78)
    print(
        f"COVERAGE: {len(result.questions)} questions across {len(concepts)} concepts "
        f"and {len(skills)} cognitive skills"
    )
    print(
        f"TIERS: reasoning={tiers[1]}  understanding={tiers[2]}  recall={tiers[3]}"
    )
    _ = os.environ
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
