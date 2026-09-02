"""Confirmed self-reported events -> Entry / timeline / products (Q49/Q51).

The LLM only PROPOSES `detected_events`; nothing is written until the user
confirms (POST /api/conversations/{cid}/events). Applying is deterministic code:
- diet events append to the day's Entry.diet and write a user timeline event
  (Q24: self-reported causes always hit the timeline);
- product_start/product_stop upsert the canonical `products` table (Q28) and
  reference it from Entry.products so causality can be traced later.

Diet trigger tags (Q29) are derived here by deterministic keywords — the same
function can re-derive tags from stored text when the correlation detector runs.
"""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from .models import Entry, Product, TimelineEvent
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


def apply_events(session: Session, conv_id: str, events: list[DetectedEvent]) -> dict:
    """Write confirmed events. Idempotent-ish: same text/name on the same day is skipped."""
    today = datetime.date.today()
    entry = session.query(Entry).filter_by(conversation_id=conv_id, date=today).first()
    if entry is None:
        entry = Entry(conversation_id=conv_id, date=today)
        session.add(entry)
        session.flush()

    stats = {"diet": 0, "product": 0}
    existing_timeline = {
        (e.date, e.text, e.source)
        for e in session.query(TimelineEvent).filter_by(conversation_id=conv_id).all()
    }

    for ev in events:
        if ev.type == "diet" and ev.text.strip():
            if ev.text.strip() in entry.diet:
                continue  # already recorded today
            entry.diet = [*entry.diet, ev.text.strip()]
            stats["diet"] += 1
        elif ev.type in ("product_start", "product_stop") and ev.product_name.strip():
            prod = _get_or_create_product(session, conv_id, ev.product_name)
            stats["product"] += 1
            if ev.type == "product_start":
                if prod.id not in entry.products:
                    entry.products = [*entry.products, prod.id]
            else:
                entry.products = [p for p in entry.products if p != prod.id]
            ev.text = ev.text or ("開始用：" + prod.name if ev.type == "product_start" else "停用：" + prod.name)

        text = ev.text.strip()
        if text and (today, text, "user") not in existing_timeline:
            session.add(
                TimelineEvent(
                    conversation_id=conv_id,
                    date=today,
                    text=text,
                    source="user",
                )
            )
            existing_timeline.add((today, text, "user"))

    session.commit()
    return stats
