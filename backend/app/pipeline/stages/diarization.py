"""
Speaker diarization stage — identifies "who spoke when" so transcript
segments can be labeled (and, for multi-speaker Q&A sections, so the
silence-classification pass can tell a real conversational pause from
dead air).

Real approach: pyannote.audio's pretrained diarization pipeline
(`settings.diarization_model`), requires a HuggingFace access token
accepted for that gated model.
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "diarization"


def run(ctx: PipelineContext) -> PipelineContext:
    if ctx.audio_path is None:
        raise RuntimeError("diarization requires audio_path — run audio_extraction.py first")

    # TODO(real impl):
    #   from pyannote.audio import Pipeline
    #   pipeline = Pipeline.from_pretrained(settings.diarization_model, use_auth_token=...)
    #   diarization = pipeline(str(ctx.audio_path))
    #   ctx.diarization_segments = [
    #       {"start": turn.start, "end": turn.end, "speaker": speaker}
    #       for turn, _, speaker in diarization.itertracks(yield_label=True)
    #   ]

    raise NotImplementedError("Reference stub — wire in pyannote.audio. See module docstring.")
