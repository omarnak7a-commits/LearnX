"""Persistence for the MSEMAX A/B benchmark (STEP 9).

Why this table exists
---------------------
The full STEP 9 benchmark needs ~485 sequential provider calls. That cannot run
inside one Vercel invocation (10s default, 300s ceiling even on Pro), and a
serverless filesystem is ephemeral, so partial results written to disk would be
lost between invocations. Progress therefore lives in the Postgres database the
project already uses — no new infrastructure, no new dependency.

The unit of work is one ``(document, seed)`` pair. Measured worst case for a
single pair is 16 provider calls, which fits comfortably inside one invocation,
and the 8-document x 5-seed matrix gives exactly 40 such batches.

What is stored
--------------
Only non-sensitive measurement metadata: identifiers, counts, defect totals,
latency, provider *names* and *model names*, and error categories.

**No API key, token, or credential is ever written here.** The provider secrets
stay in the Vercel environment and are read by AIService at call time; nothing
in this module can observe them.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


#: Batch lifecycle. A batch is only ever counted once it is ``completed``, so a
#: retry of a failed or interrupted batch can never double-count results.
BATCH_PENDING = "pending"
BATCH_RUNNING = "running"
BATCH_COMPLETED = "completed"
BATCH_FAILED = "failed"


class BenchmarkRun(Base):
    """One STEP 9 execution: its methodology, configuration and progress."""

    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)

    # Methodology is recorded with the run so a report can never be read
    # without knowing exactly what produced it. Changing seeds or count starts
    # a different run rather than silently altering an existing one.
    seeds: Mapped[str] = mapped_column(String(128))
    count: Mapped[int] = mapped_column(Integer)
    documents: Mapped[list] = mapped_column(JSON, default=list)

    # Provider/model NAMES only — never credentials.
    provider_primary: Mapped[str] = mapped_column(String(32), default="")
    provider_fallback: Mapped[str] = mapped_column(String(32), default="")
    gemini_model: Mapped[str] = mapped_column(String(64), default="")
    groq_model: Mapped[str] = mapped_column(String(64), default="")

    total_batches: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BenchmarkBatch(Base):
    """One ``(document, seed)`` pair, measured for both arms.

    Both arms are evaluated inside the same batch so the control and the
    experiment always see the identical document, seed, blueprints, validators
    and scanner. Storing them separately would allow the two arms to drift.
    """

    __tablename__ = "benchmark_batches"
    __table_args__ = (
        # The resumability guarantee, enforced by the database rather than by
        # application logic: a given (run, document, seed) can exist only once,
        # so a retried or concurrent request cannot create a duplicate.
        UniqueConstraint("run_id", "document", "seed", name="uq_benchmark_batch_unit"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(64), index=True)

    document: Mapped[str] = mapped_column(String(128))
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=BATCH_PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    #: How many of this unit's blueprints have been phrased so far. A single
    #: Vercel invocation cannot phrase all ~16 blueprints of a unit (one
    #: provider call can alone consume the whole 10-15s budget), so phrasing is
    #: advanced a few blueprints at a time and this records the high-water mark.
    #: The unit only moves to `completed` once phrasing is finished AND both
    #: arms have been measured.
    phrased_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Total blueprints in this unit, discovered on the first pass.
    blueprint_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- deterministic arm (control) ---
    baseline_questions: Mapped[int] = mapped_column(Integer, default=0)
    baseline_concepts: Mapped[int] = mapped_column(Integer, default=0)
    baseline_tier1: Mapped[int] = mapped_column(Integer, default=0)
    baseline_defects: Mapped[int] = mapped_column(Integer, default=0)
    baseline_warnings: Mapped[int] = mapped_column(Integer, default=0)
    baseline_candidates: Mapped[int] = mapped_column(Integer, default=0)
    baseline_rejections: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_defect_kinds: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_latency: Mapped[float] = mapped_column(Float, default=0.0)

    # --- MSEMAX arm (experiment) ---
    msemax_questions: Mapped[int] = mapped_column(Integer, default=0)
    msemax_concepts: Mapped[int] = mapped_column(Integer, default=0)
    msemax_tier1: Mapped[int] = mapped_column(Integer, default=0)
    msemax_defects: Mapped[int] = mapped_column(Integer, default=0)
    msemax_warnings: Mapped[int] = mapped_column(Integer, default=0)
    msemax_candidates: Mapped[int] = mapped_column(Integer, default=0)
    msemax_rejections: Mapped[dict] = mapped_column(JSON, default=dict)
    msemax_defect_kinds: Mapped[dict] = mapped_column(JSON, default=dict)
    msemax_latency: Mapped[float] = mapped_column(Float, default=0.0)

    # --- MSEMAX provider accounting ---
    generations_requested: Mapped[int] = mapped_column(Integer, default=0)
    generations_accepted: Mapped[int] = mapped_column(Integer, default=0)
    provider_errors: Mapped[int] = mapped_column(Integer, default=0)
    #: Rejection reason -> count. Categories only ("provider error",
    #: "unsupported content", ...), never raw provider payloads.
    rejection_reasons: Mapped[dict] = mapped_column(JSON, default=dict)

    #: Why a batch failed, as a short category plus message. Provider errors are
    #: recorded verbatim only as far as their type/message; the AIService never
    #: includes credentials in an exception.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BenchmarkPhrasing(Base):
    """One MSEMAX phrasing, cached so a unit can be completed across requests.

    Why this exists
    ---------------
    Measuring a ``(document, seed)`` unit needs every one of its blueprints
    phrased, but ~16 sequential provider calls cannot fit in a Vercel
    invocation. Each request therefore phrases only as many blueprints as its
    time budget allows and stores the results here; once the whole unit is
    covered, a final request replays these rows -- making **zero** provider
    calls -- and measures both arms.

    That keeps the methodology identical to the offline harness: the same
    blueprints get the same MSEMAX prose, merely produced across several
    invocations instead of one long one.

    Stores generated prose and rejection *reasons* only. No credential, prompt
    key, or provider secret is ever written here.
    """

    __tablename__ = "benchmark_phrasings"
    __table_args__ = (
        # Each blueprint is phrased at most once per unit: the resume guarantee
        # at blueprint granularity, enforced by the database.
        UniqueConstraint(
            "batch_id", "blueprint_id", name="uq_benchmark_phrasing_blueprint"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    blueprint_id: Mapped[str] = mapped_column(String(64))

    #: The accepted candidate dict, or NULL when MSEMAX declined this blueprint.
    candidate: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Populated instead of ``candidate`` when the generation was rejected.
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    concept_id: Mapped[str] = mapped_column(String(128), default="")
    cognitive_skill: Mapped[str] = mapped_column(String(32), default="")
    #: Wall time of this single provider call, for latency reporting.
    latency: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
