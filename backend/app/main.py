"""FastAPI entrypoint."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.agent.service import run_consult
from app.config import settings
from app.db import get_session, init_db
from app.export import export_zip, import_zip


class ConsultRequest(BaseModel):
    conversation_id: str
    text: str
    photo_paths: list[str] = []


class ConversationRequest(BaseModel):
    body_part: str
    icon: str = "🧴"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}


@app.get("/api/export")
def export() -> Response:
    """Download the full local record (SQLite + photos) as a zip."""
    return Response(
        content=export_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=skincoach.zip"},
    )


@app.post("/api/import")
async def import_data(file: UploadFile = File(...)) -> dict:
    """Restore a previously exported zip."""
    import_zip(await file.read())
    return {"status": "ok"}


@app.get("/api/conversations")
def list_conversations(db: Session = Depends(get_session)) -> list[dict]:
    return [{"id": c.id, "body_part": c.body_part, "icon": c.icon} for c in crud.list_conversations(db)]


@app.post("/api/conversations")
def create_conversation(req: ConversationRequest, db: Session = Depends(get_session)) -> dict:
    c = crud.create_conversation(db, req.body_part, req.icon)
    return {"id": c.id, "body_part": c.body_part, "icon": c.icon}


@app.post("/api/consult")
def consult(req: ConsultRequest) -> dict:
    """Run the LangGraph agent: analyze -> tools -> advise -> guardrail -> persist."""
    return run_consult(req.conversation_id, req.text, req.photo_paths)
