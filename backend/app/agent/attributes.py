"""Fixed attribute schema + deterministic change detection (Q21/Q22/Q24).

The agent rates the SAME fixed set of attributes every analysis (0–3 severity),
so:
- change detection is a deterministic code diff over historical entries
  (Q21C — the vision model only ever looks at the current photo);
- memory reconcile later compares tag + direction (Q14) on this same schema.

Timeline policy (Q24): self-reported events are always written by the caller;
AI-detected changes are written ONLY when they clear NOTABLE_DELTA and the
severity is at/above NOTABLE_FLOOR — so the timeline stays sparse and causal,
not a daily noise log.
"""
from __future__ import annotations

import datetime

from ..memory import DIRECTION_NORMAL, DIRECTION_PROBLEM
from ..models import Entry
from .schemas import AttributeKey

ATTRIBUTE_KEYS: list[AttributeKey] = [
    "acne",
    "oiliness",
    "redness",
    "dryness",
    "pores",
    "texture",
]

# zh labels for display / prompt text.
ATTRIBUTE_LABELS: dict[AttributeKey, str] = {
    "acne": "暗瘡",
    "oiliness": "油光",
    "redness": "泛紅",
    "dryness": "乾燥",
    "pores": "毛孔",
    "texture": "質感",
}

NOTABLE_DELTA = 1  # severity points required for an AI-detected timeline event
NOTABLE_FLOOR = 2  # at least one side must be >= this severity (avoids 0<->1 noise)

# Anchor windows for rolling comparison (Q12): ~1 month and ~3 months, with a
# tolerance of ~1 week to fall back to the nearest available entry.
MONTH_WINDOW_DAYS = 28
QUARTER_WINDOW_DAYS = 90
ANCHOR_TOLERANCE_DAYS = 7


def severity_map(attributes: list[dict]) -> dict[str, int]:
    """{attribute key -> severity} for an Entry.attributes JSON list."""
    return {a["key"]: int(a["severity"]) for a in attributes if a.get("key")}


def attribute_severity_text(sev: int) -> str:
    return {0: "正常", 1: "輕微", 2: "中等", 3: "嚴重"}.get(sev, "正常")


def direction_for(severity: int) -> str:
    """State category for memory (Q47): >=2 is a problem, <=1 is normal."""
    return DIRECTION_PROBLEM if severity >= 2 else DIRECTION_NORMAL


def describe_attribute(key: AttributeKey, severity: int) -> str:
    """Human text for a derived memory insight, e.g. 「暗瘡：中等」."""
    label = ATTRIBUTE_LABELS.get(key, key)
    return f"{label}：{attribute_severity_text(severity)}"


def _day(entry: Entry) -> datetime.date:
    return entry.date


def diff_attributes(current: dict[str, int], previous: dict[str, int]) -> list[dict]:
    """Per-attribute delta between two severity maps (only differing keys)."""
    out: list[dict] = []
    for key in ATTRIBUTE_KEYS:
        new = current.get(key)
        old = previous.get(key)
        if new is None or old is None:
            continue
        delta = new - old
        if delta != 0:
            out.append(
                {
                    "key": key,
                    "label": ATTRIBUTE_LABELS[key],
                    "old": old,
                    "new": new,
                    "delta": delta,
                }
            )
    return out


def is_notable(change: dict) -> bool:
    return abs(change["delta"]) >= NOTABLE_DELTA and max(change["old"], change["new"]) >= NOTABLE_FLOOR


def find_previous_entry(entries: list[Entry], today: datetime.date) -> Entry | None:
    """Most recent entry strictly before `today` (if any)."""
    older = [e for e in entries if _day(e) < today]
    if not older:
        return None
    return max(older, key=_day)


def find_anchor_entry(entries: list[Entry], today: datetime.date, days_ago: int) -> Entry | None:
    """Closest entry to `today - days_ago`, within ANCHOR_TOLERANCE_DAYS (Q12)."""
    target = today - datetime.timedelta(days=days_ago)
    best: Entry | None = None
    best_gap = ANCHOR_TOLERANCE_DAYS + 1
    for e in entries:
        if _day(e) >= today:
            continue
        gap = abs((target - _day(e)).days)
        if gap < best_gap:
            best_gap = gap
            best = e
    return best if best_gap <= ANCHOR_TOLERANCE_DAYS else None


def describe_change(change: dict, *, anchor_label: str) -> str:
    """One deterministic zh timeline line for a change vs an anchor."""
    label = change["label"]
    verb = "惡化" if change["delta"] > 0 else "改善"
    arrow = "↑" if change["delta"] > 0 else "↓"
    return (
        f"{label} {verb}{arrow}（{attribute_severity_text(change['old'])} → "
        f"{attribute_severity_text(change['new'])}，{anchor_label}）"
    )


def build_change_lines(
    current: dict[str, int],
    entries: list[Entry],
    today: datetime.date,
) -> list[str]:
    """Deterministic timeline lines: vs previous entry + vs 1M/3M anchors.

    Only notable changes (Q24 threshold) are reported. Returns [] when nothing
    notable changed.
    """
    lines: list[str] = []
    emitted: set[tuple[str, int]] = set()

    prev = find_previous_entry(entries, today)
    if prev is not None:
        old = severity_map(prev.attributes or [])
        for c in diff_attributes(current, old):
            if is_notable(c):
                lines.append(describe_change(c, anchor_label="同上次比"))
                emitted.add((c["key"], c["delta"]))

    for days_ago, label in (
        (MONTH_WINDOW_DAYS, "同約 1 個月前比"),
        (QUARTER_WINDOW_DAYS, "同約 3 個月前比"),
    ):
        anchor = find_anchor_entry(entries, today, days_ago)
        if anchor is None:
            continue
        old = severity_map(anchor.attributes or [])
        for c in diff_attributes(current, old):
            # Skip changes already reported against a closer anchor so the
            # timeline stays sparse (Q24).
            if (c["key"], c["delta"]) in emitted:
                continue
            if is_notable(c):
                lines.append(describe_change(c, anchor_label=label))
                emitted.add((c["key"], c["delta"]))

    return lines


def anchor_comparisons(current: dict[str, int], entries: list[Entry], today: datetime.date) -> list[dict]:
    """Per-attribute severities vs the previous / ~1M / ~3M anchor entries.

    Pure presentation data for the "rolling multi-anchor" UI (Q12): the UI
    renders each attribute's latest value next to the closest available anchor
    (within ANCHOR_TOLERANCE_DAYS) so users can see both the near-term trend
    and the longer baseline without the backend repeating any LLM work.
    """
    out: list[dict] = []
    prev = find_previous_entry(entries, today)
    month = find_anchor_entry(entries, today, MONTH_WINDOW_DAYS)
    quarter = find_anchor_entry(entries, today, QUARTER_WINDOW_DAYS)

    for key in ATTRIBUTE_KEYS:
        if key not in current:
            continue
        sev = current[key]
        row: dict = {"key": key, "label": ATTRIBUTE_LABELS[key], "severity": sev}
        for name, anchor in (("prev", prev), ("month", month), ("quarter", quarter)):
            if anchor is None:
                row[name] = None
                continue
            old = severity_map(anchor.attributes or []).get(key)
            if old is None:
                row[name] = None
            else:
                row[name] = {"date": str(anchor.date), "old": old, "delta": sev - old}
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Same-day merge (issue #21 policy B)
# ---------------------------------------------------------------------------
#
# One `Entry` per day per conversation (doctrine: Entry = the day's structured
# summary). A second check-in the same day used to replace `attributes` and
# `metrics` wholesale, so a message that mentioned one attribute silently reset the
# other five to 0 — the anchors, the derived memories and the product verdict all
# read those values (measured: acne 2→1 flipped a product from `good` to `caution`
# because `recommend.TRIGGER_FLOOR` is 2).
#
# Policy B: a later check-in only replaces the readings it actually mentioned.
# `Attribute.mentioned` is the signal (the LLM says which attributes this turn is
# about); an attribute it did not mention keeps the day's existing reading.


def merge_attributes(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], list[str]]:
    """Same-day merge of the day's readings.

    Returns `(merged, kept)` where `kept` lists the attribute keys carried over from
    an earlier turn (useful in the run trace). Output order is the fixed
    `ATTRIBUTE_KEYS` order, so the stored JSON stays stable.
    """
    old = {a["key"]: a for a in (existing or []) if a.get("key")}
    new = {a["key"]: a for a in (incoming or []) if a.get("key")}
    merged: list[dict] = []
    kept: list[str] = []
    for key in ATTRIBUTE_KEYS:
        n = new.get(key)
        o = old.get(key)
        if n is not None and (n.get("mentioned", True) or o is None):
            merged.append(dict(n))
        elif o is not None:
            merged.append(dict(o))
            kept.append(key)
        elif n is not None:
            merged.append(dict(n))
    return merged, kept


def merge_metrics(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Same-day merge of the display list, by metric key.

    `Metric` keys are the model's own free text（「油光」「新暗瘡」）and are display-only
    (they never feed change detection, memory or the timeline). Rows for things this
    turn did not talk about are kept, so the day's card does not lose the morning's
    observations — the same "唔講就唔抹" rule as the attributes above.
    """
    merged = [dict(m) for m in (existing or [])]
    index = {m["key"]: i for i, m in enumerate(merged) if m.get("key")}
    for m in incoming or []:
        key = m.get("key")
        if key and key in index:
            merged[index[key]] = dict(m)
        else:
            merged.append(dict(m))
            if key:
                index[key] = len(merged) - 1
    return merged


def merge_note(existing: str, incoming: str) -> str:
    """The day keeps everything the user said, in order (one Entry per day).

    The old code assigned `entry.note = user_text`, so a later partial check-in erased
    the morning's sentence — the same loss the readings suffered. Appending keeps the
    day's note honest; the user can still edit it afterwards
    (`PATCH /api/conversations/{cid}/entries/{eid}/note`).
    """
    old = (existing or "").strip()
    new = (incoming or "").strip()
    if not new or new == old:
        return old or new
    if not old:
        return new
    if new in old.split("\n"):
        return old
    return f"{old}\n{new}"
