"""Tool whitelist.

The agent may only call tools registered here — no arbitrary URLs, no code
execution. Selection happens in the `analyze` node (the model proposes tool
names); execution happens here, and unknown names are ignored.
"""
from sqlalchemy.orm import Session

from ..models import Entry, Insight
from ..rag.embeddings import Embedder
from ..rag.retrieve import retrieve

WHITELIST = {"get_skin_profile", "get_recent_entries", "search_knowledge"}


def run_tool(name: str, state: dict, session: Session, embedder: Embedder) -> dict:
    if name == "get_skin_profile":
        insights = (
            session.query(Insight)
            .filter_by(conversation_id=state["conversation_id"])
            .filter(Insight.superseded_by.is_(None))
            .all()
        )
        return {
            "tool": name,
            "result": [
                {"kind": i.kind, "text": i.text, "confidence": i.confidence} for i in insights
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
        return {
            "tool": name,
            "result": [{"date": str(e.date), "note": e.note, "metrics": e.metrics} for e in entries],
        }
    if name == "search_knowledge":
        results = retrieve(session, state["user_text"], embedder, top_k=3)
        return {"tool": name, "result": [c.text for c, _ in results]}
    return {"tool": name, "result": None}
