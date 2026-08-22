"""Full human-review dump of the final quiz for one or more PDFs.

audit_quiz.py truncates evidence and omits per-option detail because it is a
pipeline diagnostic. This script exists for the opposite purpose: printing every
field a human reviewer needs to judge a question on its merits -- full evidence,
every distractor, the correct answer, difficulty, concept, knowledge target,
cognitive skill, source page and quality score -- with nothing shortened.

Usage:
    python backend/scripts/review_quiz.py --seeds 1 3 5
    python backend/scripts/review_quiz.py path/to/file.pdf --seeds 3
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ai_documents import _extract_pdf  # noqa: E402
from app.services.quiz_blueprints import target_tier  # noqa: E402
from app.services.quiz_pipeline import generate_quiz  # noqa: E402

DEMO_DIR = ROOT / "public" / "demo-files"
TIER_NAME = {1: "T1 reasoning", 2: "T2 understanding", 3: "T3 recall"}


class _NoProvider:
    def complete_structured(self, **_kwargs):  # noqa: ANN003
        from app.services.ai_service import AIServiceError

        raise AIServiceError("no provider configured")


def _wrap(text: str, indent: int = 22, width: int = 96) -> str:
    """Wrap long evidence so nothing is cut off."""
    import textwrap

    pad = " " * indent
    body = textwrap.fill(" ".join((text or "").split()), width=width)
    return body.replace("\n", "\n" + pad)


def review(pdf: Path, *, seed: int, count: int) -> dict[str, object]:
    source = _extract_pdf(
        pdf.read_bytes(),
        file_id=pdf.stem,
        title=pdf.stem,
        max_characters=200_000,
        allowed_pages=None,
    )
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
        system_prompt="Use only the supplied source.",
    )

    understanding = result.understanding
    blueprints = {bp.id: bp for bp in (result.blueprints or [])}
    prov = {t.question_id: t for t in (result.provenance or [])}

    print("=" * 98)
    print(f"{pdf.name}   seed={seed}   count requested={count}")
    print("=" * 98)
    print(
        f"provider={result.provider}  model={result.model}  "
        f"fallback_used={result.fallback_used}"
    )
    print()

    for index, question in enumerate(result.questions, start=1):
        trace = prov.get(question.id)
        bp = blueprints.get(trace.blueprint_id) if trace else None
        tier = TIER_NAME.get(target_tier(bp), "-") if bp is not None else "-"
        print(f"Q{index}. [{question.type}] [difficulty: {question.difficulty}]")
        print(f"    prompt          : {question.prompt}")
        if question.type == "mcq":
            print("    options         :")
            for option in question.options or []:
                mark = "CORRECT  " if option == question.correct_answer else "distractor"
                print(f"        [{mark}] {option}")
        elif question.type == "true-false":
            print(f"    options         : {question.options}")
            print(f"    correct answer  : {question.correct_answer}")
        else:
            print(f"    correct answer  : {question.correct_answer}")
        print(f"    concept         : {trace.concept if trace else '-'}"
              f" ({trace.concept_id if trace else '-'})")
        print(f"    knowledge target: {trace.knowledge_target if trace else '-'}")
        print(f"    cognitive skill : {trace.cognitive_skill if trace else '-'}"
              f"   tier: {tier}")
        print(f"    facet/relation  : {getattr(bp, 'facet_kind', '') or '-'}")
        print(f"    importance      : {getattr(bp, 'importance_reason', '') or '-'}")
        print(f"    source pages    : {question.source_pages}")
        print(f"    evidence        : {_wrap(bp.evidence if bp else '')}")
        print(f"    explanation     : {_wrap(question.explanation)}")
        if trace is not None:
            print(f"    quality score   : {trace.quality_score:.3f}")
        print()

    important = list(understanding.important_concepts()) if understanding else []
    tested = {t.concept_id for t in (result.provenance or [])}
    untested = [c for c in important if c.concept_id not in tested]

    tf = [q for q in result.questions if q.type == "true-false"]
    true_n = sum(1 for q in tf if q.correct_answer.strip().lower() == "true")

    print("-" * 98)
    print("COVERAGE")
    print(f"    important concepts  : {len(important)}")
    print(f"    concepts tested     : {len(tested)}")
    if untested:
        for c in untested:
            print(f"      NOT TESTED: {c.concept_id} (importance {c.importance:.3f})")
    tiers = Counter(
        target_tier(blueprints[t.blueprint_id])
        for t in (result.provenance or [])
        if t.blueprint_id in blueprints
    )
    print(f"    tiers               : T1={tiers.get(1,0)} T2={tiers.get(2,0)} T3={tiers.get(3,0)}")
    print(f"    cognitive skills    : "
          f"{dict(Counter(t.cognitive_skill for t in (result.provenance or [])))}")
    print(f"    question types      : {dict(Counter(q.type for q in result.questions))}")
    print(f"    T/F polarity        : True={true_n} False={len(tf)-true_n}")
    targets = [t.knowledge_target_id for t in (result.provenance or [])]
    print(f"    duplicate targets   : {len(targets) - len(set(targets))}")
    print()
    return {"questions": len(result.questions)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 3, 5])
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()

    pdfs = args.pdfs or sorted(DEMO_DIR.glob("*.pdf"))
    for pdf in pdfs:
        for seed in args.seeds:
            review(pdf, seed=seed, count=args.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
