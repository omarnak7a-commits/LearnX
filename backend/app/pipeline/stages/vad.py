"""
Voice Activity Detection stage.

Real approach: run Silero VAD (CPU-friendly, ONNX export available) over
the extracted mono 16kHz audio track to get raw speech/non-speech
segment boundaries. This is the fast, cheap first pass — speaker
diarization (`diarization.py`) then subdivides the speech segments by
speaker, and `silence_detection.py` classifies everything Silero marked
as non-speech.
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "vad"


def run(ctx: PipelineContext) -> PipelineContext:
    if ctx.audio_path is None:
        raise RuntimeError("vad requires audio_path — run audio_extraction.py first")

    # TODO(real impl):
    #   import torch
    #   model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
    #   (get_speech_timestamps, *_ ) = utils
    #   wav = read_audio(ctx.audio_path, sampling_rate=16000)
    #   timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
    #   ctx.vad_segments = [(t['start'] / 16000, t['end'] / 16000) for t in timestamps]

    raise NotImplementedError(
        "This is a reference architecture stub — see module docstring and "
        "backend/README.md. Wire in a real Silero VAD model to make this stage functional."
    )
