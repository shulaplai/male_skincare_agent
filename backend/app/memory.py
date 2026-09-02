"""Long-term memory rules (deterministic core, no LLM).

This mirrors the SKINFILE concept but as pure, testable functions that operate on
the `Insight` ORM shape via dataclasses. The agent (Phase 3) calls these to decide
how new evidence updates memory; the LLM never decides decay/contradiction — code does.

Rules:
- derived insights expire after DECAY_DAYS.
- reconcile(): new evidence on the same tag either strengthens confidence
  (consistent) or supersedes the old version (contradiction), keeping history.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, replace

DECAY_DAYS = 30
MAX_CONFIDENCE = 0.97
CONFIDENCE_STEP = 0.05


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
    direction: str = ""  # better | worse | same (derived attribute trends)


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


def is_expired(insight: MemoryInsight, now: datetime.datetime) -> bool:
    return insight.expires_at is not None and now >= insight.expires_at


def reconcile(
    existing: MemoryInsight,
    candidate: MemoryInsight,
    now: datetime.datetime,
) -> list[MemoryInsight]:
    """Return the insights that should replace `existing` + `candidate`.

    - Non-derived, or different tags: leave both unchanged.
    - Same tag + same text: strengthen confidence, extend expiry, return one.
    - Same tag + different text: supersede old (keep history), version+1 on new.
    """
    if existing.kind != "derived" or candidate.kind != "derived":
        return [existing, candidate]
    if existing.tag != candidate.tag:
        return [existing, candidate]

    if existing.text == candidate.text:
        base = existing.confidence or 0.0
        new_conf = round(
            min(MAX_CONFIDENCE, max(base, candidate.confidence or 0.0, base + CONFIDENCE_STEP)), 2
        )
        strengthened = replace(existing, confidence=new_conf, expires_at=expiry_for(now))
        return [strengthened]

    old = replace(existing, superseded_by=candidate.id)
    new = replace(
        candidate,
        version=existing.version + 1,
        confidence=round(min(candidate.confidence or 0.0, MAX_CONFIDENCE), 2),
        expires_at=expiry_for(now),
    )
    return [old, new]
