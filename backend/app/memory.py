"""Long-term memory rules (deterministic core, no LLM).

Mirrors the SKINFILE concept but as pure, testable functions operating on the
`Insight` ORM shape via dataclasses. The agent calls these to decide how new
evidence updates memory; the LLM never decides decay/contradiction — code does.

Rules (Q14/Q47):
- derived insights expire after DECAY_DAYS.
- reconcile() compares **tag + direction** (not text):
    same tag + same direction → strengthen (confidence up, expiry extended,
      text refreshed to the latest observation);
    same tag + different direction → supersede (old keeps history with
      superseded_by, new gets version+1);
    different tags / non-derived kinds → both left untouched.
Direction for skin attributes: `problem` (severity ≥ 2) vs `normal` (≤ 1) —
the *state category*, not the trend (trends live in the entries timeline).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, replace

DECAY_DAYS = 30
MAX_CONFIDENCE = 0.97
CONFIDENCE_STEP = 0.05

# Derived attribute directions (Q47).
DIRECTION_PROBLEM = "problem"
DIRECTION_NORMAL = "normal"


@dataclass
class MemoryInsight:
    id: str
    kind: str  # fact | derived | preference
    tag: str
    text: str
    confidence: float | None = None
    expires_at: datetime.datetime | None = None
    superseded_by: str | None = None
    version: int = 1
    direction: str = ""  # derived: problem | normal (see DIRECTION_*)


def expiry_for(now: datetime.datetime) -> datetime.datetime:
    return now + datetime.timedelta(days=DECAY_DAYS)


def from_orm(insight) -> MemoryInsight:
    """Adapt an ORM Insight (duck-typed) into a MemoryInsight for reconcile()."""
    return MemoryInsight(
        id=insight.id,
        kind=insight.kind,
        tag=insight.tag,
        text=insight.text,
        confidence=insight.confidence,
        expires_at=insight.expires_at,
        superseded_by=insight.superseded_by,
        version=insight.version,
        direction=getattr(insight, "direction", ""),
    )


def make_derived(
    id: str,
    tag: str,
    text: str,
    confidence: float,
    now: datetime.datetime,
    direction: str = "",
) -> MemoryInsight:
    return MemoryInsight(
        id=id,
        kind="derived",
        tag=tag,
        text=text,
        confidence=round(min(max(confidence, 0.0), MAX_CONFIDENCE), 2),
        expires_at=expiry_for(now),
        direction=direction,
    )


def make_fact(
    id: str,
    text: str,
    tag: str = "user_fact",
) -> MemoryInsight:
    """A ground-truth fact (self-reported, Q25): never expires, never versions."""
    return MemoryInsight(id=id, kind="fact", tag=tag, text=text, confidence=None)


def is_expired(insight: MemoryInsight, now: datetime.datetime) -> bool:
    return insight.expires_at is not None and now >= insight.expires_at


def reconcile(
    existing: MemoryInsight,
    candidate: MemoryInsight,
    now: datetime.datetime,
) -> list[MemoryInsight]:
    """Return the insights that should replace `existing` + `candidate`.

    - Non-derived, or different tags: leave both unchanged.
    - Same tag + same direction: strengthen the existing one (confidence up,
      expiry extended, text refreshed to the candidate's) — one result.
    - Same tag + different direction: supersede old (keep history), version+1
      on the new one — two results.
    """
    if existing.kind != "derived" or candidate.kind != "derived":
        return [existing, candidate]
    if existing.tag != candidate.tag:
        return [existing, candidate]

    if existing.direction == candidate.direction:
        base = existing.confidence or 0.0
        new_conf = round(
            min(MAX_CONFIDENCE, max(base, candidate.confidence or 0.0, base + CONFIDENCE_STEP)), 2
        )
        strengthened = replace(
            existing,
            confidence=new_conf,
            text=candidate.text,  # refresh to the latest observation
            expires_at=expiry_for(now),
        )
        return [strengthened]

    old = replace(existing, superseded_by=candidate.id)
    new = replace(
        candidate,
        version=existing.version + 1,
        confidence=round(min(candidate.confidence or 0.0, MAX_CONFIDENCE), 2),
        expires_at=expiry_for(now),
    )
    return [old, new]
