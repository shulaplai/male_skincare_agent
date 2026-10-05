"""LangGraph state graph — the deterministic skeleton that "controls" the LLM.

Flow:
    START -> analyze -> tools -> advise -> guardrail -> persist -> END

Each node is a plain function that returns a partial state update. The LLM only
appears in `analyze` and `advise` (the "fuzzy" layers); memory read, tool
dispatch, guardrails, change detection and persistence are all deterministic
code.

Debugging: every node appends one entry to `state["trace"]` (node, duration,
small summary) — no silent degradation. `graph.stream()` yields the per-node
deltas live, and `/api/consult` returns the final trace, so a wrong-looking reply
can be traced to the exact stage (see `scripts/trace_consult.py`).

Vision policy (Q18/Q23/Q40/Q41):
- analyze sends the photo to a vision model ONLY when the conversation has
  opted in (`cloud_analysis=True`) AND a photo is attached AND a real LLM is
  configured. Otherwise it runs a text-only analysis on the cheap text model
  and marks `vision_used=False` — privacy never depends on the model behaving.
- If the vision call itself fails, we degrade to text-only rather than crash,
  but the failure is logged and recorded in the run trace (never swallowed).

Persistence (Q21C/Q24/Q38): the day's Entry is auto-upserted (photo / text
interactions both count), the fixed-schema attributes are stored, and notable
changes vs history are written to the timeline by deterministic code.
"""
import datetime
import logging
import time

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
from .attributes import (
    build_change_lines,
    describe_attribute,
    direction_for,
    merge_attributes,
    merge_metrics,
    merge_note,
    severity_map,
)
from .guardrails import apply_guardrails
from .ingredients import looks_like_ingredient_list
from .llm import FakeLLM
from .product_context import evaluate_for_conversation, summarise_evaluation
from .prompts import ADVISE_SYSTEM, ANALYZE_SYSTEM, build_advise_prompt, build_analyze_prompt
from .schemas import Advice, SkinAnalysis
from .state import AgentState, TraceStep
from .tools import WHITELIST, run_tool
from ..memory import from_orm, expiry_for, is_expired, make_derived, reconcile
from ..photo import load_photo_b64, photo_exists

logger = logging.getLogger(__name__)


def _step(node: str, started: float, detail: dict) -> TraceStep:
    """One trace entry for a finished node (kept small — no full prompts/photos)."""
    return {
        "node": node,
        "ms": round((time.perf_counter() - started) * 1000, 1),
        "keys": sorted(detail.keys()),
        "detail": detail,
    }


def _text_only_analysis(
    llm, state, has_photo: bool, photo_unreadable: bool = False
) -> SkinAnalysis:
    return llm.structured(
        ANALYZE_SYSTEM,
        build_analyze_prompt(
            state["user_text"], has_photo, photo_viewed=False, photo_unreadable=photo_unreadable
        ),
        SkinAnalysis,
    )


def build_graph(*, llm: FakeLLM, session_factory, embedder, vision_llm: FakeLLM | None = None):
    # Model tiering (Q20): photo analysis goes to the vision model when the
    # user opted in; everything else (advice, …) uses the plain text model.
    vllm = vision_llm or llm

    def analyze(state: AgentState) -> dict:
        started = time.perf_counter()
        has_photo = bool(state.get("photo_paths"))
        consent = bool(state.get("cloud_analysis"))
        vision = has_photo and consent and not isinstance(vllm, FakeLLM)

        analysis = None
        vision_error: str | None = None
        images_loaded = 0
        # Whether the vision branch is *entered* is a different fact from whether it
        # produced an analysis. Computing this after the `vision = False` fallback
        # below is what used to report `vision_attempted: False` for a photo the code
        # had actually tried to read — a trace that misleads whoever debugs it.
        vision_attempted = bool(has_photo and consent and not isinstance(vllm, FakeLLM))
        if vision:
            images = [
                img
                for pid in state["photo_paths"]
                if (img := load_photo_b64(pid)) is not None
            ]
            images_loaded = len(images)
            if images:
                try:
                    analysis = vllm.structured_vision(
                        ANALYZE_SYSTEM,
                        build_analyze_prompt(
                            state["user_text"], True, photo_viewed=True, clip=state.get("clip")
                        ),
                        SkinAnalysis,
                        images,
                    )
                except Exception as e:  # degrade to text-only, but never silently
                    vision_error = f"{type(e).__name__}: {e}"
                    logger.warning("vision analysis failed,降級做純文字: %s", vision_error)
                    analysis = None

        # A photo we could not read is not "no photo" and not "local mode": consent was
        # granted and the bytes were requested, the file just failed to load. Pass that
        # through so the model gets an accurate reason instead of a false privacy claim.
        photo_unreadable = vision_attempted and images_loaded == 0
        if analysis is None:
            analysis = _text_only_analysis(llm, state, has_photo, photo_unreadable)
            vision = False
        if photo_unreadable:
            vision_reason = "photo_unreadable"
        elif vision_error:
            vision_reason = "vision_error"
        elif vision:
            vision_reason = "used"
        elif has_photo and not consent:
            vision_reason = "consent_off"
        elif has_photo and isinstance(vllm, FakeLLM):
            vision_reason = "fake_llm"
        else:
            vision_reason = "no_photo"
        return {
            "analysis": analysis.model_dump(),
            "vision_used": vision,
            # Declared into state, not only into the trace detail below:
            # `build_advise_prompt` reads it to decide whether the model may claim to
            # have seen a photo, and to add the「下次影相／拍片」nudge on a non-first
            # text-only check-in. It lived in the trace alone for a while, so both
            # reads silently saw `None` on the real path while the prompt tests passed
            # by constructing the key themselves (state.py has the full note).
            "vision_reason": vision_reason,
            "trace": [
                _step(
                    "analyze",
                    started,
                    {
                        "has_photo": has_photo,
                        "cloud_consent": consent,
                        "vision_attempted": vision_attempted,
                        "vision_used": vision,
                        "images_loaded": images_loaded,
                        "vision_reason": vision_reason,
                        "vision_error": vision_error,
                        "tool_calls": list(analysis.tool_calls),
                        "attributes": len(analysis.attributes),
                        "metrics": len(analysis.metrics),
                    },
                )
            ],
        }

    def tools(state: AgentState) -> dict:
        started = time.perf_counter()
        session = session_factory()
        try:
            requested = list(state["analysis"].get("tool_calls", []))
            results = []
            for name in requested:
                t0 = time.perf_counter()
                try:
                    r = run_tool(name, state, session, embedder)
                except Exception as e:  # one bad tool must not kill the consult
                    r = {"tool": name, "result": None, "error": f"{type(e).__name__}: {e}"}
                    logger.warning("tool %s failed: %s", name, r["error"])
                if name not in WHITELIST:
                    r.setdefault("error", "unknown tool (not in whitelist)")
                    logger.warning("tool %s is not in the whitelist — ignored", name)
                r["ms"] = round((time.perf_counter() - t0) * 1000, 1)
                results.append(r)

            # A pasted ingredient list → run the deterministic coverage check here rather
            # than letting the model reason about ingredients. The LLM writes the
            # comparison; the *facts* in it (which actives are present, which of the
            # user's recommendations are missing) come from `product_eval`.
            #
            # This is why the product path lives in the graph instead of a separate UI:
            # the reply is an ordinary chat bubble. `persist` will not write an Entry for
            # it, because `observes_skin` is false for a list of ingredients.
            product_eval = None
            if looks_like_ingredient_list(state["user_text"]):
                try:
                    ev = evaluate_for_conversation(
                        session, state["conversation_id"], state["user_text"]
                    )
                    product_eval = summarise_evaluation(ev)
                except Exception as e:  # evaluation must never kill the consult
                    logger.warning("product evaluation failed: %s: %s", type(e).__name__, e)

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
                "product_eval": product_eval,
                "recent_messages": recent_messages,
                "first_checkin": has_entries is None,
                "trace": [
                    _step(
                        "tools",
                        started,
                        {
                            "requested": requested,
                            "ran": [
                                {
                                    "tool": r["tool"],
                                    "rows": len(r["result"]) if isinstance(r["result"], list) else None,
                                    "error": r.get("error"),
                                }
                                for r in results
                            ],
                            "recent_messages": len(recent_messages),
                            "first_checkin": has_entries is None,
                            "product_eval": (
                                None
                                if product_eval is None
                                else {
                                    "verdict": product_eval["verdict"],
                                    "recognised": len(product_eval["recognised"]),
                                    "unknown": len(product_eval["unknown"]),
                                    "matched": product_eval["matched"],
                                    "missing": product_eval["missing"],
                                    "conflicts": len(product_eval["conflicts"]),
                                }
                            ),
                        },
                    )
                ],
            }
        finally:
            session.close()

    def advise(state: AgentState) -> dict:
        started = time.perf_counter()
        prompt = build_advise_prompt(state)
        advice = llm.structured(ADVISE_SYSTEM, prompt, Advice)
        return {
            "advice": advice.model_dump(),
            "trace": [
                _step(
                    "advise",
                    started,
                    {
                        # prompt_chars + tool_rows answer "有冇真係將檢索結果入到 prompt"
                        "prompt_chars": len(prompt),
                        "tool_rows": sum(
                            len(r["result"]) if isinstance(r.get("result"), list) else 0
                            for r in state.get("tool_results", [])
                        ),
                        "items": len(advice.items),
                        "reply_chars": len(advice.reply),
                        "detected_events": len(advice.detected_events),
                    },
                )
            ],
        }

    def guardrail(state: AgentState) -> dict:
        started = time.perf_counter()
        advice = Advice(**state["advice"])
        final, escalate = apply_guardrails(advice, state["user_text"])

        # A prescription ingredient in a pasted product is a deterministic hard stop, so
        # the reply is replaced with the computed text rather than left to whatever the
        # model phrased. `evaluate_product` deliberately suppresses coverage in this case
        # (showing "matched: 水楊酸" next to a drug reads as "mostly fine, just one bad
        # ingredient"), and the standalone route skips its narrative for the same reason.
        # Naming the ingredient is safe *and* more useful than the generic escalation,
        # because the user is the one who pasted it.
        forced: list[str] = []
        evaluation = state.get("product_eval") or {}
        if evaluation.get("escalate"):
            forced = [c["text"] for c in evaluation.get("conflicts", []) if c.get("kind") == "prescription"]
            if forced:
                escalate = True
                final = final.model_copy(update={"reply": forced[0], "items": forced})

        replaced = [i for i in advice.items if i not in final.items]
        return {
            "advice": final.model_dump(),
            "escalate": escalate,
            "trace": [
                _step(
                    "guardrail",
                    started,
                    {
                        "escalate": escalate,
                        "items_replaced": len(replaced),
                        "disclaimer_added": not advice.disclaimer and bool(final.disclaimer),
                        "forced_by_product_eval": bool(forced),
                    },
                )
            ],
        }

    def persist(state: AgentState) -> dict:
        started = time.perf_counter()
        session = session_factory()
        try:
            analysis = SkinAnalysis(**state["analysis"])
            conv_id = state["conversation_id"]
            today = datetime.date.today()
            now = utcnow()

            # Does this turn actually carry skin evidence? A question is not a check-in.
            #
            # `Entry` is the daily *structured summary* (doctrine #5): data truth for
            # change detection, the timeline and memory. Writing one from a message that
            # merely asked about a product replaced the day's real readings with the
            # "未提及就畀 0" analysis — and because only one agent timeline event per day
            # is allowed (`:316`), the resulting fake "改善" was frozen permanently: a
            # later real check-in could restore the attributes but never the event.
            # Measured on the live path: the model returns all six attributes as 0 for
            # 「呢支精華得唔得？」 and says so itself in the reply.
            #
            # A photo the vision model actually read is evidence by definition, so it
            # short-circuits the flag.
            observes_skin = bool(analysis.observes_skin) or bool(state.get("vision_used"))

            entry = session.query(Entry).filter_by(conversation_id=conv_id, date=today).first()
            entry_reused = entry is not None
            photos_added = 0
            timeline_lines: list[str] = []
            attributes_kept: list[str] = []  # 今次冇提及、保留當日舊讀數嘅 attribute
            insights_created = 0
            insights_strengthened = 0
            insights_superseded = 0

            if not observes_skin:
                # Skip the whole Entry block — including the timeline — but still write
                # the chat turns below (display truth). An existing Entry for today is
                # left completely untouched, so a question can never rewrite the day.
                pass
            else:
                if entry is None:
                    entry = Entry(conversation_id=conv_id, date=today)
                    session.add(entry)
                    session.flush()  # assign entry.id before attaching photos
                # Same-day merge (issue #21 policy B, chosen by the user): a later
                # check-in only replaces the attributes it actually mentioned. Before
                # this, 「今朝爆多咗兩粒」 reset the other five attributes to 0 — and the
                # anchors, the derived memories and the product verdict read those.
                entry.attributes, attributes_kept = merge_attributes(
                    entry.attributes or [], [a.model_dump() for a in analysis.attributes]
                )
                entry.metrics = merge_metrics(
                    entry.metrics or [], [m.model_dump() for m in analysis.metrics]
                )
                entry.note = merge_note(entry.note or "", state["user_text"])

            # Photos attach to the day's entry once (dedupe by file name); only
            # photos that actually exist on disk are linked (no dangling rows).
            existing_photo_names = {p.path for p in entry.photos} if entry is not None else set()
            for pid in state.get("photo_paths", []):
                if not photo_exists(pid):
                    continue
                if entry is None:
                    # No entry to attach to: a photo turn always has evidence, so this
                    # only happens if the model wrongly reported observes_skin=False
                    # while vision was off. Log it rather than drop the photo silently.
                    logger.warning(
                        "persist: 有相但唔寫 Entry（observes_skin=False、vision 冇行）pid=%s", pid
                    )
                    continue
                if f"photos/{pid}.jpg" not in existing_photo_names:
                    session.add(Photo(entry_id=entry.id, path=f"photos/{pid}.jpg"))
                    existing_photo_names.add(f"photos/{pid}.jpg")
                    photos_added += 1
            session.flush()

            # Timeline: deterministic change detection (Q24 — sparse, notable
            # changes only; one agent event per conversation per day at most).
            existing_agent_event = (
                session.query(TimelineEvent)
                .filter_by(conversation_id=conv_id, date=today, source="agent")
                .first()
            )
            if observes_skin and existing_agent_event is None:
                history = (
                    session.query(Entry)
                    .filter(Entry.conversation_id == conv_id, Entry.date < today)
                    .order_by(Entry.date.asc())
                    .all()
                )
                timeline_lines = build_change_lines(severity_map(entry.attributes or []), history, today)
                if timeline_lines:
                    session.add(
                        TimelineEvent(
                            conversation_id=conv_id,
                            date=today,
                            text="；".join(timeline_lines),
                            source="agent",
                        )
                    )

            # Long-term memory (Q14/Q47): one derived insight per attribute,
            # keyed by tag (attribute) + direction (problem/normal). Same
            # tag+direction strengthens (confidence up, expiry extended); a
            # direction flip supersedes and version-bumps, keeping history.
            #
            # Gated on `observes_skin` too: without it, asking about a product produced
            # a permanent「暗瘡：正常」memory for a user who never reported any skin state.
            #
            # And gated on `mentioned` (issue #21): the analysis rates all six
            # attributes every turn with「未提及就畀 0」, so a memory for an attribute the
            # user did NOT talk about would have been "strengthened" with a 0 it never
            # earned (measured before the fix: 6 of them on one vague message).
            for attr in analysis.attributes if observes_skin else []:
                if not attr.mentioned:
                    continue
                direction = direction_for(attr.severity)
                candidate = make_derived(
                    new_id(),
                    attr.key,
                    describe_attribute(attr.key, attr.severity),
                    0.6,
                    now,
                    direction=direction,
                )
                existing = (
                    session.query(Insight)
                    .filter_by(conversation_id=conv_id, kind="derived", tag=attr.key)
                    .filter(Insight.superseded_by.is_(None))
                    .first()
                )
                if existing is not None and not is_expired(from_orm(existing), now):
                    for r in reconcile(from_orm(existing), candidate, now):
                        if r.id == existing.id:
                            existing.confidence = r.confidence
                            existing.expires_at = r.expires_at
                            existing.text = r.text
                            existing.direction = r.direction
                            existing.superseded_by = r.superseded_by
                            insights_strengthened += 1
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
                            if r.superseded_by is None and r.version > 1:
                                insights_superseded += 1
                            else:
                                insights_created += 1
                else:
                    session.add(
                        Insight(
                            conversation_id=conv_id,
                            kind="derived",
                            tag=attr.key,
                            direction=direction,
                            text=describe_attribute(attr.key, attr.severity),
                            confidence=0.6,
                            expires_at=expiry_for(now),
                            version=1,
                        )
                    )
                    insights_created += 1

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
                    payload={
                        "photos": state.get("photo_paths", []),
                        # 用戶睇到嘅係「一條片」：UI 靠呢個 flag 出影片 chip 而唔係相
                        # （唔可以 leak「抽咗 6 張相」呢件事）。
                        "clip": state.get("clip"),
                    },
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
                        # Persisted so the「我留意到…✅ 記低」chips survive a reload
                        # (Q51 / issue #22). `events_applied` 之後由 confirm 嗰條 route
                        # 寫入 → reload 唔會再出已經記低咗嘅 chip。
                        "detected_events": list(advice.get("detected_events") or []),
                    },
                )
            )
            session.commit()
            return {
                "trace": [
                    _step(
                        "persist",
                        started,
                        {
                            # Visible evidence that a question did NOT become a day of data.
                            "observes_skin": observes_skin,
                            "entry_written": observes_skin,
                            "entry_reused": entry_reused,
                            "attributes": len(analysis.attributes) if observes_skin else 0,
                            "attributes_kept": attributes_kept,
                            "photos_added": photos_added,
                            "timeline_lines": len(timeline_lines),
                            "insights_created": insights_created,
                            "insights_strengthened": insights_strengthened,
                            "insights_superseded": insights_superseded,
                        },
                    )
                ]
            }
        finally:
            session.close()

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
