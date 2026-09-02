# SkinCoach backend image: FastAPI + LangGraph + SQLite (RAG + photos).
#
# The image ships the committed seed corpus (`corpus/`) and `scripts/`, but NOT
# runtime data: `data/` (SQLite db, photos) is a bind-mounted volume, and the
# entrypoint creates tables + seeds RAG chunks on first boot instead.

FROM python:3.12-slim

# fastembed (onnxruntime) needs the OpenMP runtime on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the app package (deps from pyproject.toml) first for layer caching;
# pip install . must run from /app where pyproject.toml + app/ live.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Non-package files needed at runtime.
COPY corpus ./corpus
COPY scripts ./scripts
COPY docker_entrypoint.sh ./docker_entrypoint.sh
RUN chmod +x /app/docker_entrypoint.sh

# Stream backend logs to `docker compose logs`.
ENV PYTHONUNBUFFERED=1
# Where fastembed caches models downloaded on first ingest (needs network).
ENV HF_HOME=/app/.hf-cache

EXPOSE 8000

ENTRYPOINT ["./docker_entrypoint.sh"]
