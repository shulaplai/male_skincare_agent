"""FastAPI entrypoint.

Phase 1: database + memory + photo storage land here. The agent graph and RAG
routers will be mounted as they arrive in later phases.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}
