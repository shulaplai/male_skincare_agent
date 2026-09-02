"""Preference extraction — deterministic + throttled (Q13/Q48).

"Preferences" are the stable, low-churn memory tier ("鍾意清爽質地"). The LLM
never decides memory here: code derives a preference only from *repeated*
confirmed evidence, so it changes slowly and never churns per message.

Rules:
- diet trigger tag seen on >= DIET_MIN_DAYS distinct days in the rolling window
  -> global preference "近排成日食<label>" (diet affects every body part);
- product referenced on >= PRODUCT_MIN_DAYS distinct days in the window
  -> conversation-scoped preference "常用產品：<name>".

Extraction is *throttled* by writing only when the candidate text differs from
the currently active preference with the same tag — a repeat day that adds no
new information writes nothing, so at most one row per tag per change.
"""
from __future__ import annotations

import datetime

PREFERENCE_WINDOW_DAYS = 21
DIET_MIN_DAYS = 3
PRODUCT_MIN_DAYS = 3

DIET_ZH: dict[str, str] = {
    "spicy": "辣嘢",
    "sugary": "甜嘢",
    "oily_food": "油炸嘢",
    "dairy": "奶類",
    "alcohol": "酒精",
}


def _within(dates: list[datetime.date], window_days: int) -> int:
    today = datetime.date.today()
    return len({d for d in dates if (today - d).days <= window_days})


def _active(session, tag: str, conversation_id: str | None):
    from .models import Insight

    return (
        session.query(Insight)
        .filter_by(conversation_id=conversation_id, kind="preference", tag=tag)
        .filter(Insight.superseded_by.is_(None))
        .first()
    )


def _upsert(session, conversation_id: str | None, tag: str, text: str, written: list) -> None:
    """Write one preference row per (scope, tag) only when text changed."""
    cur = _active(session, tag, conversation_id)
    if cur is not None:
        if cur.text == text:
            return  # throttled: no new information
        cur.text = text  # evidence grew: refresh in place (still one row)
        written.append(cur)
        return
    from .models import Insight

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    new = Insight(
        conversation_id=conversation_id,
        kind="preference",
        tag=tag,
        direction="",
        text=text,
        confidence=None,
        created_at=now,
    )
    session.add(new)
    written.append(new)


def extract_preferences(session, conv_id: str) -> dict:
    """Scan confirmed diet + product evidence and upsert preference insights.

    Returns {"written": <count>}. Deterministic; at most one write per
    (scope, tag) per change because identical text is skipped.
    """
    from .models import Entry, Product, TimelineEvent
    from .self_report import trigger_tags

    written: list = []

    # --- Diet: count distinct days per trigger tag across conv + global events.
    events = (
        session.query(TimelineEvent)
        .filter(
            (TimelineEvent.conversation_id == conv_id)
            | (TimelineEvent.conversation_id.is_(None))
        )
        .filter(TimelineEvent.source == "user")
        .all()
    )
    days_by_tag: dict[str, list[datetime.date]] = {}
    for ev in events:
        for tag in trigger_tags(ev.text or ""):
            days_by_tag.setdefault(tag, []).append(ev.date)
    for tag, dates in days_by_tag.items():
        n = _within(dates, PREFERENCE_WINDOW_DAYS)
        if n < DIET_MIN_DAYS:
            continue
        zh = DIET_ZH.get(tag, tag)
        text = f"近排成日食{zh}（最近 {PREFERENCE_WINDOW_DAYS} 日內 {n} 日）"
        _upsert(session, None, f"diet:{tag}", text, written)  # global

    # --- Products: count distinct days an entry references the product.
    entries = (
        session.query(Entry)
        .filter(Entry.conversation_id == conv_id)
        .order_by(Entry.date.asc())
        .all()
    )
    products = session.query(Product).filter(Product.conversation_id == conv_id).all()
    for prod in products:
        days = [e.date for e in entries if prod.id in (e.products or [])]
        n = _within(days, PREFERENCE_WINDOW_DAYS)
        if n < PRODUCT_MIN_DAYS:
            continue
        text = f"常用產品：{prod.name.strip()}（最近 {PREFERENCE_WINDOW_DAYS} 日內 {n} 日）"
        _upsert(session, conv_id, f"product:{prod.name.strip().lower()}", text, written)

    session.commit()
    return {"written": len(written)}
