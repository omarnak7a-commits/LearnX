"""Protected STEP 9 benchmark control endpoints.

These exist so the MSEMAX A/B benchmark can use the provider credentials that
already live in the Vercel environment, without copying them anywhere. The
server reads them exactly as it does for normal AI traffic; the benchmark
caller never sees, sends, or needs them.

Security posture
----------------
* The router is registered ONLY when ``BENCHMARK_TOKEN`` is configured. With no
  token set -- the default, including today's production -- these routes do not
  exist at all and return 404.
* Every request must present that token in ``X-Benchmark-Token``, compared with
  ``secrets.compare_digest`` to avoid a timing side channel.
* ``BENCHMARK_TOKEN`` is a separate credential. It is never a provider key, and
  the provider keys are never read, returned, or logged here.
* Nothing is exposed to the frontend: no UI, no unauthenticated route, and the
  responses contain only measurement metadata.

Why endpoints instead of one long request
-----------------------------------------
The full benchmark is ~485 provider calls. A single invocation cannot survive
that inside Vercel's limits, so work advances one ``(document, seed)`` batch at
a time -- worst case 16 provider calls -- with progress in Postgres.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.models.benchmark import BATCH_COMPLETED, BenchmarkBatch, BenchmarkRun
from app.services.ai_service import AIService, get_ai_service
from app.services.benchmark_runner import (
    DEFAULT_COUNT,
    DEFAULT_SEEDS,
    BenchmarkError,
    build_report,
    create_run,
    run_batch,
    run_progress,
)
from app.services.quiz_msemax import MsemaxConfigurationError

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


def require_benchmark_token(
    x_benchmark_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """Authorise a benchmark request.

    Deliberately strict: an unset token means the feature is off, not open.
    """
    expected = (getattr(settings, "benchmark_token", "") or "").strip()
    if not expected:
        # Should be unreachable (the router is not mounted), but a defence in
        # depth against a future refactor accidentally exposing it.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    provided = (x_benchmark_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or missing benchmark token"
        )


class StartRequest(BaseModel):
    """Methodology is fixed by default; overriding it starts a *different* run."""

    seeds: list[int] = Field(default_factory=lambda: list(DEFAULT_SEEDS))
    count: int = DEFAULT_COUNT


@router.post("/runs", dependencies=[Depends(require_benchmark_token)])
def start_run(
    payload: StartRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Create a run and materialise its full batch matrix."""
    body = payload or StartRequest()
    try:
        run = create_run(
            db,
            settings=settings,
            seeds=tuple(body.seeds),
            count=body.count,
        )
    except BenchmarkError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return run_progress(db, run)


def _load_run(db: Session, run_id: str) -> BenchmarkRun:
    run = db.query(BenchmarkRun).filter(BenchmarkRun.id == run_id).first()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark run not found")
    return run


@router.post("/runs/{run_id}/next", dependencies=[Depends(require_benchmark_token)])
def advance_run(
    run_id: str,
    db: Session = Depends(get_db),
    service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    """Execute the next outstanding batch.

    Idempotent by construction: batches are claimed under a row lock and only
    ``pending``/``failed`` ones are eligible, so calling this repeatedly (or
    concurrently) advances the run without ever re-measuring a completed pair.
    """
    run = _load_run(db, run_id)
    try:
        batch = run_batch(db, run, service=service)
    except MsemaxConfigurationError as exc:
        # Provider not configured for this deployment: an operator error.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    progress = run_progress(db, run)
    if batch is None:
        if run.status != BATCH_COMPLETED:
            run.status = "completed"
            db.commit()
        return {"batch": None, "progress": progress, "message": "no batches remaining"}

    return {
        "batch": {
            "id": batch.id,
            "document": batch.document,
            "seed": batch.seed,
            "status": batch.status,
            "attempts": batch.attempts,
            "phrased_count": batch.phrased_count,
            "blueprint_count": batch.blueprint_count,
            "baseline_questions": batch.baseline_questions,
            "msemax_questions": batch.msemax_questions,
            "generations_requested": batch.generations_requested,
            "generations_accepted": batch.generations_accepted,
            "provider_errors": batch.provider_errors,
            "error": batch.error,
        },
        "progress": progress,
    }


@router.get("/runs/{run_id}", dependencies=[Depends(require_benchmark_token)])
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Progress plus per-batch status; no A/B numbers until the run finishes."""
    run = _load_run(db, run_id)
    batches = (
        db.query(BenchmarkBatch)
        .filter(BenchmarkBatch.run_id == run.id)
        .order_by(BenchmarkBatch.document, BenchmarkBatch.seed)
        .all()
    )
    return {
        "progress": run_progress(db, run),
        "batches": [
            {
                "document": batch.document,
                "seed": batch.seed,
                "status": batch.status,
                "attempts": batch.attempts,
                "error": batch.error,
            }
            for batch in batches
        ],
    }


@router.get("/runs/{run_id}/report", dependencies=[Depends(require_benchmark_token)])
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The STEP 9 report, once every batch has genuinely completed."""
    run = _load_run(db, run_id)
    return build_report(db, run)
