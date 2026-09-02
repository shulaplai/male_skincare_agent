"""Tool whitelist.

The agent may only call tools registered here — no arbitrary URLs, no code
execution. Selection happens in the `analyze` node (the model proposes tool
names); execution happens here, and unknown names are ignored.
"""
from sqlalchemy.orm import Session

from ..models import Entry, Insight, Product
from ..rag.embeddings import Embedder
from ..rag.hybrid import search_hybrid

WHITELIST = {"get_skin_profile", "get_recent_entries", "search_knowledge"}


def run_tool(name: str, state: dict, session: Session, embedder: Embedder) -> dict:
    if name == "get_skin_profile":
        # Conversation-scoped insights (derived attribute memory) PLUS global
        # insights (body-spanning facts/preferences, Q31) — the coach sees the
        # whole user, not just one body part.
        insights = (
            session.query(Insight)
            .filter(
                (Insight.conversation_id == state["conversation_id"])
                | (Insight.conversation_id.is_(None))
            )
            .filter(Insight.superseded_by.is_(None))
            .order_by(Insight.kind, Insight.tag)
            .all()
        )
        return {
            "tool": name,
            "result": [
                {
                    "kind": i.kind,
                    "text": i.text,
                    "confidence": i.confidence,
                    "scope": "global" if i.conversation_id is None else "body_part",
                }
                for i in insights
            ],
        }
    if name == "get_recent_entries":
        entries = (
            session.query(Entry)
            .filter_by(conversation_id=state["conversation_id"])
            .order_by(Entry.date.desc())
            .limit(5)
            .all()
        )
        # Resolve product ids to names so the coach can talk about products.
        prod_ids = {pid for e in entries for pid in (e.products or [])}
        products = {p.id: p.name for p in session.query(Product).filter(Product.id.in_(prod_ids))} if prod_ids else {}
        return {
            "tool": name,
            "result": [
                {
                    "date": str(e.date),
                    "note": e.note,
                    "metrics": e.metrics,
                    "diet": e.diet,
                    "products": [products.get(pid, pid) for pid in (e.products or [])],
                }
                for e in entries
            ],
        }
    if name == "search_knowledge":
        # Hybrid retrieval (semantic recall + keyword re-rank): Chinese queries
        # surface same-language chunks without BM25 flood.
        results = search_hybrid(session, state["user_text"], embedder, top_k=3)
        return {"tool": name, "result": [c.text for c, _ in results]}
    return {"tool": name, "result": None}
