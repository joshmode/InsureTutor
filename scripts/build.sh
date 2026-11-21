#!/usr/bin/env sh
# Native build: prepare/reuse the pinned local embedding model, then build UI.
set -eu
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
    build_python=.venv/bin/python
else
    build_python=python3
fi
"$build_python" -m backend.app.scripts.download_embedding_model \
    --revision "${EMBEDDING_MODEL_REVISION:-faf4aa4225822f3bc6376869cb1164e8e3feedd0}"
npm --prefix frontend run build
