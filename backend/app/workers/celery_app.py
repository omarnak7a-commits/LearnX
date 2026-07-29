"""
Celery application + the video pipeline task.

Reference implementation — no Redis/Celery broker is running here.
"""

from __future__ import annotations

from pathlib import Path

from celery import Celery

from app.core.config import get_settings
from app.pipeline.orchestrator import run_pipeline
from app.pipeline.stage import PipelineContext

settings = get_settings()

celery_app = Celery(
    "learnx",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Long-running video jobs: don't let Celery's default visibility
    # timeout requeue an in-progress job onto a second worker.
    broker_transport_options={"visibility_timeout": 6 * 60 * 60},
)


@celery_app.task(bind=True, name="video.process_lecture")
def process_lecture(self, lecture_id: str, original_video_path: str, workdir: str) -> dict:
    """
    Entry point queued by `app/api/video.py` once an upload completes.
    Publishes progress to Redis pub/sub as it runs so
    `app/api/websockets.py` can relay it to the connected client — this is
    what would replace the client-side `setInterval` simulation in
    `VideoIntelligencePage.tsx`.
    """

    ctx = PipelineContext(
        lecture_id=lecture_id,
        original_video_path=Path(original_video_path),
        workdir=Path(workdir),
    )

    def on_progress(stage_id: str, pct: float) -> None:
        self.update_state(state="PROGRESS", meta={"stage_id": stage_id, "pct": pct})
        # TODO(real impl): also publish to Redis pub/sub channel
        # f"lecture:{lecture_id}:progress" for the WebSocket relay.

    ctx = run_pipeline(ctx, on_progress=on_progress)

    # TODO(real impl): persist ctx.chapters / transcript_segments /
    # silence_segments / generated_assets to Postgres, upload
    # ctx.optimized_video_path to object storage, and mark the
    # VideoLecture row `state = ready`.

    return {"lecture_id": lecture_id, "status": "completed"}
