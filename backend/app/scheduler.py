"""主動問候嘅 DB／LLM 部分（2026-10-21）。

`app/greeting.py` 只管純邏輯（窗口、去重、prompt）；呢度負責：

* 揀邊個 conversation 收問候（**最近有動靜**嗰個，唔係第一個）；
* 由 DB 攞少少事實（最近 entry 原話、有幾多日紀錄、最高信心嘅記憶）；
* 叫一次 LLM 寫一句，寫入 `ChatMessage`（`payload["proactive"] = slot`）；
* `maybe_greet()`：每分鐘由 `loop()` 叫一次，重複呼叫安全（同一 slot 一日只發一次）。

⚠️ 呢個係**唯一**會自己寫 ChatMessage 而唔係由用戶觸發嘅路徑。所以：
1. 佢永遠唔會寫 `Entry`（打招呼唔係皮膚觀察）；
2. 冇 key（FakeLLM）時仍然會發 —— 但 FakeLLM 嘅 `GreetingProse` 文字係罐頭，
   所以 `run_greeting` 喺 `mode == "fake"` 之下**唔會**發，避免用戶見到假問候；
3. 限制長度（`greeting.compose`）＋窗口外唔發，避免變成 spam。
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from . import greeting as greet_mod
from .agent.llm import describe_llm, get_llm
from .models import ChatMessage, Conversation, Entry, Insight, User

logger = logging.getLogger(__name__)


def _pick_conversation(db: Session) -> Conversation | None:
    """Most recently active conversation (by last chat message), else the oldest."""
    newest = (
        db.query(ChatMessage)
        .order_by(ChatMessage.id.desc())
        .filter(ChatMessage.role == "user")
        .first()
    )
    if newest is not None:
        conv = db.get(Conversation, newest.conversation_id)
        if conv is not None:
            return conv
    return db.query(Conversation).order_by(Conversation.created_at.asc()).first()


def _context(db: Session, conv: Conversation) -> dict:
    """Small factual context. Everything here is real data or nothing at all."""
    entries = (
        db.query(Entry)
        .filter_by(conversation_id=conv.id)
        .order_by(Entry.date.desc())
        .limit(1)
        .all()
    )
    last = entries[0] if entries else None
    days = db.query(Entry).filter_by(conversation_id=conv.id).count()
    insights = (
        db.query(Insight)
        .filter_by(conversation_id=conv.id)
        .order_by(Insight.confidence.desc())
        .limit(3)
        .all()
    )
    return {
        "last_entry_note": (last.note or "") if last else "",
        "recent_days": days,
        "memory_lines": [i.text for i in insights if i.text],
    }


def _today_payloads(db: Session, conv_id: str, now: dt.datetime) -> list[dict]:
    start = dt.datetime.combine(now.date(), dt.time.min)
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conv_id,
            ChatMessage.role == "coach",
            ChatMessage.created_at >= start,
        )
        .all()
    )
    return [r.payload or {} for r in rows]


def run_greeting(
    db: Session,
    *,
    slot: str | None = None,
    now: dt.datetime | None = None,
    force: bool = False,
    llm=None,
) -> dict:
    """Write one proactive greeting. Returns a small report dict (never raises).

    `force=True` skips the window and the once-per-slot check — used by the
    `POST /api/greet/run` route for manual verification.
    """
    now = now or dt.datetime.now()
    slot = slot or greet_mod.slot_for(now)
    if slot not in greet_mod.SLOTS:
        return {"sent": False, "reason": "outside_window", "slot": slot}

    user = db.query(User).first()
    if user is None:
        return {"sent": False, "reason": "no_user", "slot": slot}
    if not user.greet_enabled:
        return {"sent": False, "reason": "disabled", "slot": slot}

    conv = _pick_conversation(db)
    if conv is None:
        return {"sent": False, "reason": "no_conversation", "slot": slot}

    if not force and greet_mod.already_sent(_today_payloads(db, conv.id, now), slot):
        return {"sent": False, "reason": "already_sent", "slot": slot}

    from .persona import from_user

    # `llm` 可以注入（test 用 stub）—— 唔係嘅話唯一寫 ChatMessage 嘅背景路徑
    # 就冇得驗，只能靠真 key 或者 FakeLLM 嘅罐頭文字。
    llm = llm if llm is not None else get_llm("text")
    mode = describe_llm(llm).mode
    if mode == "fake":
        # FakeLLM 只會回罐頭文字；寫入 DB 就會變成「假問候」出現在真對話。
        return {"sent": False, "reason": "fake_llm", "slot": slot}

    ctx = _context(db, conv)
    prompt = greet_mod.build_prompt(from_user(user), slot, **ctx)
    try:
        prose = llm.structured(
            "你係用戶嘅專屬護膚顧問。你而家主動開口打招呼。",
            prompt,
            greet_mod.GreetingProse,
        )
        text = greet_mod.compose(getattr(prose, "text", ""), slot)
    except Exception:
        logger.warning("greeting: LLM 失敗，今次唔發", exc_info=True)
        return {"sent": False, "reason": "llm_error", "slot": slot}
    if not text:
        return {"sent": False, "reason": "empty", "slot": slot}

    msg = ChatMessage(
        conversation_id=conv.id,
        role="coach",
        text=text,
        payload={"proactive": slot, "greeting": True},
    )
    db.add(msg)
    db.commit()
    logger.info("greeting: 已發 %s 問候（conversation=%s）", slot, conv.id)
    return {"sent": True, "slot": slot, "text": text, "conversation_id": conv.id}


def maybe_greet(now: dt.datetime | None = None) -> dict:
    """Called every minute by the loop; safe to call by hand."""
    from .db import SessionLocal

    now = now or dt.datetime.now()
    slot = greet_mod.slot_for(now)
    if slot is None:
        return {"sent": False, "reason": "outside_window", "slot": None}
    session = SessionLocal()
    try:
        return run_greeting(session, slot=slot, now=now)
    finally:
        session.close()
