"""FastAPI entrypoint."""
import datetime
import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import correlation, crud
from app.agent.attributes import anchor_comparisons, severity_map
from app.agent.schemas import DetectedEvent
from app.agent.service import run_consult
from app.config import settings
from app.db import get_session, init_db
from app.export import export_zip, import_zip
from app.models import ChatMessage, Conversation, Entry, Insight, Photo, Product, TimelineEvent
from app.photo import save_photo
from app.self_report import apply_events


class ConsultRequest(BaseModel):
    conversation_id: str
    text: str
    photo_paths: list[str] = []


class ConversationRequest(BaseModel):
    body_part: str
    icon: str = "🧴"


class CloudAnalysisRequest(BaseModel):
    enabled: bool


class FactRequest(BaseModel):
    """A ground-truth fact the user records themselves (Q25): not derived by AI."""
    text: str
    tag: str = "user_fact"
    global_scope: bool = False  # body-spanning fact (Q27/Q31) -> conversation_id NULL


class RenameRequest(BaseModel):
    body_part: str


class EventsRequest(BaseModel):
    """Confirmed self-reported events from the user (Q49/Q51)."""
    events: list[DetectedEvent]


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
    return [
        {"id": c.id, "body_part": c.body_part, "icon": c.icon, "cloud_analysis": bool(c.cloud_analysis)}
        for c in crud.list_conversations(db)
    ]


@app.post("/api/conversations")
def create_conversation(req: ConversationRequest, db: Session = Depends(get_session)) -> dict:
    c = crud.create_conversation(db, req.body_part, req.icon)
    return {"id": c.id, "body_part": c.body_part, "icon": c.icon, "cloud_analysis": bool(c.cloud_analysis)}


@app.get("/api/conversations/{cid}")
def get_conversation(cid: str, db: Session = Depends(get_session)) -> dict:
    c = db.query(Conversation).filter_by(id=cid).first()
    if c is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"id": c.id, "body_part": c.body_part, "icon": c.icon, "cloud_analysis": bool(c.cloud_analysis)}


@app.put("/api/conversations/{cid}/cloud-analysis")
def set_cloud_analysis(cid: str, req: CloudAnalysisRequest, db: Session = Depends(get_session)) -> dict:
    """Toggle cloud-photo-analysis consent for a conversation (Q18)."""
    c = db.query(Conversation).filter_by(id=cid).first()
    if c is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    c.cloud_analysis = req.enabled
    db.commit()
    return {"id": c.id, "cloud_analysis": bool(c.cloud_analysis)}


@app.put("/api/conversations/{cid}")
def rename_conversation(cid: str, req: RenameRequest, db: Session = Depends(get_session)) -> dict:
    """Rename a conversation (Q52)."""
    c = db.query(Conversation).filter_by(id=cid).first()
    if c is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    name = req.body_part.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be empty")
    c.body_part = name
    db.commit()
    return {"id": c.id, "body_part": c.body_part, "icon": c.icon, "cloud_analysis": bool(c.cloud_analysis)}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: str, db: Session = Depends(get_session)) -> dict:
    """Permanently delete a conversation and all its records (Q32/Q52)."""
    c = db.query(Conversation).filter_by(id=cid).first()
    if c is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    db.query(ChatMessage).filter_by(conversation_id=cid).delete()
    db.query(Product).filter_by(conversation_id=cid).delete()
    db.delete(c)  # cascades entries -> photos, insights, timeline_events
    db.commit()
    return {"status": "ok", "deleted": cid}


@app.post("/api/conversations/{cid}/facts")
def create_fact(cid: str, req: FactRequest, db: Session = Depends(get_session)) -> dict:
    """User-recorded ground-truth fact (Q25). `global_scope` => affects all body parts."""
    if not req.global_scope:
        conv = db.query(Conversation).filter_by(id=cid).first()
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
    fact = Insight(
        conversation_id=None if req.global_scope else cid,
        kind="fact",
        tag=req.tag,
        direction="",
        text=req.text,
    )
    db.add(fact)
    db.commit()
    return {
        "id": fact.id,
        "kind": "fact",
        "tag": fact.tag,
        "text": fact.text,
        "scope": "global" if req.global_scope else "body_part",
    }


@app.post("/api/conversations/{cid}/events")
def confirm_events(cid: str, req: EventsRequest, db: Session = Depends(get_session)) -> dict:
    """User confirmed detected_events -> write Entry / timeline / products (Q51)."""
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    stats = apply_events(db, cid, req.events)
    return {"written": stats["diet"] + stats["product"], **stats}


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


@app.get("/api/conversations/{cid}/messages")
def conversation_messages(cid: str, db: Session = Depends(get_session)) -> list[dict]:
    """Full chat-thread history for a conversation (Q7: survives reloads)."""
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    msgs = (
        db.query(ChatMessage)
        .filter_by(conversation_id=cid)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "payload": m.payload,
            "created_at": m.created_at.isoformat(timespec="seconds"),
        }
        for m in msgs
    ]


@app.get("/api/conversations/{cid}/summary")
def conversation_summary(cid: str, db: Session = Depends(get_session)) -> dict:
    """All data for the records / progress views of one body-part conversation."""
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    entries = db.query(Entry).filter_by(conversation_id=cid).order_by(Entry.date.desc()).all()
    # Insights: conversation-scoped derived memory + global facts/preferences
    # (Q31 — body-spanning memory belongs to every body part's view).
    insights = (
        db.query(Insight)
        .filter(
            (Insight.conversation_id == cid) | (Insight.conversation_id.is_(None))
        )
        .filter(Insight.superseded_by.is_(None))
        .order_by(Insight.created_at.desc())
        .all()
    )
    # Timeline: conversation events + global user events (diet causes, Q31)
    # merged chronologically so every body part sees the same "因".
    conv_events = (
        db.query(TimelineEvent)
        .filter_by(conversation_id=cid)
        .order_by(TimelineEvent.date.asc())
        .all()
    )
    global_events = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.conversation_id.is_(None))
        .order_by(TimelineEvent.date.asc())
        .all()
    )
    events = sorted(
        [*conv_events, *global_events],
        key=lambda e: (e.date, e.created_at),
    )
    # Rolling multi-anchor comparison for the latest entry (Q12 UI data).
    today = datetime.date.today()
    latest = entries[0] if entries else None
    anchors: list[dict] = []
    if latest is not None and (latest.attributes or []):
        history = [e for e in entries if e.date < latest.date]
        anchors = anchor_comparisons(severity_map(latest.attributes or []), history, latest.date)
    return {
        "conversation": {
            "id": conv.id,
            "body_part": conv.body_part,
            "icon": conv.icon,
            "cloud_analysis": bool(conv.cloud_analysis),
        },
        "entries": [
            {
                "id": e.id,
                "date": str(e.date),
                "note": e.note,
                "metrics": e.metrics,
                "attributes": e.attributes,
                "photos": [p.path for p in e.photos],
                "products": e.products,
            }
            for e in entries
        ],
        "insights": [
            {
                "id": i.id,
                "kind": i.kind,
                "text": i.text,
                "confidence": i.confidence,
                "direction": i.direction,
                "tag": i.tag,
                "scope": "global" if i.conversation_id is None else "body_part",
            }
            for i in insights
        ],
        "timeline": [
            {
                "date": str(e.date),
                "text": e.text,
                "source": e.source,
                "scope": "global" if e.conversation_id is None else "body_part",
            }
            for e in events
        ],
        "anchors": anchors,
    }


@app.get("/api/conversations/{cid}/correlations")
def conversation_correlations(cid: str, db: Session = Depends(get_session)) -> dict:
    """Deterministic correlation candidates for a conversation (Q30)."""
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return correlation.conversation_candidates(db, cid)


@app.get("/api/photos/{photo_id}")
def get_photo(photo_id: str) -> FileResponse:
    """Serve a stored photo by id."""
    path = Path(settings.data_dir) / "photos" / f"{photo_id}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path)


@app.get("/api/settings")
def get_settings() -> dict:
    provider = settings.llm_provider
    text_model = {
        "deepseek": settings.deepseek_text_model,
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
    }.get(provider, settings.deepseek_text_model)
    vision_model = (
        settings.deepseek_vision_model if provider == "deepseek" else text_model
    )
    return {
        "llm_provider": provider,
        "model": text_model,
        "vision_model": vision_model,
        "has_api_key": bool(
            settings.anthropic_api_key or settings.deepseek_api_key or settings.openai_api_key
        ),
    }


class EntryNoteRequest(BaseModel):
    """Edit a day entry's note (memory correction)."""
    note: str = ""


def _delete_photo_file(path: str) -> None:
    """Best-effort removal of a stored photo file (path is data-dir relative)."""
    try:
        (Path(settings.data_dir) / path).unlink(missing_ok=True)
    except OSError:
        pass  # file already gone or unreadable — row deletion is what matters


@app.put("/api/conversations/{cid}/entries/{eid}")
def edit_entry_note(cid: str, eid: str, req: EntryNoteRequest, db: Session = Depends(get_session)) -> dict:
    """Edit a day entry's note (delete/edit memory-correction UI)."""
    entry = db.query(Entry).filter_by(id=eid, conversation_id=cid).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    entry.note = req.note.strip()
    db.commit()
    return {"id": entry.id, "note": entry.note}


@app.delete("/api/conversations/{cid}/entries/{eid}")
def delete_entry(cid: str, eid: str, db: Session = Depends(get_session)) -> dict:
    """Permanently delete a single day entry + its photos (memory correction).

    Also removes that day's conversation-scoped timeline events (they were
    generated for this record); global events are kept (they belong to every
    body part, Q31).
    """
    entry = db.query(Entry).filter_by(id=eid, conversation_id=cid).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    for p in entry.photos:
        _delete_photo_file(p.path)
    # Bulk delete bypasses ORM cascade, so remove photos explicitly first.
    db.query(Photo).filter_by(entry_id=eid).delete()
    db.query(TimelineEvent).filter_by(conversation_id=cid, date=entry.date).delete()
    db.query(Entry).filter_by(id=eid).delete()
    db.commit()
    return {"status": "ok", "deleted": eid}


@app.delete("/api/entries/{eid}/photos/{photo_id}")
def delete_entry_photo(eid: str, photo_id: str, db: Session = Depends(get_session)) -> dict:
    """Delete one photo from an entry (memory correction without losing the day).

    `photo_id` is the uploaded file id (photo path is photos/<id>.jpg) — the
    same id the frontend renders from an entry's photo path.
    """
    path = f"photos/{photo_id}.jpg"
    photo = db.query(Photo).filter_by(entry_id=eid, path=path).first()
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")
    _delete_photo_file(photo.path)
    db.delete(photo)
    db.commit()
    return {"status": "ok", "deleted": photo_id}


@app.delete("/api/conversations/{cid}/insights/{iid}")
def delete_insight(cid: str, iid: str, db: Session = Depends(get_session)) -> dict:
    """Delete one memory insight (user memory correction)."""
    ins = db.query(Insight).filter_by(id=iid).first()
    if ins is None:
        raise HTTPException(status_code=404, detail="insight not found")
    if ins.conversation_id not in (cid, None):
        raise HTTPException(status_code=403, detail="insight belongs to another conversation")
    # Clear superseded_by pointers that reference this insight before deleting.
    db.query(Insight).filter(Insight.superseded_by == iid).update({"superseded_by": None})
    db.delete(ins)
    db.commit()
    return {"status": "ok", "deleted": iid}
