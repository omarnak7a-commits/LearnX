"""
WebSocket relay for live pipeline progress.

Real approach: subscribe to the Redis pub/sub channel
`lecture:{lecture_id}:progress` (published by
`app/workers/celery_app.py::process_lecture`) and forward each message to
the connected client — this is what would replace the client-side
`setInterval` simulation in `VideoIntelligencePage.tsx`.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/videos/{lecture_id}/progress")
async def lecture_progress(websocket: WebSocket, lecture_id: str) -> None:
    await websocket.accept()
    try:
        # TODO(real impl):
        #   redis = aioredis.from_url(settings.redis_url)
        #   pubsub = redis.pubsub()
        #   await pubsub.subscribe(f"lecture:{lecture_id}:progress")
        #   async for message in pubsub.listen():
        #       if message["type"] == "message":
        #           await websocket.send_json(json.loads(message["data"]))
        raise NotImplementedError("Reference stub — wire in Redis pub/sub. See module docstring.")
    except WebSocketDisconnect:
        pass
