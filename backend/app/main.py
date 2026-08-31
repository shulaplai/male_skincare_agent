"""FastAPI entrypoint."""
import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.agent.service import run_consult
from app.config import settings
from app.db import get_session, init_db
from app.export import export_zip, import_zip
from app.models import Entry, Insight, TimelineEvent
from app.photo import save_photo


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


@app.post("/api/photos")
async def upload_photo(file: UploadFile = File(...)) -> dict:
    """Store a photo locally (compressed) and return its id/path."""
    photo_id = uuid.uuid4().hex
    path = save_photo(photo_id, await file.read())
    return {"id": photo_id, "path": path}


@app.get("/api/conversations/{cid}/summary")
def conversation_summary(cid: str, db: Session = Depends(get_session)) -> dict:
    """All data for the records / progress views of one body-part conversation."""
    entries = db.query(Entry).filter_by(conversation_id=cid).order_by(Entry.date.desc()).all()
    insights = (
        db.query(Insight)
        .filter_by(conversation_id=cid)
        .filter(Insight.superseded_by.is_(None))
        .all()
    )
    events = (
        db.query(TimelineEvent)
        .filter_by(conversation_id=cid)
        .order_by(TimelineEvent.date.asc())
        .all()
    )
    return {
        "entries": [
            {
                "id": e.id,
                "date": str(e.date),
                "note": e.note,
                "metrics": e.metrics,
                "photos": [p.path for p in e.photos],
            }
            for e in entries
        ],
        "insights": [{"kind": i.kind, "text": i.text, "confidence": i.confidence} for i in insights],
        "timeline": [{"date": str(e.date), "text": e.text} for e in events],
    }


@app.get("/api/photos/{photo_id}")
def get_photo(photo_id: str) -> FileResponse:
    """Serve a stored photo by id."""
    path = Path(settings.data_dir) / "photos" / f"{photo_id}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path)


@app.get("/api/settings")
def get_settings() -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "model": "deepseek-chat" if settings.llm_provider == "deepseek" else settings.strong_model,
        "has_api_key": bool(
            settings.anthropic_api_key or settings.deepseek_api_key or settings.openai_api_key
        ),
    }
