"""
OCR / subtitle detection — reads on-screen slide text at each detected
scene change (see scene_detection.py), and detects embedded subtitle
tracks if present.

Real approach: PaddleOCR or Tesseract on a sampled frame per scene;
ffprobe to detect embedded subtitle streams first (cheaper and more
accurate than OCR when available).
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "ocr"


def run(ctx: PipelineContext) -> PipelineContext:
    # TODO(real impl):
    #   for t in ctx.scene_changes:
    #       frame = extract_frame(ctx.original_video_path, at_second=t)
    #       ctx.ocr_text_by_scene[t] = pytesseract.image_to_string(frame)
    raise NotImplementedError("Reference stub — wire in OCR. See module docstring.")
