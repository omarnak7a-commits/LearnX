"""
Sanity tests for the pipeline stage contract.

These only verify import structure, dataclass shape, and the
silence-classification heuristic — they do NOT exercise any real AI model
(no GPU / model weights available). Real integration tests belong in a
separate suite gated behind `pytest -m gpu` once models are available.
"""

from pathlib import Path

from app.pipeline.stage import PipelineContext
from app.pipeline.stages import silence_detection


def _ctx(**overrides) -> PipelineContext:
    base = dict(
        lecture_id="lec-test",
        original_video_path=Path("/tmp/original.mp4"),
        workdir=Path("/tmp/work"),
    )
    base.update(overrides)
    return PipelineContext(**base)


def test_silence_detection_flags_setup_time_at_start():
    ctx = _ctx(
        vad_segments=[(18.0, 90.0), (95.0, 200.0)],
        metadata={"duration_sec": 200.0},
    )
    result = silence_detection.run(ctx)

    setup_segment = next(s for s in result.silence_segments if s["start_sec"] == 0.0)
    assert setup_segment["reason"] == "setup-time"
    assert setup_segment["removed"] is True


def test_silence_detection_keeps_short_pauses_as_meaningful():
    ctx = _ctx(
        vad_segments=[(20.0, 100.0), (104.0, 200.0)],  # 4s gap at 100-104
        metadata={"duration_sec": 200.0},
    )
    result = silence_detection.run(ctx)

    short_gap = next(s for s in result.silence_segments if s["start_sec"] == 100.0)
    assert short_gap["reason"] == "meaningful-pause"
    assert short_gap["removed"] is False


def test_silence_detection_requires_vad_segments():
    ctx = _ctx(vad_segments=[])
    try:
        silence_detection.run(ctx)
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
