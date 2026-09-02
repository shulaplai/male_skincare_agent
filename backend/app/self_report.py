"""Confirmed self-reported events -> Entry / timeline / products (Q49/Q51).

The LLM only PROPOSES `detected_events`; nothing is written until the user
confirms (POST /api/conversations/{cid}/events). Applying is deterministic code:
- diet events append to the day's Entry.diet AND write a *global* timeline
  event (conversation_id NULL — diet is body-spanning, Q31) so every body part
  sees the same cause;
- product_start/product_stop upsert the canonical `products` table (Q28),
  reference it from Entry.products, and maintain a fact insight per product
  (Q25 "check-in 自動 fact": confirmed ground truth the coach can read) —
  so causality can be traced deterministically later.

Diet trigger tags (Q29) are derived here by deterministic keywords — the same
function re-derives tags from stored text for the correlation detector and the
preference extractor.
"""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from .models import Entry, Insight, Product, TimelineEvent
from .agent.schemas import DetectedEvent

# zh tokens -> deterministic diet trigger tags (Q29). Keep versioned + tested.
_TRIGGERS: dict[str, tuple[str, ...]] = {
    "spicy": ("辣", "麻辣", "辛辣"),
    "sugary": ("甜", "糖", "蛋糕", "甜品", "珍珠奶茶"),
    "oily_food": ("油炸", "炸", "油膩", "肥膩"),
    "dairy": ("奶", "芝士", "乳酪", "雪糕", "牛奶"),
    "alcohol": ("酒", "啤酒", "紅酒", "白酒"),
}


def trigger_tags(text: str) -> list[str]:
    """Deterministic diet trigger tags for a free-text diet note (Q29)."""
    low = text.lower()
    return [tag for tag, tokens in _TRIGGERS.items() if any(t in low for t in tokens)]


def _product_key(name: str) -> str:
    return name.strip().lower()


def _get_or_create_product(session: Session, conv_id: str, name: str) -> Product:
    key = _product_key(name)
    prod = (
        session.query(Product)
        .filter_by(conversation_id=conv_id)
        .all()
    )
    for p in prod:
        if _product_key(p.name) == key:
            return p
    p = Product(conversation_id=conv_id, name=name.strip() or "未命名產品")
    session.add(p)
    session.flush()  # assign p.id before it is referenced from Entry.products
    return p


def _upsert_product_fact(session: Session, conv_id: str, prod: Product, start: bool, date: datetime.date) -> None:
    """Check-in auto fact (Q25): one fact insight per product, current state.

    product_start -> 「由 {date} 開始用「{name}」」; product_stop appends the
    stop date. Facts are ground truth (never expire) and are refreshed in
    place, so the coach's memory always reflects the latest confirmed state.
    """
    tag = f"product_use:{_product_key(prod.name)}"
    fact = (
        session.query(Insight)
        .filter_by(conversation_id=conv_id, kind="fact", tag=tag)
        .order_by(Insight.created_at.desc())
        .first()
    )
    if start:
        text = f"由 {date.isoformat()} 開始用「{prod.name.strip()}」"
        if fact is None:
            session.add(Insight(conversation_id=conv_id, kind="fact", tag=tag, text=text))
        elif fact.text != text:
            fact.text = text
    else:
        # Stop: only meaningful if we have a start fact; otherwise record anyway.
        text = f"用過「{prod.name.strip()}」（{date.isoformat()} 停用）"
        if fact is None:
            session.add(Insight(conversation_id=conv_id, kind="fact", tag=tag, text=text))
        elif "停用" not in fact.text:
            fact.text = fact.text + f"，{date.isoformat()} 停用"


def apply_events(session: Session, conv_id: str, events: list[DetectedEvent], *, with_preferences: bool = True) -> dict:
    """Write confirmed events. Idempotent-ish: same text/name on the same day is skipped."""
    today = datetime.date.today()
    entry = session.query(Entry).filter_by(conversation_id=conv_id, date=today).first()
    if entry is None:
        entry = Entry(conversation_id=conv_id, date=today)
        session.add(entry)
        session.flush()

    stats = {"diet": 0, "product": 0}
    existing_timeline = {
        (e.date, e.text, e.source, e.conversation_id)
        for e in session.query(TimelineEvent).filter_by(conversation_id=conv_id).all()
    }
    # Global diet events: dedupe across ALL conversations (conversation_id NULL).
    existing_global = {
        (e.date, e.text, e.source)
        for e in session.query(TimelineEvent).filter(TimelineEvent.conversation_id.is_(None)).all()
    }

    for ev in events:
        if ev.type == "diet" and ev.text.strip():
            # Diet is recorded once per (day, text): the entry's diet list is
            # today's list, so duplicate detection on that list is enough.
            if ev.text.strip() in entry.diet:
                continue
            entry.diet = [*entry.diet, ev.text.strip()]
            stats["diet"] += 1
            # Global cause event (Q31): diet affects every body part. One row
            # per (date, text); conversation-scoped copy is intentionally NOT
            # written — /summary merges global events into every timeline.
            gkey = (today, ev.text.strip(), "user")
            if gkey not in existing_global:
                session.add(
                    TimelineEvent(
                        conversation_id=None,
                        date=today,
                        text=ev.text.strip(),
                        source="user",
                    )
                )
                existing_global.add(gkey)
        elif ev.type in ("product_start", "product_stop") and ev.product_name.strip():
            prod = _get_or_create_product(session, conv_id, ev.product_name)
            stats["product"] += 1
            if ev.type == "product_start":
                if prod.id not in entry.products:
                    entry.products = [*entry.products, prod.id]
            else:
                entry.products = [p for p in entry.products if p != prod.id]
            ev.text = ev.text or ("開始用：" + prod.name if ev.type == "product_start" else "停用：" + prod.name)
            _upsert_product_fact(session, conv_id, prod, start=ev.type == "product_start", date=today)

        text = ev.text.strip()
        if text and ev.type != "diet":
            key = (today, text, "user", conv_id)
            if key not in existing_timeline:
                session.add(
                    TimelineEvent(
                        conversation_id=conv_id,
                        date=today,
                        text=text,
                        source="user",
                    )
                )
                existing_timeline.add(key)

    session.commit()
    if with_preferences:
        from .preferences import extract_preferences

        prefs = extract_preferences(session, conv_id)
        stats["preferences"] = prefs["written"]
    return stats
