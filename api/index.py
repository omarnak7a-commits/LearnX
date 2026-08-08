import os
import sys
import traceback
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

for p in [str(backend_dir), str(root_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

app_instance = None
import_error = None

try:
    from app.main import app as real_app
    app_instance = real_app
except Exception as e:
    import_error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

async def app(scope, receive, send):
    if scope["type"] == "http":
        if app_instance is not None:
            await app_instance(scope, receive, send)
        else:
            import json
            err_dict = {"status": "error", "error": "Backend startup exception", "details": import_error}
            body = json.dumps(err_dict, indent=2).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                    (b"access-control-allow-origin", b"*"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
    elif scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                break

handler = app
application = app
