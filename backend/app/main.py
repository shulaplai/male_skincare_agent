"""FastAPI entrypoint.

Phase 0: skeleton only. The agent, RAG and storage routers will be mounted
here as they land in later phases.
"""
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}
