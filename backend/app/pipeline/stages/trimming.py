"""
Smart lecture trimming — produces the "AI Optimized" video from the
original + the classified silence segments.

Real approach:
  1. Take `ctx.silence_segments` where `removed=True` from
     `silence_detection.py` (after its transcript-aware refinement pass).
  2. Build the complementary list of "keep" segments (everything NOT
     removed).
  3. Use ffmpeg's `concat` demuxer (or `select`/`atrim` filtergraph for a
     single-pass cut, which avoids re-encoding artifacts at each splice
     point) to produce the optimized MP4:

       ffmpeg -i original.mp4 -filter_complex
         "[0:v]select='between(t,{k1s},{k1e})+between(t,{k2s},{k2e})+...'..."
         optimized.mp4

  4. Re-derive chapter/transcript timestamps for the OPTIMIZED timeline by
     accumulating the duration of each kept segment — this mapping is
     also what the frontend's `VideoPlayer` "skip removed silence" logic
     in `optimized` mode would consume once wired to a real optimized
     video file (currently it's simulated purely client-side against the
     *original* timeline, since no rendered optimized video exists in
     this environment).
  5. Compute the final stats block (`VideoStatsOut`): original/optimized
     duration, minutes saved, percent removed, and a learning efficiency
     score (a weighted function of percent-removed, chapter confidence,
     and exam-importance coverage — see `app/services/stats.py`).
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "trimming"


def run(ctx: PipelineContext) -> PipelineContext:
    if not ctx.silence_segments:
        raise RuntimeError("trimming requires silence_segments — run silence_detection.py first")

    keep_segments = _invert_removed_segments(ctx.silence_segments, ctx.metadata.get("duration_sec", 0.0))

    # TODO(real impl): build and run the ffmpeg filtergraph described in
    # the module docstring, writing to
    # ctx.workdir / f"{ctx.lecture_id}-optimized.mp4", then set
    # ctx.optimized_video_path to that path and upload it via
    # app/services/storage.py.

    raise NotImplementedError(
        f"Reference stub — {len(keep_segments)} segments would be kept and stitched via ffmpeg. "
        "See module docstring for the real implementation plan."
    )


def _invert_removed_segments(
    silence_segments: list[dict], total_duration: float
) -> list[tuple[float, float]]:
    removed = sorted(
        [(s["start_sec"], s["end_sec"]) for s in silence_segments if s["removed"]]
    )
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in removed:
        if start > cursor:
            keep.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total_duration:
        keep.append((cursor, total_duration))
    return keep
