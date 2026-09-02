"""LangGraph state graph — the deterministic skeleton that "controls" the LLM.

Flow:
    START -> analyze -> tools -> advise -> guardrail -> persist -> END

Each node is a plain function that returns a partial state update. The LLM only
appears in `analyze` and `advise` (the "fuzzy" layers); memory read, tool
dispatch, guardrails, change detection and persistence are all deterministic
code.

Vision policy (Q18/Q23/Q40/Q41):
- analyze sends the photo to a vision model ONLY when the conversation has
  opted in (`cloud_analysis=True`) AND a photo is attached AND a real LLM is
  configured. Otherwise it runs a text-only analysis on the cheap text model
  and marks `vision_used=False` — privacy never depends on the model behaving.
- If the vision call itself fails, we degrade to text-only rather than crash.

Persistence (Q21C/Q24/Q38): the day's Entry is auto-upserted (photo / text
interactions both count), the fixed-schema attributes are stored, and notable
changes vs history are written to the timeline by deterministic code.
"""
import datetime

from langgraph.graph import END, START, StateGraph

from ..models import (
    ChatMessage,
    Conversation,
    Entry,
    Insight,
    Photo,
    TimelineEvent,
    new_id,
    utcnow,
)
from .attributes import build_change_lines, severity_map
from .guardrails import apply_guardrails
from .llm import FakeLLM
from .prompts import ADVISE_SYSTEM, ANALYZE_SYSTEM, build_advise_prompt, build_analyze_prompt
from .schemas import Advice, SkinAnalysis
from .state import AgentState
from .tools import run_tool
from ..memory import from_orm, expiry_for, is_expired, make_derived, reconcile
from ..photo import load_photo_b64, photo_exists


def _text_only_analysis(llm, state, has_photo: bool) -> SkinAnalysis:
    return llm.structured(
        ANALYZE_SYSTEM,
        build_analyze_prompt(state["user_text"], has_photo, photo_viewed=False),
        SkinAnalysis,
    )


def build_graph(*, llm: FakeLLM, session_factory, embedder, vision_llm: FakeLLM | None = None):
    # Model tiering (Q20): photo analysis goes to the vision model when the
    # user opted in; everything else (advice, …) uses the plain text model.
    vllm = vision_llm or llm

    def analyze(state: AgentState) -> dict:
        has_photo = bool(state.get("photo_paths"))
        consent = bool(state.get("cloud_analysis"))
        vision = has_photo and consent and not isinstance(vllm, FakeLLM)

        analysis = None
        if vision:
            images = [
                img
                for pid in state["photo_paths"]
                if (img := load_photo_b64(pid)) is not None
            ]
            if images:
                try:
                    analysis = vllm.structured_vision(
                        ANALYZE_SYSTEM,
                        build_analyze_prompt(state["user_text"], True, photo_viewed=True),
                        SkinAnalysis,
                        images,
                    )
                except Exception:
                    analysis = None  # degrade to text-only, never crash

        if analysis is None:
            analysis = _text_only_analysis(llm, state, has_photo)
            vision = False
        return {"analysis": analysis.model_dump(), "vision_used": vision}

    def tools(state: AgentState) -> dict:
        session = session_factory()
        try:
            results = []
            for name in state["analysis"].get("tool_calls", []):
                results.append(run_tool(name, state, session, embedder))

            # Recent chat turns become context for this advice (Q39: stateless
            # consult + recent-messages context, so "我頭先講嘅嘢" still works).
            recent = (
                session.query(ChatMessage)
                .filter_by(conversation_id=state["conversation_id"])
                .order_by(ChatMessage.id.desc())
                .limit(10)
                .all()
            )
            recent_messages = []
            for m in reversed(recent):
                who = "你" if m.role == "user" else "教練"
                recent_messages.append(f"{who}：{m.text}")

            # First check-in = no entries at all yet (its photo becomes the
            # baseline). Drives a more detailed onboarding-style reply.
            has_entries = (
                session.query(Entry.id).filter_by(conversation_id=state["conversation_id"]).first()
            )
            return {
                "tool_results": results,
                "recent_messages": recent_messages,
                "first_checkin": has_entries is None,
            }
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
            now = utcnow()

            entry = session.query(Entry).filter_by(conversation_id=conv_id, date=today).first()
            if entry is None:
                entry = Entry(conversation_id=conv_id, date=today)
                session.add(entry)
                session.flush()  # assign entry.id before attaching photos
            entry.note = state["user_text"]
            entry.metrics = [m.model_dump() for m in analysis.metrics]
            entry.attributes = [a.model_dump() for a in analysis.attributes]

            # Photos attach to the day's entry once (dedupe by file name); only
            # photos that actually exist on disk are linked (no dangling rows).
            existing_photo_names = {p.path for p in entry.photos}
            for pid in state.get("photo_paths", []):
                if not photo_exists(pid):
                    continue
                if f"photos/{pid}.jpg" not in existing_photo_names:
                    session.add(Photo(entry_id=entry.id, path=f"photos/{pid}.jpg"))
                    existing_photo_names.add(f"photos/{pid}.jpg")
            session.flush()

            # Timeline: deterministic change detection (Q24 — sparse, notable
            # changes only; one agent event per conversation per day at most).
            existing_agent_event = (
                session.query(TimelineEvent)
                .filter_by(conversation_id=conv_id, date=today, source="agent")
                .first()
            )
            if existing_agent_event is None:
                history = (
                    session.query(Entry)
                    .filter(Entry.conversation_id == conv_id, Entry.date < today)
                    .order_by(Entry.date.asc())
                    .all()
                )
                lines = build_change_lines(severity_map(entry.attributes or []), history, today)
                if lines:
                    session.add(
                        TimelineEvent(
                            conversation_id=conv_id,
                            date=today,
                            text="；".join(lines),
                            source="agent",
                        )
                    )

            # Long-term memory (derived "recent_status" summary for now; the
            # per-attribute tag+direction rewrite lands with the memory block).
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
                                direction=r.direction,
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
                        direction="",
                        text=analysis.summary,
                        confidence=0.6,
                        expires_at=expiry_for(now),
                        version=1,
                    )
                )

            # Chat turns (Q7/Q35): persist user message + coach reply so the
            # thread survives a reload. The coach payload carries everything the
            # UI needs to re-render the reply identically.
            advice = state.get("advice") or {}
            reply_text = advice.get("reply") or analysis.summary
            session.add(
                ChatMessage(
                    conversation_id=conv_id,
                    role="user",
                    text=state["user_text"],
                    payload={"photos": state.get("photo_paths", [])},
                )
            )
            session.add(
                ChatMessage(
                    conversation_id=conv_id,
                    role="coach",
                    text=reply_text,
                    payload={
                        "summary": analysis.summary,
                        "reply": advice.get("reply", ""),
                        "metrics": [m.model_dump() for m in analysis.metrics],
                        "attributes": [a.model_dump() for a in analysis.attributes],
                        "advice": advice.get("items", []),
                        "disclaimer": advice.get("disclaimer", ""),
                        "escalate": bool(state.get("escalate")),
                        "vision_used": bool(state.get("vision_used")),
                    },
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
