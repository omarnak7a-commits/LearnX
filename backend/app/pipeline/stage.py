"""
Shared pipeline stage contract.

Every module in `app/pipeline/stages/` implements a `run()` function with
this signature so `app/pipeline/orchestrator.py` can execute them
uniformly and persist progress after each one — matching the
`PipelineStage` shape the frontend already renders
(`src/components/dashboard/student/video/PipelineTimeline.tsx`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class PipelineContext:
    """
    Mutable state threaded through every stage. Real implementations
    would load/save this from Postgres + object storage between stages so
    a crashed Celery worker can resume from the last completed stage
    instead of restarting the whole pipeline.
    """

    lecture_id: str
    original_video_path: Path
    workdir: Path

    # Populated incrementally by each stage:
    audio_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    vad_segments: list[tuple[float, float]] = field(default_factory=list)
    diarization_segments: list[dict[str, Any]] = field(default_factory=list)
    silence_segments: list[dict[str, Any]] = field(default_factory=list)
    scene_changes: list[float] = field(default_factory=list)
    ocr_text_by_scene: dict[float, str] = field(default_factory=dict)
    transcript_segments: list[dict[str, Any]] = field(default_factory=list)
    chapters: list[dict[str, Any]] = field(default_factory=list)
    optimized_video_path: Path | None = None
    generated_assets: dict[str, Any] = field(default_factory=dict)  # summaries/flashcards/quiz/mindmap/notes


class PipelineStage(Protocol):
    """Every stage module exposes a module-level `STAGE_ID` and `run()`."""

    STAGE_ID: str

    def run(self, ctx: PipelineContext) -> PipelineContext: ...
