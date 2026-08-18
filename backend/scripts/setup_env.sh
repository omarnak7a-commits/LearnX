#!/usr/bin/env bash
# Recreate the local Python environment used by the quiz test suite and the
# diagnostic harnesses.
#
# .venv/ is intentionally git-ignored and is not preserved in workspace
# snapshots, so it has to be rebuilt after a fresh checkout or a new sandbox.
# Everything here is reproducible from requirements.txt; no state lives in the
# virtualenv itself.
#
#   bash backend/scripts/setup_env.sh
#   .venv/bin/python -m pytest backend/tests -q
set -euo pipefail

cd "$(dirname "$0")/../.."

python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
# Test-only tooling, not part of the deployed runtime dependency set.
.venv/bin/pip install --quiet pytest pytest-asyncio

.venv/bin/python - <<'PY'
import fastapi, pypdf, pytest  # noqa: F401
print("environment ready")
PY
