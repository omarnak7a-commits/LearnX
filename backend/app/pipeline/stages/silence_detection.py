"""
Silence detection & classification — one of the platform's core
differentiators (see product spec § Smart Silence Removal).

Real approach
-------------
1. Run Silero VAD (or reuse the VAD stage's output — see
   `app/pipeline/stages/vad.py`) to get raw speech/non-speech segments.
2. For every non-speech gap longer than
   `settings.silence_min_removable_seconds`, classify *why* it's silent
   using cheap signal-level heuristics before ever calling an LLM:
     - Position in the lecture (first 30s => likely "setup-time")
     - Preceding/following scene change from `scene_detection.py`
       (silence right after a slide change => likely the presenter is
       reading/waiting => more likely removable)
     - Audio energy profile during the gap (near-total silence vs. faint
       ambient/room noise => "dead-air" vs. "idle-moment")
     - Repetition — multiple similar-length gaps close together => flag
       as "repeated-pause" (e.g. presenter repeatedly waiting for
       questions with no response)
3. Any gap shorter than `settings.meaningful_pause_max_seconds` that
   falls *between* two segments the diarization stage attributes to the
   *same* speaker, and where the surrounding transcript looks like an
   unfinished sentence (checked once transcription is available, so this
   stage's classification is revisited/refined after `transcription.py`
   runs) is reclassified as "meaningful-pause" and is NEVER removed —
   this directly implements the spec's "never remove thinking pauses"
   requirement.
4. Only segments still flagged as dead-air/setup-time/waiting/idle after
   that pass are marked `removed=True` and handed to `trimming.py`.

This two-pass design (cheap heuristic pass now, transcript-aware
refinement later) is what lets the system distinguish "the professor is
thinking" from "the professor stepped out to find a marker" without
requiring a full LLM call for every single gap in the lecture.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.pipeline.stage import PipelineContext

STAGE_ID = "silence-detection"

settings = get_settings()


def run(ctx: PipelineContext) -> PipelineContext:
    if not ctx.vad_segments:
        raise RuntimeError("silence_detection requires vad_segments — run vad.py first")

    gaps = _invert_speech_segments(ctx.vad_segments, total_duration=ctx.metadata.get("duration_sec", 0.0))

    classified = []
    for start, end in gaps:
        duration = end - start
        if duration < settings.silence_min_removable_seconds:
            continue  # too short to matter either way

        reason = _classify_gap(start, end, ctx)
        removable = reason not in ("meaningful-pause",)
        classified.append(
            {
                "start_sec": start,
                "end_sec": end,
                "reason": reason,
                "removed": removable,
                # TODO(real impl): confidence should come from the
                # heuristic scoring function, not a placeholder.
                "confidence": 0.85,
            }
        )

    ctx.silence_segments = classified
    return ctx


def _invert_speech_segments(
    speech_segments: list[tuple[float, float]], total_duration: float
) -> list[tuple[float, float]]:
    """Turn a list of (speech_start, speech_end) tuples into the gaps between them."""
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in sorted(speech_segments):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total_duration:
        gaps.append((cursor, total_duration))
    return gaps


def _classify_gap(start: float, end: float, ctx: PipelineContext) -> str:
    """
    Heuristic-only classification pass (see module docstring for the full
    two-pass design). This is intentionally simple and would be replaced
    with a scored, multi-signal function in a real implementation.
    """
    duration = end - start

    if start < 20:
        return "setup-time"
    if duration <= settings.meaningful_pause_max_seconds:
        return "meaningful-pause"
    if duration > 40:
        return "dead-air"
    return "waiting"
