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
    err_app = FastAPI()
    error_trace = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
    
    @err_app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(full_path: str):
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error_type": type(e).__name__, "message": str(e), "trace": error_trace}
        )
    app = err_app
