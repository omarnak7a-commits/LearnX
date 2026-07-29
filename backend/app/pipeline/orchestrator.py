"""
Pipeline orchestrator.

Runs every stage in `app/pipeline/stages/` in the exact order defined by
the product spec (and mirrored in
`src/data/videoIntelligenceMock.ts::PIPELINE_STAGE_DEFS`), persisting
`PipelineStage` progress after each step so:

  1. A crashed Celery worker can resume from the last completed stage
     instead of restarting the whole (potentially hour-long) pipeline.
  2. The frontend's WebSocket progress subscription
     (`app/api/websockets.py`) can push live updates that map directly
     onto `PipelineTimeline.tsx` without any client-side translation.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict

from app.pipeline.stage import PipelineContext
from app.pipeline.stages import (
    audio_extraction,
    chaptering,
    diarization,
    generation,
    ocr,
    scene_detection,
    silence_detection,
    transcription,
    trimming,
    vad,
)

# Order matches PIPELINE_STAGE_DEFS in the frontend mock data exactly.
# `virus_scan` and `metadata` are intentionally omitted here — they are
# infra/validation steps handled in app/services/validation.py before a
# lecture ever reaches the AI pipeline, not "stages" with reusable
# PipelineContext transforms.
STAGE_ORDER: list[Callable[[PipelineContext], PipelineContext]] = [
    audio_extraction.run,
    vad.run,
    diarization.run,
    silence_detection.run,
    scene_detection.run,
    ocr.run,
    transcription.run,
    chaptering.run,
    generation.run,
    trimming.run,
]


def run_pipeline(
    ctx: PipelineContext,
    on_progress: Callable[[str, float], None] | None = None,
) -> PipelineContext:
    """
    Executes every stage in order. `on_progress(stage_id, pct)` is called
    after each stage completes so a caller (typically the Celery task in
    `app/workers/video_pipeline.py`) can persist state and publish a
    WebSocket update.
    """

    for i, stage_fn in enumerate(STAGE_ORDER):
        stage_id = getattr(stage_fn.__module__, "STAGE_ID", stage_fn.__module__.split(".")[-1])
        started = time.monotonic()

        ctx = stage_fn(ctx)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        if on_progress:
            on_progress(stage_id, (i + 1) / len(STAGE_ORDER) * 100)

        # TODO(real impl): persist ctx + elapsed_ms to the DB/cache here
        # so a resumed worker can skip already-completed stages.
        _ = elapsed_ms

    return ctx


def context_to_dict(ctx: PipelineContext) -> dict:
    """Serializes the working context for checkpointing between stages."""
    data = asdict(ctx)
    data["original_video_path"] = str(ctx.original_video_path)
    data["workdir"] = str(ctx.workdir)
    if ctx.audio_path:
        data["audio_path"] = str(ctx.audio_path)
    if ctx.optimized_video_path:
        data["optimized_video_path"] = str(ctx.optimized_video_path)
    return data
