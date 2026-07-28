"""
Scene detection — flags slide/scene changes in the video, used both as a
signal for silence classification (a pause right after a slide change is
more likely to be "waiting", not "explaining") and as a hint for OCR
(only run OCR once per scene, not once per frame).

Real approach: PySceneDetect's content-aware detector on the extracted
video, or a cheaper histogram-diff over sampled frames via ffmpeg.
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "scene-detection"


def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(real impl):
    #   from scenedetect import detect, ContentDetector
    #   scene_list = detect(str(ctx.original_video_path), ContentDetector())
    #   ctx.scene_changes = [scene[0].get_seconds() for scene in scene_list]
    raise NotImplementedError("Reference stub — wire in PySceneDetect. See module docstring.")
