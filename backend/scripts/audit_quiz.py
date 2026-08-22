"""Adversarial quality audit for the quiz pipeline.

Unlike ``inspect_quiz.py``, which shows the surviving quiz, this harness reports
the *whole* pipeline for one or more real PDFs:

    PDF -> understanding -> concepts -> importance -> knowledge targets
        -> blueprints -> candidates -> validation -> scoring -> dedup
        -> diversity selection -> final quiz

and — crucially — every rejected candidate together with the reason it was
dropped. That is what makes it possible to tell whether a weak question was
generated wrongly, scored wrongly, or selected wrongly, instead of guessing.

Usage:
    python backend/scripts/audit_quiz.py                     # all demo PDFs
    python backend/scripts/audit_quiz.py --seed 7 --count 8
    python backend/scripts/audit_quiz.py path/to/file.pdf
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ai_documents import _extract_pdf  # noqa: E402
from app.services.ai_service import AIUnavailableError  # noqa: E402
from app.services.quiz_blueprints import target_tier  # noqa: E402
from app.services.quiz_pipeline import generate_quiz  # noqa: E402

DEMO_DIR = ROOT / "public" / "demo-files"
TIER_NAME = {1: "T1 reasoning", 2: "T2 understanding", 3: "T3 recall"}


class _NoProvider:
    """Forces the deterministic path so the audit is reproducible."""

    def complete_structured(self, **_kwargs):  # noqa: ANN003
        from app.services.ai_service import AIServiceError

        raise AIServiceError("no provider configured")


def _rule(char: str = "=") -> str:
    return char * 78


def audit(pdf: Path, *, seed: int, count: int) -> dict[str, object]:
    data = pdf.read_bytes()
    source = _extract_pdf(
        data,
        file_id=pdf.stem,
        title=pdf.stem,
        max_characters=200_000,
        allowed_pages=None,
    )

    print("\n" + _rule())
    print(f"DOCUMENT: {pdf.name}   (seed={seed}, requested count={count})")
    print(_rule())

    try:
        result = generate_quiz(
            _NoProvider(),
            source,
            count=count,
            question_types=["mcq", "true-false", "fill-blank", "short-answer"],
            difficulty="mixed",
            kind="practice",
            language="en",
            seed=seed,
            previous_questions=[],
            system_prompt="You are LearnX.",
        )
    except AIUnavailableError as exc:
        print(f"\nUNAVAILABLE: {exc}")
        return {"pdf": pdf.name, "questions": 0, "unavailable": True}

    understanding = result.understanding
    assert understanding is not None

    # ---------------------------------------------------------------- 1
    print("\n1. DOCUMENT UNDERSTANDING")
    print(_rule("-"))
    print(f"subject : {understanding.subject}")
    print(f"summary : {understanding.summary[:300]}")
    topic_names = [topic.name for topic in understanding.main_topics]
    print(f"topics  : {', '.join(topic_names) or '(none)'}")
    print(f"objectives ({len(understanding.learning_objectives)}):")
    for objective in understanding.learning_objectives[:6]:
        print(f"   - {objective}")

    # ---------------------------------------------------------------- 2
    print("\n2. CONCEPTS BY IMPORTANCE (central vs supporting vs excluded)")
    print(_rule("-"))
    important = understanding.important_concepts()
    important_ids = {concept.concept_id for concept in important}
    for concept in important:
        facets = ",".join(sorted({facet.kind for facet in concept.facets})) or "-"
        print(
            f"   {concept.importance:5.3f}  {concept.concept_id:38s} "
            f"{concept.knowledge_type:12s} facets={facets}"
        )
    excluded = [c for c in understanding.concepts if c.concept_id not in important_ids]
    if excluded:
        print(f"   --- excluded ({len(excluded)}): "
              + ", ".join(f"{c.concept_id}({c.importance:.2f})" for c in excluded[:12]))

    # ---------------------------------------------------------------- 3
    print("\n3. KNOWLEDGE TARGETS")
    print(_rule("-"))
    for target in result.knowledge_targets:
        print(
            f"   T{target_tier(target)} {target.concept_id:34s} "
            f"{target.cognitive_skill:14s} facet={target.facet_kind or '-'}"
        )

    # ---------------------------------------------------------------- 4
    print("\n4. BLUEPRINTS PLANNED")
    print(_rule("-"))
    for blueprint in result.blueprints:
        print(
            f"   {blueprint.id:12s} {blueprint.concept_id:34s} "
            f"{blueprint.cognitive_skill:14s} {blueprint.question_type}"
        )

    # ---------------------------------------------------------------- 5
    print("\n5. REJECTED CANDIDATES (why each was dropped)")
    print(_rule("-"))
    if not result.rejections:
        print("   (none)")
    for note in result.rejections:
        print(f"   [{note.stage}] {note.concept_id or '?'} / {note.cognitive_skill or '?'}")
        print(f"       prompt: {note.prompt[:96]}")
        print(f"       reason: {note.reason}")

    # ---------------------------------------------------------------- 6
    print("\n6. FINAL QUIZ")
    print(_rule("-"))
    print(f"provider={result.provider} model={result.model} fallback={result.fallback_used}")
    target_by_id = {t.target_id: t for t in result.knowledge_targets}
    concept_by_id = {c.concept_id: c for c in understanding.concepts}
    tiers: Counter[int] = Counter()

    for index, (question, trace) in enumerate(zip(result.questions, result.provenance), 1):
        target = target_by_id.get(trace.knowledge_target_id)
        tier = target_tier(target) if target else 0
        tiers[tier] += 1
        concept = concept_by_id.get(trace.concept_id)
        print(f"\nQ{index} [{question.type}, {question.difficulty}] {question.prompt}")
        if question.options:
            for option in question.options:
                mark = "*" if option == question.correct_answer else " "
                print(f"     {mark} {option}")
        else:
            print(f"     answer: {question.correct_answer}")
        print(f"     concept        : {trace.concept} ({trace.concept_id})")
        print(f"     knowledge target: {trace.knowledge_target}")
        print(f"     cognitive skill : {trace.cognitive_skill}   tier: {TIER_NAME.get(tier, '?')}")
        print(f"     source pages    : {trace.source_pages}")
        if concept is not None:
            print(f"     evidence        : {concept.primary_evidence[:150]}")
            print(f"     why it matters  : importance {concept.importance:.3f}")
        print(f"     quality score   : {trace.quality_score:.3f}")

    # ---------------------------------------------------------------- 7
    print("\n7. STATISTICS")
    print(_rule("-"))
    concepts = [t.concept_id for t in result.provenance]
    targets = [t.knowledge_target_id for t in result.provenance]
    skills = [t.cognitive_skill for t in result.provenance]
    print(f"   questions            : {len(result.questions)} (requested {count})")
    print(f"   distinct concepts    : {len(set(concepts))} / {len(concepts)}")
    print(f"   distinct targets     : {len(set(targets))} / {len(targets)}")
    print(f"   duplicate targets    : {len(targets) - len(set(targets))}")
    print(f"   cognitive skills     : {len(set(skills))} -> {sorted(set(skills))}")
    print(f"   tiers                : T1={tiers[1]} T2={tiers[2]} T3={tiers[3]}")
    print(f"   rejected candidates  : {len(result.rejections)}")

    return {
        "pdf": pdf.name,
        "questions": len(result.questions),
        "concepts": len(set(concepts)),
        "dupe_targets": len(targets) - len(set(targets)),
        "t1": tiers[1],
        "t2": tiers[2],
        "t3": tiers[3],
        "rejections": len(result.rejections),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()

    pdfs = args.pdfs or sorted(DEMO_DIR.glob("*.pdf"))
    rows = [audit(pdf, seed=args.seed, count=args.count) for pdf in pdfs]

    print("\n" + _rule())
    print("SUMMARY")
    print(_rule())
    header = f"{'document':38s} {'Q':>2s} {'concepts':>8s} {'dupes':>5s} {'T1':>3s} {'T2':>3s} {'T3':>3s} {'rej':>4s}"
    print(header)
    for row in rows:
        if row.get("unavailable"):
            print(f"{row['pdf']:38s}  UNAVAILABLE")
            continue
        print(
            f"{row['pdf']:38s} {row['questions']:2d} {row['concepts']:8d} "
            f"{row['dupe_targets']:5d} {row['t1']:3d} {row['t2']:3d} {row['t3']:3d} "
            f"{row['rejections']:4d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
