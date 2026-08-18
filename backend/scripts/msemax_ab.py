#!/usr/bin/env python3
"""A/B benchmark: deterministic baseline vs MSEMAX-enabled generation.

    A = current engine, MSEMAX disabled   (reproducible, no network)
    B = current engine, MSEMAX enabled    (real provider, real model)

Both arms run the same documents, the same seeds, the same blueprints and the
same validation gates, so any difference is attributable to the generation
layer alone.

This harness never fabricates a result. It calls the real provider through the
existing AIService. If no credentials are configured it exits with status
``not_executed`` and a clear message rather than inventing numbers or
substituting canned responses.

    # baseline only (always runnable)
    .venv/bin/python backend/scripts/msemax_ab.py --baseline-only

    # full A/B (requires GEMINI_API_KEY or GROQ_API_KEY)
    MSEMAX_ENABLED=true GEMINI_API_KEY=... \
        .venv/bin/python backend/scripts/msemax_ab.py

Outputs a machine-readable JSON artefact and a human-readable summary.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.ai_documents import AIDocumentSource, _extract_pdf  # noqa: E402
from app.services.ai_service import AIService, AIServiceError  # noqa: E402
from app.services.quiz_msemax import MsemaxConfigurationError  # noqa: E402
from app.services.quiz_pipeline import generate_quiz  # noqa: E402

DEMO_DIR = ROOT / "public" / "demo-files"
CORPUS_DIR = ROOT / "backend" / "tests" / "fixtures" / "domain_corpus"
DEFAULT_SEEDS = (1, 3, 5, 7, 11)
ALL_TYPES = ["mcq", "true-false", "fill-blank", "short-answer"]


class _NoQuizProvider:
    """Blocks provider *quiz authoring* so both arms share one planner.

    The A/B question is "does MSEMAX phrase blueprints better than the
    deterministic writer?". Letting the provider also author whole quizzes in
    arm B would confound that with a different planning path, so quiz-level
    completion is refused in both arms; MSEMAX is reached through its own seam.
    """

    def complete_structured(self, **kwargs: Any) -> Any:
        raise AIServiceError("quiz authoring disabled for A/B comparison")


def load_source(doc: Path) -> AIDocumentSource:
    """Identical loading for both arms (mirrors adversarial_scan.load_source)."""
    if doc.suffix.lower() == ".pdf":
        return _extract_pdf(
            doc.read_bytes(),
            file_id=doc.stem,
            title=doc.stem,
            max_characters=200_000,
            allowed_pages=None,
        )
    paragraphs = [b.strip() for b in doc.read_text(encoding="utf-8").split("\n\n") if b.strip()]
    pages = [paragraphs[i : i + 2] for i in range(0, len(paragraphs), 2)]
    text = "\n\n".join(
        f"[Page {n}]\n" + "\n\n".join(block) for n, block in enumerate(pages, start=1)
    )
    return AIDocumentSource(
        file_id=doc.stem,
        title=doc.stem.replace("-", " ").title(),
        text=text,
        page_count=len(pages),
    )


@dataclass
class ArmMetrics:
    """Everything measured for one arm, aggregated over documents and seeds."""

    arm: str
    runs: int = 0
    failures: int = 0
    questions: int = 0
    concepts: set[str] = field(default_factory=set)
    tier1: int = 0
    tier2: int = 0
    blueprints: int = 0
    rejections_by_stage: Counter = field(default_factory=Counter)
    msemax_requested: int = 0
    msemax_generated: int = 0
    msemax_rejected: int = 0
    msemax_provider_errors: int = 0
    msemax_reasons: Counter = field(default_factory=Counter)
    scanner_defects: int = 0
    scanner_warnings: int = 0
    defect_kinds: Counter = field(default_factory=Counter)
    latencies: list[float] = field(default_factory=list)
    per_document: dict[str, int] = field(default_factory=dict)

    @property
    def candidate_survival(self) -> float:
        """Questions kept per candidate actually written."""
        return (
            round(self.questions / self.candidates_written, 4)
            if self.candidates_written
            else 0.0
        )

    #: Candidates that reached scoring, i.e. blueprints the writer could
    #: actually realise. Compared against questions+rejections to detect a
    #: candidate vanishing without a recorded reason.
    candidates_written: int = 0

    @property
    def silent_candidate_loss(self) -> int:
        """Written candidates that neither survived nor were rejected.

        Deliberately measured against *written candidates*, not planned
        blueprints: the planner over-plans on purpose (it proposes several
        angles per concept and lets scoring choose), so blueprints minus
        questions is expected slack rather than loss. A candidate that was
        written and then disappeared with no rejection note is the real bug,
        and that is what this counts.
        """
        accounted = self.questions + sum(self.rejections_by_stage.values())
        return max(0, self.candidates_written - accounted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "runs": self.runs,
            "failures": self.failures,
            "questions": self.questions,
            "unique_concepts": len(self.concepts),
            "tier1": self.tier1,
            "tier2": self.tier2,
            "blueprints_planned": self.blueprints,
            "candidates_written": self.candidates_written,
            "candidate_survival": self.candidate_survival,
            "silent_candidate_loss": self.silent_candidate_loss,
            "rejections_by_stage": dict(self.rejections_by_stage),
            "scanner_defects": self.scanner_defects,
            "scanner_warnings": self.scanner_warnings,
            "defect_kinds": dict(self.defect_kinds),
            "msemax": {
                "requested": self.msemax_requested,
                "generated": self.msemax_generated,
                "rejected": self.msemax_rejected,
                "provider_errors": self.msemax_provider_errors,
                "valid_rate": (
                    round(self.msemax_generated / self.msemax_requested, 4)
                    if self.msemax_requested
                    else None
                ),
                "rejection_reasons": dict(self.msemax_reasons),
            },
            "latency_seconds": {
                "total": round(sum(self.latencies), 3),
                "mean": round(statistics.fmean(self.latencies), 3) if self.latencies else 0.0,
                "max": round(max(self.latencies), 3) if self.latencies else 0.0,
            },
            "per_document_questions": self.per_document,
        }


def run_arm(
    *,
    arm: str,
    documents: list[Path],
    seeds: tuple[int, ...],
    count: int,
    msemax_enabled: bool,
    service: Any,
    scanner: Any,
) -> ArmMetrics:
    metrics = ArmMetrics(arm=arm)
    for document in documents:
        source = load_source(document)
        for seed in seeds:
            metrics.runs += 1
            started = time.perf_counter()
            try:
                result = generate_quiz(
                    service,
                    source,
                    count=count,
                    question_types=ALL_TYPES,
                    difficulty="mixed",
                    kind="practice",
                    language="en",
                    seed=seed,
                    previous_questions=[],
                    system_prompt="Benchmark run.",
                    msemax_enabled=msemax_enabled,
                )
            except MsemaxConfigurationError:
                raise
            except Exception as exc:  # a run that cannot produce a quiz at all
                metrics.failures += 1
                print(f"  {document.stem[:26]:26s} s{seed:<3d} FAILED: {exc}")
                continue
            finally:
                metrics.latencies.append(time.perf_counter() - started)

            metrics.questions += len(result.questions)
            metrics.blueprints += len(result.blueprints)
            # A written candidate is one that survived the writer: it either
            # became a question or carries a rejection note from a later stage.
            metrics.candidates_written += len(result.questions) + len(result.rejections)
            metrics.per_document[f"{document.stem}#s{seed}"] = len(result.questions)
            for note in result.rejections:
                metrics.rejections_by_stage[note.stage] += 1
            if result.understanding is not None:
                for concept in result.understanding.important_concepts():
                    metrics.concepts.add(f"{document.stem}:{concept.concept_id}")
            stats = result.msemax_stats
            if stats is not None:
                metrics.msemax_requested += stats.requested
                metrics.msemax_generated += stats.generated
                metrics.msemax_rejected += stats.rejected
                metrics.msemax_provider_errors += stats.provider_errors
                for reason, hits in stats.reasons.items():
                    metrics.msemax_reasons[reason] += hits

            findings = scanner(result)
            for severity, _where, message in findings:
                key = message.split(":")[0]
                if severity == "DEFECT":
                    metrics.scanner_defects += 1
                    metrics.defect_kinds[key] += 1
                else:
                    metrics.scanner_warnings += 1

            tier1, tier2 = _tier_counts(result)
            metrics.tier1 += tier1
            metrics.tier2 += tier2
            print(
                f"  {document.stem[:26]:26s} s{seed:<3d} "
                f"{len(result.questions)}Q  defects={sum(1 for f in findings if f[0] == 'DEFECT')}"
            )
    return metrics


def _tier_counts(result: Any) -> tuple[int, int]:
    from app.services.quiz_blueprints import target_tier

    by_id = {blueprint.id: blueprint for blueprint in result.blueprints}
    tier1 = tier2 = 0
    for trace in result.provenance:
        blueprint = by_id.get(getattr(trace, "blueprint_id", ""))
        if blueprint is None:
            continue
        tier = target_tier(blueprint)
        if tier == 1:
            tier1 += 1
        elif tier == 2:
            tier2 += 1
    return tier1, tier2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="run arm A only; never contacts a provider",
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT / "QUIZ_MSEMAX_AB.json"
    )
    args = parser.parse_args()

    documents = sorted(DEMO_DIR.glob("*.pdf")) + sorted(CORPUS_DIR.glob("*.txt"))
    seeds = tuple(args.seeds)

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_adv_scan", ROOT / "backend" / "scripts" / "adversarial_scan.py"
    )
    scan_module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(scan_module)
    scanner = scan_module.inspect_quiz

    settings = get_settings()
    has_credentials = bool(
        (settings.gemini_api_key or "").strip() or (settings.groq_api_key or "").strip()
    )

    report: dict[str, Any] = {
        "configuration": {
            "documents": [doc.name for doc in documents],
            "seeds": list(seeds),
            "count": args.count,
            "question_types": ALL_TYPES,
            "provider_primary": settings.ai_provider,
            "provider_fallback": settings.ai_fallback_provider,
            "gemini_model": settings.gemini_model,
            "groq_model": settings.groq_model,
            "credentials_present": has_credentials,
        }
    }

    print("=" * 78)
    print("ARM A — deterministic baseline (MSEMAX disabled)")
    print("=" * 78)
    baseline = run_arm(
        arm="baseline",
        documents=documents,
        seeds=seeds,
        count=args.count,
        msemax_enabled=False,
        service=_NoQuizProvider(),
        scanner=scanner,
    )
    report["baseline"] = baseline.to_dict()

    if args.baseline_only:
        report["msemax"] = {"status": "not_executed", "reason": "--baseline-only"}
    elif not has_credentials:
        # Explicitly NOT executed. No fake backend, no invented numbers.
        report["msemax"] = {
            "status": "not_executed",
            "reason": (
                "provider credentials missing: set GEMINI_API_KEY or GROQ_API_KEY "
                "to run the MSEMAX arm"
            ),
        }
        print()
        print("ARM B — MSEMAX: NOT EXECUTED (provider credentials missing)")
        print("       Set GEMINI_API_KEY or GROQ_API_KEY and re-run.")
    else:
        print()
        print("=" * 78)
        print("ARM B — MSEMAX enabled (real provider)")
        print("=" * 78)
        try:
            experimental = run_arm(
                arm="msemax",
                documents=documents,
                seeds=seeds,
                count=args.count,
                msemax_enabled=True,
                service=AIService(settings),
                scanner=scanner,
            )
            report["msemax"] = {"status": "executed", **experimental.to_dict()}
            report["comparison"] = _compare(baseline, experimental)
        except MsemaxConfigurationError as exc:
            report["msemax"] = {"status": "not_executed", "reason": str(exc)}
            print(f"ARM B — NOT EXECUTED: {exc}")

    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _print_summary(report)
    print(f"\nMachine-readable results: {args.out}")
    return 0


def _compare(baseline: ArmMetrics, experimental: ArmMetrics) -> dict[str, Any]:
    """Deltas only; the verdict is left to a human reading them."""
    return {
        "questions_delta": experimental.questions - baseline.questions,
        "unique_concepts_delta": len(experimental.concepts) - len(baseline.concepts),
        "tier1_delta": experimental.tier1 - baseline.tier1,
        "scanner_defects_delta": experimental.scanner_defects - baseline.scanner_defects,
        "scanner_warnings_delta": experimental.scanner_warnings - baseline.scanner_warnings,
        "candidate_survival_delta": round(
            experimental.candidate_survival - baseline.candidate_survival, 4
        ),
        "latency_multiple": (
            round(sum(experimental.latencies) / sum(baseline.latencies), 2)
            if sum(baseline.latencies)
            else None
        ),
        "verdict_rule": (
            "MSEMAX is an improvement only if defects do not increase AND "
            "coverage (questions, concepts, tier 1) does not decrease."
        ),
    }


def _print_summary(report: dict[str, Any]) -> None:
    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    baseline = report["baseline"]
    print(
        f"baseline : {baseline['questions']}Q  "
        f"concepts={baseline['unique_concepts']}  tier1={baseline['tier1']}  "
        f"defects={baseline['scanner_defects']}  warnings={baseline['scanner_warnings']}  "
        f"survival={baseline['candidate_survival']}  "
        f"silent_loss={baseline['silent_candidate_loss']}"
    )
    msemax = report.get("msemax", {})
    if msemax.get("status") != "executed":
        print(f"msemax   : NOT EXECUTED — {msemax.get('reason')}")
        return
    print(
        f"msemax   : {msemax['questions']}Q  "
        f"concepts={msemax['unique_concepts']}  tier1={msemax['tier1']}  "
        f"defects={msemax['scanner_defects']}  warnings={msemax['scanner_warnings']}  "
        f"survival={msemax['candidate_survival']}  "
        f"silent_loss={msemax['silent_candidate_loss']}"
    )
    print(f"msemax valid rate: {msemax['msemax']['valid_rate']}")
    for key, value in report.get("comparison", {}).items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
