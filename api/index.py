import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

for p in [str(backend_dir), str(root_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    err_msg = str(e)
    err_tb = traceback.format_exc()
    fallback = FastAPI(title="LearnX API Fallback")

    @fallback.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    def catch_all(path: str = ""):
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error_type": type(e).__name__,
                "error": err_msg,
                "traceback": err_tb,
            },
        )

    app = fallback
