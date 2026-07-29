"""Audio extraction — pulls a mono 16kHz WAV track out of the source video via ffmpeg."""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "audio-extraction"


def run(ctx: PipelineContext) -> PipelineContext:
    output_path = ctx.workdir / f"{ctx.lecture_id}.wav"

    # TODO(real impl):
    #   import ffmpeg
    #   ffmpeg.input(str(ctx.original_video_path)).output(
    #       str(output_path), ac=1, ar=16000, format="wav"
    #   ).overwrite_output().run(quiet=True)

    ctx.audio_path = output_path
    return ctx
