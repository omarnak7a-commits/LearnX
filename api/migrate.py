"""
One-off guarded Alembic migration runner for Vercel.

Vercel has no pre-deploy hook for serverless functions, so run the schema
migrations once after the first deploy:

    curl -X POST https://learn-x-ofvm.vercel.app/api/migrate \
      -H "x-migration-key: <MIGRATION_KEY from Vercel dashboard>"

Security: the endpoint only works if `MIGRATION_KEY` is set in the Vercel
dashboard AND the caller sends the matching header. If the key is not set
the endpoint returns 503 (disabled). It can only run `alembic upgrade
head` — it cannot execute arbitrary SQL.
"""

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

app = FastAPI(title="LearnX migration runner")


@app.post("/api/migrate")
def run_migrations(x_migration_key: str = Header(default="")) -> dict:
    key = os.environ.get("MIGRATION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Migration runner disabled — set MIGRATION_KEY in the Vercel dashboard.",
        )
    if x_migration_key != key:
        raise HTTPException(status_code=403, detail="Invalid migration key.")

    os.chdir(_BACKEND_DIR)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return {"ok": True, "target": "head"}
