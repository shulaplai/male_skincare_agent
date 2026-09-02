#!/bin/sh
# SkinCoach backend entrypoint (runs at /app inside the image):
#   1. init_db          — create tables + apply lightweight migrations
#   2. seed RAG chunks  — only when the chunks table is empty; best-effort
#                         (first run downloads the fastembed model = network)
#   3. exec uvicorn     — replace this shell so signals reach the app
set -e

echo "[entrypoint] creating tables (init_db)"
python - <<'PY'
from app.db import init_db
init_db()
print("[entrypoint] init_db ok")
PY

echo "[entrypoint] checking existing RAG chunks"
chunks=$(python - <<'PY'
from sqlalchemy import text
from app.db import engine
with engine.connect() as conn:
    print(conn.execute(text("SELECT COUNT(*) FROM chunks")).scalar() or 0)
PY
)
echo "[entrypoint] chunks in db: ${chunks}"

if [ "${chunks}" = "0" ]; then
    echo "[entrypoint] chunks empty -> ingesting corpus (first run downloads the embedding model; needs network)"
    if python scripts/ingest_corpus.py; then
        echo "[entrypoint] corpus ingest OK"
    else
        echo "[entrypoint] WARN: corpus ingest failed (offline?) - continuing without RAG corpus" >&2
    fi
else
    echo "[entrypoint] corpus already seeded - skipping ingest"
fi

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
