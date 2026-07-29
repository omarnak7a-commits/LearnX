"""
Speech recognition stage — WhisperX transcription + forced word alignment.

Real approach:
  1. Run WhisperX (`whisper_model_size` from settings, GPU strongly
     recommended) to get segment-level transcript + timestamps.
  2. Run WhisperX's forced-alignment pass to get word-level timestamps
     (needed for accurate "jump to timestamp" behavior in the transcript
     panel and for trimming precision).
  3. Merge with `diarization.py` output to attach a speaker label to each
     segment (`TranscriptSegment.speaker`).
  4. Compute a sentence-transformers embedding per segment
     (`embeddings_model` in settings) and store it — this is what powers
     the RAG-grounded AI chat in `app/services/rag.py`, and is required
     for the "always cite, never hallucinate" behavior.
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "transcription"


def run(ctx: PipelineContext) -> PipelineContext:
    if ctx.audio_path is None:
        raise RuntimeError("transcription requires audio_path — run audio_extraction.py first")

    # TODO(real impl):
    #   import whisperx
    #   model = whisperx.load_model(settings.whisper_model_size, settings.whisper_device)
    #   result = model.transcribe(str(ctx.audio_path))
    #   align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=settings.whisper_device)
    #   aligned = whisperx.align(result["segments"], align_model, metadata, str(ctx.audio_path), settings.whisper_device)
    #   ctx.transcript_segments = _merge_with_diarization(aligned["segments"], ctx.diarization_segments)
    #   for seg in ctx.transcript_segments:
    #       seg["embedding"] = embed(seg["text"])  # sentence-transformers

    raise NotImplementedError(
        "Reference stub — wire in WhisperX + your embeddings model. See module docstring."
    )
