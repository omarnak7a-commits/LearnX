#!/usr/bin/env python3
"""Drive the batched STEP 9 benchmark on a deployed LearnX instance.

The provider credentials never leave the server. This client holds only the
benchmark token, which authorises *triggering* a run and grants no access to
GEMINI_API_KEY or GROQ_API_KEY.

It simply calls the protected endpoints in a loop -- one bounded batch per
request -- until every ``(document, seed)`` pair has been measured, then fetches
the final report. Because progress lives in Postgres, this script can be
interrupted and re-run at any time without losing or repeating work.

    export BENCHMARK_TOKEN=...            # NOT a provider key
    python backend/scripts/run_remote_benchmark.py \
        --base-url https://learn-x-ofvm.vercel.app

    # resume an interrupted run
    python backend/scripts/run_remote_benchmark.py \
        --base-url https://... --run-id <id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="deployment origin")
    parser.add_argument("--api-prefix", default="/api/v1")
    parser.add_argument("--run-id", default="", help="resume an existing run")
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 3, 5, 7, 11])
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument(
        "--out", type=Path, default=Path("QUIZ_MSEMAX_AB.json")
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="per-batch HTTP timeout"
    )
    args = parser.parse_args()

    token = os.getenv("BENCHMARK_TOKEN", "").strip()
    if not token:
        print(
            "BENCHMARK_TOKEN is not set. This is the benchmark authorisation "
            "secret configured on the server -- NOT a provider API key.",
            file=sys.stderr,
        )
        return 2

    base = args.base_url.rstrip("/") + args.api_prefix
    headers = {"X-Benchmark-Token": token}

    with httpx.Client(timeout=args.timeout, headers=headers) as client:
        run_id = args.run_id
        if not run_id:
            response = client.post(
                f"{base}/benchmark/runs",
                json={"seeds": args.seeds, "count": args.count},
            )
            if response.status_code == 404:
                print(
                    "Benchmark routes are not mounted: BENCHMARK_TOKEN is not "
                    "configured on the server.",
                    file=sys.stderr,
                )
                return 3
            response.raise_for_status()
            progress = response.json()
            run_id = progress["run_id"]
            print(f"run {run_id}: {progress['total_batches']} batches")
        else:
            print(f"resuming run {run_id}")

        while True:
            response = client.post(f"{base}/benchmark/runs/{run_id}/next")
            if response.status_code >= 400:
                print(f"batch request failed: {response.status_code} {response.text}")
                return 4
            body = response.json()
            batch = body["batch"]
            progress = body["progress"]
            if batch is None:
                print("all batches complete")
                break
            state = batch["status"]
            if state == "pending":
                # Phrasing is bounded per request so the invocation cannot
                # overrun Vercel's limit; the unit continues on the next call.
                print(
                    f"  [..  ] {batch['document'][:28]:28s} s{batch['seed']:<3d} "
                    f"phrasing {batch.get('phrased_count', '?')}/"
                    f"{batch.get('blueprint_count', '?')} "
                    f"({progress['completed']}/{progress['total_batches']} units)"
                )
                continue
            marker = "ok " if state == "completed" else "FAIL"
            print(
                f"  [{marker}] {batch['document'][:28]:28s} s{batch['seed']:<3d} "
                f"baseline={batch['baseline_questions']}Q "
                f"msemax={batch['msemax_questions']}Q "
                f"accepted={batch['generations_accepted']}/"
                f"{batch['generations_requested']} "
                f"({progress['completed']}/{progress['total_batches']})"
            )
            if state != "completed" and batch.get("error"):
                print(f"        error: {batch['error'][:160]}")
            # A failed batch stays eligible; keep going and it is retried on a
            # later pass rather than aborting the whole run.
            if progress["remaining"] == 0:
                break
            time.sleep(0.2)

        report = client.get(f"{base}/benchmark/runs/{run_id}/report").json()

    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nreport written to {args.out}")

    if report.get("status") != "completed":
        print(f"STATUS: {report.get('status')} — {report.get('note', '')}")
        return 0

    baseline = report["baseline"]
    msemax = report["msemax"]
    print("\n" + "=" * 70)
    print(f"{'metric':28s} {'baseline':>12s} {'MSEMAX':>12s}")
    print("-" * 70)
    for label, key in [
        ("questions", "questions"),
        ("tier 1", "tier1"),
        ("scanner defects", "scanner_defects"),
        ("scanner warnings", "scanner_warnings"),
        ("candidate survival", "candidate_survival"),
        ("silent candidate loss", "silent_candidate_loss"),
    ]:
        print(f"{label:28s} {baseline[key]:>12} {msemax[key]:>12}")
    print("-" * 70)
    print(f"MSEMAX accepted : {msemax['generations_accepted']}"
          f"/{msemax['generations_requested']} (rate {msemax['valid_rate']})")
    print(f"provider errors : {msemax['provider_errors']}")
    if msemax["rejection_reasons"]:
        print(f"rejections      : {msemax['rejection_reasons']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
