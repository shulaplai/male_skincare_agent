"""FastAPI entrypoint."""
import datetime
import logging
import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import correlation, crud
from app.agent.attributes import anchor_comparisons, severity_map
from app.agent.llm import FakeLLM, get_llm
from app.agent.product_eval import guard_narrative
from app.agent.product_context import profile_inputs, summarise_evaluation
from app.agent.product_eval import evaluate_product
from app.agent.prompts import PRODUCT_EVAL_SYSTEM, build_product_eval_prompt
from app.agent.schemas import DetectedEvent, ProductNarrative
from app.agent.service import run_consult
from app.config import settings
from app.db import get_session, init_db
from app.export import import_zip, iter_export_zip
from app.guide import build_guide
from app.models import (
    ChatMessage,
    Conversation,
    Entry,
    Insight,
    Photo,
    Product,
    TimelineEvent,
    Video,
    utcnow,
)
from app.photo import UnreadableImage, save_photo
from app.video import (
    COMPRESS_OVER_BYTES,
    VideoCompressError,
    VideoError,
    VideoTooLarge,
    check_size,
    compress_video,
    delete_video,
    extract_frames,
    video_file,
    video_path,
)
from app.self_report import apply_events


class ClipInfo(BaseModel):
    """A short clip the user uploaded instead of a photo.

    The UI does NOT tell the user that a clip is sampled into frames — from their
    side they sent a video. This object is what lets the agent talk about 「條片」
    and lets the reply avoid narrating frames/counts (2026-10-01 decision).
    """
    duration: float = 0.0
    frames: int = 0


class ConsultRequest(BaseModel):
    conversation_id: str
    text: str
    photo_paths: list[str] = []
    video: ClipInfo | None = None


class ConversationRequest(BaseModel):
    body_part: str
    icon: str = "🧴"


class ConsentRequest(BaseModel):
    """One-time photo consent. `granted=false` withdraws it (app returns to the gate)."""
    granted: bool = True


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
    # 邊條 chat message 出嘅 chip（`s<id>` → 12）。冇傳就用內容配對（見 route）。
    message_id: int | None = None


class ProductEvalRequest(BaseModel):
    """A product the user pasted for evaluation.

    `ingredients_text` is the INCI list the user copies off the packaging — the app
    never fetches it (architecture.md: no arbitrary external URL). `pigmentation`
    is D7 option 2: an explicit override of the note-keyword detection.
    """

    ingredients_text: str
    name: str = ""
    category: str = ""
    pigmentation: bool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    # App-module logs (vision failures, tool errors, embedder fallback) must be
    # visible: they were silent before, which made "reply looks wrong" reports
    # impossible to trace. uvicorn keeps its own handlers.
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    init_db()
    yield


logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "llm_provider": settings.llm_provider}


@app.get("/api/export")
def export() -> Response:
    """Download the full local record (SQLite + photos + clips) as a zip.

    Streams from a temp file. It used to hand `Response` the whole archive from
    `io.BytesIO` — so with the embedder cache living inside `data/` the body was ~1 GB,
    built in RAM and then copied again by `getvalue()`. Measured: the route returned
    **0 bytes in 45 s**. `app.export.iter_export_zip` also skips the model caches; the
    module docstring has the numbers.
    """
    return StreamingResponse(
        iter_export_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=skincoach.zip"},
    )


@app.post("/api/import")
async def import_data(file: UploadFile = File(...)) -> dict:
    """Restore a previously exported zip."""
    import_zip(await file.read())
    return {"status": "ok"}


@app.get("/api/guide")
def guide() -> dict:
    """男士護膚基本資料 (reference content).

    Rebuilt per request rather than cached: the 「應該用咩產品」 section is generated
    from `agent.recommend.RULES`, so the guide physically cannot drift from what the
    agent recommends. Cheap (pure Python, no DB).
    """
    return build_guide().model_dump()


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
    # Collect the on-disk files FIRST. `db.delete(c)` cascades the rows, and a cascade
    # never touches the filesystem — so before this, "permanently delete a conversation
    # and all its records" deleted the rows and left every photo (and clip) sitting in
    # the data dir. Measured: upload one photo, delete the conversation, the .jpg is
    # still there. The route promised deletion it did not perform.
    photo_paths = [
        p.path
        for p in db.query(Photo).join(Entry, Photo.entry_id == Entry.id).filter(
            Entry.conversation_id == cid
        )
    ]
    clips = db.query(Video).filter_by(conversation_id=cid).all()
    video_ids = [v.id for v in clips]
    # An upload writes its frames to data/photos/ *before* any Entry exists, so a
    # conversation deleted without ever consulting would leave those JPEGs behind with
    # nothing left pointing at them (the Video row carrying the ids is about to cascade
    # away). Frame ids are only ever produced by us, so turning them into paths is safe.
    frame_paths = [
        f"photos/{fid}.jpg" for v in clips for fid in (v.frames or []) if isinstance(fid, str)
    ]

    db.query(ChatMessage).filter_by(conversation_id=cid).delete()
    db.query(Product).filter_by(conversation_id=cid).delete()
    db.delete(c)  # cascades entries -> photos, insights, timeline_events, videos
    db.commit()

    # …now the files, best-effort: a row already gone is worse than a stray file.
    # Set-dedup because a frame the user actually consulted appears in both lists.
    wanted = set(photo_paths) | set(frame_paths)
    for path in wanted:
        _delete_photo_file(path)
    removed_clips = sum(1 for vid in video_ids if delete_video(vid))

    return {"status": "ok", "deleted": cid, "files_removed": len(wanted) + removed_clips}


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
    """User confirmed detected_events -> write Entry / timeline / products (Q51).

    Also marks the chat message that proposed them, so a reload does not show the
    same「我留意到…✅ 記低」chip again (pressing it twice would write the same diet /
    product twice). The id is the persisted one when the thread was loaded from the
    server; a message sent in *this* session only exists locally, so we fall back to
    matching on the events themselves.
    """
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    stats = apply_events(db, cid, req.events)
    marked = _mark_events_applied(db, cid, req.message_id, req.events)
    return {"written": stats["diet"] + stats["product"], "events_applied_on": marked, **stats}


def _mark_events_applied(
    db: Session, cid: str, message_id: int | None, events: list[DetectedEvent]
) -> int | None:
    """Stamp `events_applied` on the coach message that proposed these events."""
    wanted = {(e.type, e.text.strip()) for e in events}
    q = db.query(ChatMessage).filter_by(conversation_id=cid, role="coach")
    msg = q.filter_by(id=message_id).first() if message_id else None
    if msg is None:
        for candidate in q.order_by(ChatMessage.id.desc()).limit(20):
            proposed = {
                (e.get("type"), str(e.get("text", "")).strip())
                for e in (candidate.payload or {}).get("detected_events") or []
            }
            if proposed & wanted:
                msg = candidate
                break
    if msg is None:
        return None
    payload = dict(msg.payload or {})
    payload["events_applied"] = True
    msg.payload = payload          # 新 dict → SQLAlchemy 見到 mutation
    db.commit()
    return msg.id


@app.post("/api/conversations/{cid}/products/evaluate")
def evaluate_product_route(
    cid: str, req: ProductEvalRequest, db: Session = Depends(get_session)
) -> dict:
    """Evaluate a product the user pasted. **Persists nothing.**

    Deliberately NOT part of the `/api/consult` graph: that pipeline always ends in
    `persist`, which upserts today's `Entry`. `Entry` is the daily skin state and
    change detection / timeline / anchors all diff it, so answering "is this serum
    any good?" through the graph would silently turn a question into a day of skin
    data (docs/product-eval-plan.md §2.4).
    """
    conv = db.query(Conversation).filter_by(id=cid).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    # Inputs come from `product_context` — the same helper the consult graph uses, so the
    # explicit endpoint and a pasted list in chat can never disagree about whose profile
    # is being matched.
    inputs = profile_inputs(db, cid, pigmentation=req.pigmentation)
    result = evaluate_product(
        req.ingredients_text,
        attributes=inputs["attributes"],
        pigmentation=inputs["pigmentation"],
        in_use=inputs["in_use"],
    )

    payload = {
        **summarise_evaluation(result),
        "name": req.name,
        "category": req.category,
        "pigmentation_source": inputs["pigmentation_source"],
        "narrative": None,
    }

    # Narrative is presentation only. A prescription hit already returns the
    # escalation text, and FakeLLM must NOT invent product advice, so both skip it.
    if not result.escalate:
        llm = get_llm("text")
        if not isinstance(llm, FakeLLM):
            try:
                narrative = llm.structured(
                    PRODUCT_EVAL_SYSTEM,
                    build_product_eval_prompt(payload),
                    ProductNarrative,
                )
                payload["narrative"] = guard_narrative(narrative.summary, result)
            except Exception as e:  # never silently swallow (AGENTS.md)
                logger.warning("product narrative failed: %s: %s", type(e).__name__, e)

    return payload


@app.post("/api/consult")
def consult(req: ConsultRequest) -> dict:
    """Run the LangGraph agent: analyze -> tools -> advise -> guardrail -> persist."""
    return run_consult(
        req.conversation_id, req.text, req.photo_paths, clip=req.video.model_dump() if req.video else None
    )


@app.post("/api/photos")
async def upload_photo(file: UploadFile = File(...)) -> dict:
    """Store a photo locally (compressed) and return its id/path.

    Unreadable payloads become a **readable 415**, not a 500 (measured in-browser before
    this: uploading a HEIC — the iPhone default — showed the user 「✗ 上傳失敗：HTTP 500」,
    which says nothing and cannot be acted on).
    """
    photo_id = uuid.uuid4().hex
    try:
        path = save_photo(photo_id, await file.read())
    except UnreadableImage as e:
        logger.warning("photo upload rejected (%s): %s", file.filename, e.detail)
        raise HTTPException(
            status_code=415,
            detail=(
                "呢個檔案唔係我讀得到嘅圖片格式。如果係 iPhone 相簿嘅 HEIC／HEIF，"
                "可以先喺「設定 → 相機 → 格式」揀「最相容」（會存成 JPG），"
                "或者分享張相做 JPG 再上載。"
            ),
        ) from e
    return {"id": photo_id, "path": path}


@app.post("/api/videos")
async def upload_video(cid: str, file: UploadFile = File(...), db: Session = Depends(get_session)) -> dict:
    """Store a clip locally and turn it into frames the agent can look at.

    A couple of stills are not enough to see a whole area, so a clip is sampled into
    <= 6 de-duplicated frames — and **those frames are ordinary photos**. The client
    sends their ids as `photo_paths` to `/api/consult`, so the cloud-consent gate, photo
    dedupe, `entry.photos` and the `observes_skin or vision_used` gate all apply with no
    special cases. The agent never learns it was a video.

    **No *practical* size limit** (a user decision): a phone produces what it produces, so
    the ceiling is `video.MAX_BYTES` (100 MB) — far beyond a normal 20-second clip — rather
    than a tighter round number. The upload is streamed straight to disk rather than
    buffered in memory, and a clip over `COMPRESS_OVER_BYTES` (40 MB) is re-encoded down
    (smaller frame, no audio) before it is kept. The response reports what happened so the
    UI can tell the user.
    """
    video_id = uuid.uuid4().hex
    suffix = Path(file.filename or "").suffix or ".mp4"
    # Check the owner first: a clip with no conversation has nowhere to belong, and
    # rejecting it up front means nothing is written, decoded, or cleaned up afterwards.
    if db.query(Conversation).filter_by(id=cid).first() is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    stored = video_path(video_id, suffix)
    stored.parent.mkdir(parents=True, exist_ok=True)

    # Stream to disk. `await file.read()` would hold the whole clip in RAM, which is
    # exactly what "no size limit" must not do.
    original_bytes = 0
    try:
        with stored.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                original_bytes += len(chunk)
                try:
                    # Checked as we stream, so an oversized upload is cut off part-way
                    # instead of being written to disk in full first.
                    check_size(original_bytes)
                except VideoTooLarge as e:
                    out.close()
                    stored.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=str(e)) from e
                out.write(chunk)
    except OSError as e:  # disk full / permissions
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=507, detail=f"寫唔入 disk：{e}") from e

    if original_bytes == 0:
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="空檔案")

    rel = str(stored.relative_to(settings.data_dir))

    # Duration cap first: no point re-encoding a clip we will refuse.
    try:
        ex = extract_frames(stored)
    except VideoError as e:
        delete_video(video_id)
        raise HTTPException(status_code=422, detail=str(e)) from e

    compressed, stored_bytes, compress_error = False, original_bytes, None
    if original_bytes > COMPRESS_OVER_BYTES:
        try:
            new_path, before, after = compress_video(stored)
            if after < before:
                stored = new_path
                stored_bytes = after
                compressed = True
                rel = str(stored.relative_to(settings.data_dir))
                # Frames came from the original; the picture is the same, just smaller.
        except VideoCompressError as e:
            # Never fatal: the clip is usable, it is only bigger than we would like.
            compress_error = str(e)
            logger.warning("video compression failed, keeping the original: %s", e)

    frames = []
    for jpeg in ex.frames:
        pid = uuid.uuid4().hex
        frames.append({"id": pid, "path": save_photo(pid, jpeg)})

    # Record the clip so it is not an orphan file: without this row, deleting the
    # conversation could not know the clip exists and would leave it on disk.
    db.add(
        Video(
            id=video_id,
            conversation_id=cid,
            path=rel,
            duration=ex.duration,
            frames=[f["id"] for f in frames],
        )
    )
    db.commit()

    return {
        "video_id": video_id,
        "path": rel,
        "duration": round(ex.duration, 2),
        "fps": round(ex.fps, 1),
        "width": ex.width,
        "height": ex.height,
        "sampled": ex.sampled,
        "dropped": ex.dropped,
        "timestamps": ex.timestamps,
        "frames": frames,
        "original_bytes": original_bytes,
        "stored_bytes": stored_bytes,
        "compressed": compressed,
        "compress_error": compress_error,
    }


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
    #
    # Expiry is honoured on read as well as at write time. `reconcile` only *extends*
    # expiry when it strengthens a row, so this filter is what makes the documented
    # 30-day decay real: without it an expired insight stayed visible in /summary and
    # in the coach's prompt forever — and since `strengthen` is the only path that
    # raises confidence, the stale row could end up outranking the fresh one.
    insights = (
        db.query(Insight)
        .filter(
            (Insight.conversation_id == cid) | (Insight.conversation_id.is_(None))
        )
        .filter(Insight.superseded_by.is_(None))
        .filter(or_(Insight.expires_at.is_(None), Insight.expires_at > utcnow()))
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


@app.get("/api/consent")
def get_consent(db: Session = Depends(get_session)) -> dict:
    """One-time photo consent state (2026-10-01: cloud-only, consent asked once).

    `granted: false` means the app must show the consent screen and no photo may be
    sent to cloud vision — `service.run_consult` enforces the same thing server-side.
    """
    return crud.consent_state(db)


@app.post("/api/consent")
def post_consent(req: ConsentRequest, db: Session = Depends(get_session)) -> dict:
    """Record (or withdraw) consent to send photo bytes to a cloud vision model."""
    return crud.set_consent(db, req.granted)


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
