"""Deterministic correlation detector (Q30) — code decides, LLM never does.

Goal: surface *candidate* associations between a confirmed cause (diet trigger
tag / product first use) and later attribute changes, honestly labelled as
observations — NOT proof of causation.

Rules (all deterministic):
- A cause (product first-use date, or a user diet event date) needs a baseline
  entry strictly BEFORE it (within BASELINE_DAYS) and at least one follow-up
  entry strictly AFTER it (within LOOKAHEAD_DAYS) before it can say anything.
- The outcome is the most extreme severity seen for an attribute inside the
  lookahead window (max severity for worsening, min for improving).
- Deltas of >= MIN_DELTA severity in the same direction, repeated across
  >= STRONG_OCCURRENCES distinct cause episodes, become a "repeated"
  candidate; fewer occurrences are reported as weak/single observations.
- Consecutive same-cause episodes within EPISODE_GAP_DAYS are clustered into
  one episode so one breakout is not double-counted by several diet events.

Pure helpers operate on plain dicts/date so the eval harness and unit tests
can drive them without a DB.
"""
from __future__ import annotations

import datetime
from collections import defaultdict

from .agent.attributes import ATTRIBUTE_KEYS

BASELINE_DAYS = 7        # baseline entry must be within this many days before the cause
LOOKAHEAD_DAYS = 4       # look for an outcome within this many days after the cause
MIN_DELTA = 1            # severity points required to call it a change
STRONG_OCCURRENCES = 2   # repeated episodes required for a "repeated" candidate
EPISODE_GAP_DAYS = 3     # cluster cause episodes closer than this

# zh labels for deterministic diet trigger tags (display + prompt text).
DIET_ZH: dict[str, str] = {
    "spicy": "辣嘢",
    "sugary": "甜嘢",
    "oily_food": "油炸嘢",
    "dairy": "奶類",
    "alcohol": "酒精",
}

ATTRIBUTE_ZH: dict[str, str] = {
    "acne": "暗瘡",
    "oiliness": "油光",
    "redness": "泛紅",
    "dryness": "乾燥",
    "pores": "毛孔",
    "texture": "質感",
}


def _closest_before(entries: list[dict], cause_date: datetime.date, attr: str, within: int) -> dict | None:
    best: dict | None = None
    for e in entries:
        d = e["date"]
        if d >= cause_date:
            continue
        if (cause_date - d).days > within:
            continue
        if attr in e["attrs"] and (best is None or d > best["date"]):
            best = e
    return best


def _outcome_in_window(entries: list[dict], cause_date: datetime.date, attr: str, within: int) -> int | None:
    """Most extreme severity for `attr` in (cause_date, cause_date+within]."""
    values = [e["attrs"][attr] for e in entries if e["date"] > cause_date and (e["date"] - cause_date).days <= within and attr in e["attrs"]]
    return max(values, default=None)


def cluster_dates(dates: list[datetime.date], gap_days: int) -> list[datetime.date]:
    """Cluster close dates into episodes, keeping the earliest date of each."""
    out: list[datetime.date] = []
    for d in sorted(dates):
        if out and (d - out[-1]).days <= gap_days:
            continue  # same episode as the previous cluster anchor
        out.append(d)
    return out


def detect_candidates(entries: list[dict], causes: list[dict]) -> list[dict]:
    """Return candidate correlations over plain data.

    entries: [{"date": date, "attrs": {key: severity}}] (ascending ok)
    causes:  [{"type": "diet"|"product", "key": str, "label": str, "date": date}]

    Candidates are grouped by (cause type+key, attribute, direction); each
    carries occurrences (episodes), avg |delta| and a `strong` flag.
    """
    # Index entries by ascending date for window scans.
    ordered = sorted(entries, key=lambda e: e["date"])
    # Cluster causes of the same type+key so one episode isn't double counted.
    by_key: dict[tuple[str, str], list[datetime.date]] = defaultdict(list)
    cause_meta: dict[tuple[str, str], dict] = {}
    for c in causes:
        by_key[(c["type"], c["key"])].append(c["date"])
        cause_meta[(c["type"], c["key"])] = c

    episodes: list[tuple[dict, datetime.date]] = []
    for (ctype, ckey), dates in by_key.items():
        for d in cluster_dates(dates, EPISODE_GAP_DAYS):
            episodes.append((cause_meta[(ctype, ckey)], d))

    # (cause_key, attribute, direction) -> stats
    agg: dict[tuple[str, str, str], dict] = {}
    for cause, cause_date in episodes:
        for attr in ATTRIBUTE_KEYS:
            base = _closest_before(ordered, cause_date, attr, BASELINE_DAYS)
            if base is None:
                continue
            outcome = _outcome_in_window(ordered, cause_date, attr, LOOKAHEAD_DAYS)
            if outcome is None:
                continue
            delta = outcome - base["attrs"][attr]
            if abs(delta) < MIN_DELTA:
                continue
            direction = "up" if delta > 0 else "down"
            key = (cause["key"], attr, direction)
            st = agg.setdefault(
                key,
                {"type": cause["type"], "key": cause["key"], "label": cause["label"], "attribute": attr,
                 "direction": direction, "deltas": [], "first": cause_date, "last": cause_date},
            )
            st["deltas"].append(abs(delta))
            st["first"] = min(st["first"], cause_date)
            st["last"] = max(st["last"], cause_date)

    candidates: list[dict] = []
    for st in agg.values():
        occurrences = len(st["deltas"])
        avg = round(sum(st["deltas"]) / occurrences, 2)
        candidates.append(
            {
                "cause_type": st["type"],
                "cause_key": st["key"],
                "cause_label": st["label"],
                "attribute": st["attribute"],
                "attribute_label": ATTRIBUTE_ZH.get(st["attribute"], st["attribute"]),
                "direction": st["direction"],
                "occurrences": occurrences,
                "avg_delta": avg,
                "first_date": str(st["first"]),
                "last_date": str(st["last"]),
                "strong": occurrences >= STRONG_OCCURRENCES,
                "note": _candidate_note(st["label"], st["attribute"], st["direction"], occurrences),
            }
        )
    # Repeated candidates first, then single observations.
    candidates.sort(key=lambda c: (not c["strong"], -c["occurrences"], c["cause_label"]))
    return candidates


def _candidate_note(cause_label: str, attr: str, direction: str, occurrences: int) -> str:
    attr_zh = ATTRIBUTE_ZH.get(attr, attr)
    if direction == "up":
        verb = "差咗"
        delta_word = "惡化"
    else:
        verb = "好咗"
        delta_word = "改善"
    base = f"「{cause_label}」之後 {attr_zh} {verb}（觀察到 {occurrences} 次）"
    if occurrences >= STRONG_OCCURRENCES:
        return base + f"：{delta_word}模式重複出現，值得留意，但唔等於因果。"
    return base + "：暫時得一次，未夠證據，繼續記錄先。"


def explain_candidates(candidates: list[dict]) -> list[str]:
    """Deterministic zh one-liners for the UI/coach (no LLM)."""
    if not candidates:
        return []
    lines = []
    for c in candidates:
        direction_zh = "惡化↑" if c["direction"] == "up" else "改善↓"
        strength = "重複觀察" if c["strong"] else "單次觀察"
        lines.append(
            f"{c['cause_label']} → {c['attribute_label']} {direction_zh} "
            f"（{c['occurrences']} 次 · 平均 {c['avg_delta']} 級 · {strength}）"
        )
    return lines


def conversation_candidates(session, conv_id: str, max_days: int | None = None) -> dict:
    """Load a conversation's real entries + causes from the DB and detect.

    Causes:
    - product: first recorded day a Product row was referenced by an Entry;
    - diet:    every user diet TimelineEvent (conversation-scoped AND global —
               diet affects every body part, Q29/Q31) whose text matches a
               known trigger tag.

    Pure after the adapter — detection itself is `detect_candidates`.
    """
    from .models import Entry, Product, TimelineEvent
    from .self_report import trigger_tags

    entries: list[dict] = []
    rows = (
        session.query(Entry)
        .filter(Entry.conversation_id == conv_id)
        .order_by(Entry.date.asc())
        .all()
    )
    for e in rows:
        sev = {a["key"]: int(a["severity"]) for a in (e.attributes or []) if a.get("key")}
        if sev:
            entries.append({"date": e.date, "attrs": sev})

    if max_days is not None:
        from datetime import timedelta

        cutoff = datetime.date.today() - timedelta(days=max_days)
        entries = [e for e in entries if e["date"] >= cutoff]

    causes: list[dict] = []
    # Product first-use: min entry date that references the product id.
    prod_rows = session.query(Product).filter(Product.conversation_id == conv_id).all()
    for p in prod_rows:
        use_dates = [e.date for e in rows if p.id in (e.products or [])]
        if use_dates:
            causes.append(
                {
                    "type": "product",
                    "key": f"product:{p.name.strip().lower()}",
                    "label": p.name.strip(),
                    "date": min(use_dates),
                }
            )
    # Diet events: conversation-scoped + global diet timeline events (Q31).
    events = (
        session.query(TimelineEvent)
        .filter(
            (TimelineEvent.conversation_id == conv_id)
            | (TimelineEvent.conversation_id.is_(None))
        )
        .filter(TimelineEvent.source == "user")
        .all()
    )
    for ev in events:
        for tag in trigger_tags(ev.text or ""):
            causes.append(
                {
                    "type": "diet",
                    "key": f"diet:{tag}",
                    "label": DIET_ZH.get(tag, tag),
                    "date": ev.date,
                }
            )

    candidates = detect_candidates(entries, causes)
    return {
        "candidates": candidates,
        "lines": explain_candidates(candidates),
        "entry_days": len(entries),
        "cause_episodes": len({(c["type"], c["key"], str(c["date"])) for c in causes}),
        "note": _summary_note(candidates, len(entries)),
    }


def _summary_note(candidates: list[dict], entry_days: int) -> str:
    if not candidates:
        if entry_days < 3:
            return "未有足夠紀錄去偵測相關性。每日影相／打卡多啲，幾日之後我就會開始比較事件前後嘅變化。"
        return "未有重複嘅「原因 → 皮膚變化」模式。會繼續觀察。"
    strong = [c for c in candidates if c["strong"]]
    if strong:
        return "偵測到重複出現嘅關聯模式（唔等於因果，但值得你留意同一時間線上有咩做過）。"
    return "暫時只係單次觀察，未夠證據落結論；繼續記錄先，同一模式出現多次我先會講。"

