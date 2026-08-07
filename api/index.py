"""
LearnX backend on Vercel Serverless Functions (Python ASGI).

Vercel routes `/api/v1/*`, `/health`, `/docs` and `/openapi.json` here via
`vercel.json` rewrites. The FastAPI app is exposed as `app` — Vercel's
Python runtime serves ASGI apps that export a top-level `app` object.

Dependencies are installed by Vercel from `./requirements.txt` (project
root). The backend package lives under `backend/`, so we add it to
`sys.path` before importing `app.main`.
"""

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.main import app  # noqa: E402
