"""
Topic + chapter detection.

Real approach:
  1. Embed every transcript segment (already computed in
     `transcription.py`) with the configured sentence-transformers model.
  2. Run a sliding-window topic-shift detector (e.g. TextTiling, or
     cosine-similarity dips between consecutive embedding windows) to
     find candidate chapter boundaries.
  3. Snap each boundary to the nearest scene change from
     `scene_detection.py` when one exists within a few seconds — slide
     changes are a strong, free signal for "the topic just changed".
  4. For each resulting chapter, call an LLM once (grounded only in that
     chapter's transcript + OCR'd slide text) to produce:
       - a short title
       - a difficulty estimate
       - an exam-importance score (weighted by phrases like "this will be
         on the exam", repetition, and emphasis markers WhisperX exposes)
       - estimated study minutes (roughly proportional to duration and
         difficulty)
  This keeps the expensive LLM call count at O(chapters), not O(transcript
  segments) or O(video length).
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "chapter-detection"


def run(ctx: PipelineContext) -> PipelineContext:
    if not ctx.transcript_segments:
        raise RuntimeError("chapter_detection requires transcript_segments — run transcription.py first")

    raise NotImplementedError(
        "Reference stub — implement topic-shift detection + per-chapter LLM "
        "summarization as described in the module docstring."
    )
