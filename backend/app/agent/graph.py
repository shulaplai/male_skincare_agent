"""LangGraph state graph — the deterministic skeleton that "controls" the LLM.

Flow:
    START -> analyze -> tools -> advise -> guardrail -> persist -> END

Each node is a plain function that returns a partial state update. The LLM only
appears in `analyze` and `advise` (the "fuzzy" layers); memory read, tool
dispatch, guardrails and persistence are all deterministic code.
"""
import datetime

from langgraph.graph import END, START, StateGraph

from ..models import Entry, Insight, new_id, utcnow
from .guardrails import apply_guardrails
from .llm import FakeLLM
from .prompts import ADVISE_SYSTEM, ANALYZE_SYSTEM, build_advise_prompt, build_analyze_prompt
from .schemas import Advice, SkinAnalysis
from .state import AgentState
from .tools import run_tool
from ..memory import from_orm, expiry_for, is_expired, make_derived, reconcile


def build_graph(*, llm: FakeLLM, session_factory, embedder):
    def analyze(state: AgentState) -> dict:
        analysis = llm.structured(
            ANALYZE_SYSTEM,
            build_analyze_prompt(state["user_text"], bool(state.get("photo_paths"))),
            SkinAnalysis,
        )
        return {"analysis": analysis.model_dump()}

    def tools(state: AgentState) -> dict:
        session = session_factory()
        try:
            results = []
            for name in state["analysis"].get("tool_calls", []):
                results.append(run_tool(name, state, session, embedder))
            return {"tool_results": results}
        finally:
            session.close()

    def advise(state: AgentState) -> dict:
        advice = llm.structured(ADVISE_SYSTEM, build_advise_prompt(state), Advice)
        return {"advice": advice.model_dump()}

    def guardrail(state: AgentState) -> dict:
        advice = Advice(**state["advice"])
        final, escalate = apply_guardrails(advice, state["user_text"])
        return {"advice": final.model_dump(), "escalate": escalate}

    def persist(state: AgentState) -> dict:
        session = session_factory()
        try:
            analysis = SkinAnalysis(**state["analysis"])
            conv_id = state["conversation_id"]
            today = datetime.date.today()

            entry = session.query(Entry).filter_by(conversation_id=conv_id, date=today).first()
            if entry is None:
                entry = Entry(conversation_id=conv_id, date=today)
                session.add(entry)
            entry.note = state["user_text"]
            entry.metrics = [m.model_dump() for m in analysis.metrics]
            session.flush()

            now = utcnow()
            candidate = make_derived(new_id(), "recent_status", analysis.summary, 0.6, now)
            existing = (
                session.query(Insight)
                .filter_by(conversation_id=conv_id, kind="derived", tag="recent_status")
                .order_by(Insight.version.desc())
                .first()
            )
            if existing and existing.superseded_by is None and not is_expired(from_orm(existing), now):
                for r in reconcile(from_orm(existing), candidate, now):
                    if r.id == existing.id:
                        existing.confidence = r.confidence
                        existing.expires_at = r.expires_at
                        existing.superseded_by = r.superseded_by
                    elif r.id == candidate.id:
                        session.add(
                            Insight(
                                conversation_id=conv_id,
                                kind=r.kind,
                                tag=r.tag,
                                text=r.text,
                                confidence=r.confidence,
                                expires_at=r.expires_at,
                                version=r.version,
                            )
                        )
            else:
                session.add(
                    Insight(
                        conversation_id=conv_id,
                        kind="derived",
                        tag="recent_status",
                        text=analysis.summary,
                        confidence=0.6,
                        expires_at=expiry_for(now),
                        version=1,
                    )
                )
            session.commit()
        finally:
            session.close()
        return {}

    g = StateGraph(AgentState)
    g.add_node("analyze", analyze)
    g.add_node("tools", tools)
    g.add_node("advise", advise)
    g.add_node("guardrail", guardrail)
    g.add_node("persist", persist)
    g.add_edge(START, "analyze")
    g.add_edge("analyze", "tools")
    g.add_edge("tools", "advise")
    g.add_edge("advise", "guardrail")
    g.add_edge("guardrail", "persist")
    g.add_edge("persist", END)
    return g.compile()
