"""DB glue for product evaluation — the inputs, in one place.

`product_eval.py` is deliberately pure (doctrine #6), so it cannot read the profile
itself. This module holds the impure half, and **both** callers go through it:

* `POST /api/conversations/{cid}/products/evaluate` (explicit request), and
* the `tools` node of the consult graph (a pasted INCI list in normal chat).

If these two built their inputs separately they would eventually disagree about *whose*
profile is being matched — the same defect class as the guardrail that scanned `items`
in one place and `reply` in another (see AGENTS.md). One definition, two callers.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Conversation, Entry, Product
from .attributes import severity_map
from .product_eval import ProductEvaluation, evaluate_product
from .recommend import actives_in_name, mentions_pigmentation

#: How many recent days of free text are scanned for pigmentation mentions. Pigmentation
#: is deliberately not a 7th attribute (docs/product-eval-plan.md D7) — it comes from the
#: user's own words, so it needs a window.
NOTE_WINDOW = 7


def profile_inputs(
    session: Session, cid: str, *, pigmentation: bool | None = None
) -> dict:
    """Everything `evaluate_product` needs for this conversation.

    Returns `{"attributes", "pigmentation", "in_use", "pigmentation_source", "has_entry"}`.
    `in_use` maps ingredient key → the user's own product name, so the "you already use
    this" check can name the product they typed.
    """
    latest = (
        session.query(Entry)
        .filter_by(conversation_id=cid)
        .order_by(Entry.date.desc())
        .first()
    )
    attributes = severity_map(latest.attributes or []) if latest else {}

    recent_notes = [
        e.note or ""
        for e in session.query(Entry)
        .filter_by(conversation_id=cid)
        .order_by(Entry.date.desc())
        .limit(NOTE_WINDOW)
        .all()
    ]
    from_notes = mentions_pigmentation(" ".join(recent_notes))

    # `Product.ingredients` / `Product.category` are never written by any code path, so
    # the active is inferred from the name the user typed (plan §3.7). It is a weak
    # signal and only ever used to warn about stacking, never to recommend.
    in_use: dict[str, str] = {}
    for prod in session.query(Product).filter_by(conversation_id=cid).all():
        for key in actives_in_name(prod.name or ""):
            in_use.setdefault(key, prod.name)

    if pigmentation is None:
        source = "notes" if from_notes else "none"
        pig = from_notes
    else:
        source = "request"
        pig = pigmentation

    return {
        "attributes": attributes,
        "pigmentation": pig,
        "in_use": in_use,
        "pigmentation_source": source,
        "has_entry": latest is not None,
    }


def evaluate_for_conversation(
    session: Session,
    cid: str,
    ingredients_text: str,
    *,
    pigmentation: bool | None = None,
) -> ProductEvaluation:
    """`evaluate_product` with the conversation's profile filled in. Persists nothing."""
    if session.query(Conversation).filter_by(id=cid).first() is None:
        raise LookupError(f"conversation not found: {cid}")
    inputs = profile_inputs(session, cid, pigmentation=pigmentation)
    return evaluate_product(
        ingredients_text,
        attributes=inputs["attributes"],
        pigmentation=inputs["pigmentation"],
        in_use=inputs["in_use"],
    )


__all__ = [
    "NOTE_WINDOW",
    "evaluate_for_conversation",
    "profile_inputs",
    "summarise_evaluation",
]


def summarise_evaluation(ev: ProductEvaluation) -> dict:
    """JSON-safe view of an evaluation — the one shape both LLM callers consume.

    The route returns this to the client and `graph.advise` embeds it in its prompt, so
    the model can only ever repeat facts the deterministic core produced. Tuples become
    lists so the value survives `json.dumps` into the trace.
    """
    return {
        "verdict": ev.verdict,
        "recognised": list(ev.recognised),
        "unknown": list(ev.unknown),
        "matched": list(ev.matched),
        "missing": list(ev.missing),
        "conflicts": [{"kind": c.kind, "text": c.text} for c in ev.conflicts],
        "warnings": list(ev.recommendation.warnings),
        "suggestions": [
            {"key": s.key, "zh": s.zh, "tier": s.tier, "reasons": list(s.reasons)}
            for s in ev.recommendation.suggestions
        ],
        "triggers": list(ev.recommendation.triggers),
        "escalate": ev.escalate,
        "disclaimer": ev.disclaimer,
    }
